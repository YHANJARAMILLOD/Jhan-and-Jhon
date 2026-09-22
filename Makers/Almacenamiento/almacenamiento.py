import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "datos" / "movimientos.db"

_CAMPOS_MOVIMIENTO = (
    "nombre_remitente",
    "tipo",
    "categoria",
    "monto",
    "moneda",
    "nombre_destinatario",
    "entidad",
    "fecha",
    "descripcion",
)


def obtener_conexion(db_path=DB_PATH):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conexion = sqlite3.connect(db_path)
    conexion.row_factory = sqlite3.Row
    return conexion


def inicializar_db(db_path=DB_PATH):
    """Crea la tabla de movimientos si no existe."""
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
            descripcion TEXT
        )
        """
    )
    conexion.execute(
        "CREATE INDEX IF NOT EXISTS idx_movimientos_cliente ON movimientos (cliente_id)"
    )
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
    `anonimizar_movimiento()` en jhonyjhan.py: no se vuelve a llamar a
    Ollama/Groq ni a anonimizar aquí, solo se guarda lo ya procesado.

    Solo se guardan los elementos con es_movimiento_financiero=True.
    Es idempotente: reprocesar el mismo extracto sobrescribe las mismas
    filas en lugar de duplicarlas.

    Devuelve la cantidad de movimientos guardados.
    """
    inicializar_db(db_path)
    conexion = obtener_conexion(db_path)
    fecha_ingesta = datetime.now(timezone.utc).isoformat()
    guardados = 0

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
                nombre_destinatario, entidad, fecha, descripcion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            ),
        )
        guardados += 1

    conexion.commit()
    conexion.close()
    return guardados


def obtener_movimientos_cliente(cliente_id, db_path=DB_PATH):
    """Devuelve todos los movimientos guardados de un cliente, ordenados por fecha."""
    conexion = obtener_conexion(db_path)
    filas = conexion.execute(
        "SELECT * FROM movimientos WHERE cliente_id = ? ORDER BY fecha",
        (cliente_id,),
    ).fetchall()
    conexion.close()
    return [dict(fila) for fila in filas]
