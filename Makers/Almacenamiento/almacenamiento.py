import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "datos" / "movimientos.db"


def obtener_conexion(db_path=DB_PATH):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conexion = sqlite3.connect(db_path)
    conexion.row_factory = sqlite3.Row
    return conexion


def inicializar_db(db_path=DB_PATH):
    """Crea la tabla de movimientos si no existe y migra las bases antiguas."""
    conexion = obtener_conexion(db_path)
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS movimientos (
            movimiento_id TEXT PRIMARY KEY,
            cliente_id TEXT NOT NULL,
            extracto_id TEXT NOT NULL,
            fecha_ingesta TEXT NOT NULL,
            nombre_remitente TEXT,
            tipo TEXT,
            categoria TEXT,
            monto REAL,
            moneda TEXT,
            nombre_destinatario TEXT,
            entidad TEXT,
            fecha TEXT,
            descripcion TEXT,
            requiere_revision_humana INTEGER,
            motivo_revision TEXT
        )
        """
    )
    conexion.execute(
        "CREATE INDEX IF NOT EXISTS idx_movimientos_cliente ON movimientos (cliente_id)"
    )

    # Migración: las bases creadas antes de añadir el triage no tienen estas
    # columnas y perdían la marca de revisión al guardar.
    existentes = {fila["name"] for fila in conexion.execute("PRAGMA table_info(movimientos)")}
    for columna, tipo_sql in (("requiere_revision_humana", "INTEGER"), ("motivo_revision", "TEXT")):
        if columna not in existentes:
            conexion.execute(f"ALTER TABLE movimientos ADD COLUMN {columna} {tipo_sql}")

    conexion.commit()
    conexion.close()


def _generar_movimiento_id(cliente_id, extracto_id, indice, datos):
    base = json.dumps(
        {"cliente_id": cliente_id, "extracto_id": extracto_id, "indice": indice, "datos": datos},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def guardar_movimientos(cliente_id, extracto_id, movimientos_anonimizados, db_path=DB_PATH):
    """
    Persiste el resultado ya anonimizado de un extracto para un cliente.

    `movimientos_anonimizados` es la lista que produce
    `anonimizar_movimiento()` en Anonimizacion/anonimizacion.py: no se vuelve a llamar a
    Ollama/Groq ni a anonimizar aquí, solo se guarda lo ya procesado.

    Solo se guardan los elementos con es_movimiento_financiero=True.
    Es idempotente: reprocesar el mismo extracto reemplaza sus filas en
    lugar de duplicarlas. Se borran las filas anteriores del extracto porque
    el LLM puede redactar distinto la descripción al reprocesar, y entonces
    el movimiento_id (que depende de los datos) ya no coincide.

    Devuelve la cantidad de movimientos guardados.
    """
    inicializar_db(db_path)
    conexion = obtener_conexion(db_path)
    fecha_ingesta = datetime.now(timezone.utc).isoformat()
    guardados = 0

    conexion.execute(
        "DELETE FROM movimientos WHERE cliente_id = ? AND extracto_id = ?",
        (cliente_id, extracto_id),
    )

    for indice, item in enumerate(movimientos_anonimizados):
        if not item.get("es_movimiento_financiero"):
            continue

        datos = item.get("movimiento") or {}
        movimiento_id = _generar_movimiento_id(cliente_id, extracto_id, indice, datos)

        conexion.execute(
            """
            INSERT OR REPLACE INTO movimientos (
                movimiento_id, cliente_id, extracto_id, fecha_ingesta,
                nombre_remitente, tipo, categoria, monto, moneda,
                nombre_destinatario, entidad, fecha, descripcion,
                requiere_revision_humana, motivo_revision
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                movimiento_id,
                cliente_id,
                extracto_id,
                fecha_ingesta,
                datos.get("nombre_remitente"),
                datos.get("tipo"),
                datos.get("categoria"),
                datos.get("monto"),
                datos.get("moneda"),
                datos.get("nombre_destinatario"),
                datos.get("entidad"),
                datos.get("fecha"),
                datos.get("descripcion"),
                int(bool(datos.get("requiere_revision_humana"))),
                datos.get("motivo_revision"),
            ),
        )
        guardados += 1

    conexion.commit()
    conexion.close()
    return guardados


def obtener_movimientos_cliente(cliente_id, db_path=DB_PATH):
    """Devuelve todos los movimientos guardados de un cliente, ordenados por fecha."""
    inicializar_db(db_path)
    conexion = obtener_conexion(db_path)
    filas = conexion.execute(
        "SELECT * FROM movimientos WHERE cliente_id = ? ORDER BY fecha",
        (cliente_id,),
    ).fetchall()
    conexion.close()

    movimientos = []
    for fila in filas:
        datos = dict(fila)
        # SQLite guarda el booleano como 0/1; se devuelve como bool.
        if datos["requiere_revision_humana"] is not None:
            datos["requiere_revision_humana"] = bool(datos["requiere_revision_humana"])
        movimientos.append(datos)
    return movimientos
