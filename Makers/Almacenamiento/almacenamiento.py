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
            motivo_revision TEXT,
            linea_id TEXT,
            numero_linea INTEGER
        )
        """
    )
    conexion.execute(
        "CREATE INDEX IF NOT EXISTS idx_movimientos_cliente ON movimientos (cliente_id)"
    )

    # Migración: añade a las bases antiguas las columnas que no tenían.
    existentes = {fila["name"] for fila in conexion.execute("PRAGMA table_info(movimientos)")}
    for columna, tipo_sql in (
        ("requiere_revision_humana", "INTEGER"),
        ("motivo_revision", "TEXT"),
        ("linea_id", "TEXT"),
        ("numero_linea", "INTEGER"),
    ):
        if columna not in existentes:
            conexion.execute(f"ALTER TABLE movimientos ADD COLUMN {columna} {tipo_sql}")
    conexion.execute(
        "CREATE INDEX IF NOT EXISTS idx_movimientos_linea ON movimientos (linea_id)"
    )

    # Las decisiones del titular van aparte: "movimientos" guarda lo que dijo
    # el pipeline y "revisiones" lo que decidió una persona. Así queda claro
    # quién afirmó qué, deshacer es borrar una fila, y reprocesar un extracto
    # no pisa las decisiones (los ids de movimiento son estables).
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS revisiones (
            movimiento_id TEXT PRIMARY KEY,
            cliente_id TEXT NOT NULL,
            decision TEXT NOT NULL CHECK (decision IN ('confirmado', 'descartado', 'corregido')),
            correcciones TEXT,
            ejemplo_rag_id TEXT,
            revisado_en TEXT NOT NULL
        )
        """
    )
    conexion.execute(
        "CREATE INDEX IF NOT EXISTS idx_revisiones_cliente ON revisiones (cliente_id)"
    )
    # Valores efectivos: lo que corrigió el titular manda sobre lo extraído.
    # Incluye los descartados, para poder mostrarlos tachados.
    conexion.execute(
        """
        CREATE VIEW IF NOT EXISTS movimientos_efectivos AS
        SELECT
            m.movimiento_id, m.cliente_id, m.extracto_id, m.fecha_ingesta,
            m.nombre_remitente, m.nombre_destinatario, m.entidad, m.descripcion,
            COALESCE(json_extract(r.correcciones, '$.tipo'), m.tipo) AS tipo,
            COALESCE(json_extract(r.correcciones, '$.categoria'), m.categoria) AS categoria,
            COALESCE(json_extract(r.correcciones, '$.monto'), m.monto) AS monto,
            COALESCE(json_extract(r.correcciones, '$.moneda'), m.moneda) AS moneda,
            COALESCE(json_extract(r.correcciones, '$.fecha'), m.fecha) AS fecha,
            m.requiere_revision_humana, m.motivo_revision, m.linea_id, m.numero_linea,
            r.decision, r.revisado_en,
            CASE WHEN m.requiere_revision_humana = 1 AND r.decision IS NULL THEN 1 ELSE 0 END AS pendiente
        FROM movimientos m
        LEFT JOIN revisiones r ON r.movimiento_id = m.movimiento_id
        """
    )
    # Lecturas redactadas por Groq, una por titular y periodo. La huella son las
    # cifras con que se redactó: si no cambiaron, la lectura sigue vigente y no
    # hace falta volver a llamar al modelo.
    conexion.execute(
        """
        CREATE TABLE IF NOT EXISTS lecturas (
            cliente_id TEXT NOT NULL,
            periodo TEXT NOT NULL,
            huella TEXT NOT NULL,
            texto TEXT NOT NULL,
            generado_en TEXT NOT NULL,
            PRIMARY KEY (cliente_id, periodo)
        )
        """
    )
    # Lo que cuenta en los cálculos. Todas las cifras salen de aquí, para que
    # ninguna consulta pueda olvidarse de excluir lo descartado.
    conexion.execute(
        """
        CREATE VIEW IF NOT EXISTS movimientos_vigentes AS
        SELECT * FROM movimientos_efectivos
        WHERE decision IS NULL OR decision != 'descartado'
        """
    )

    conexion.commit()
    conexion.close()


def id_extracto(contenido):
    """
    Identificador de un extracto a partir de su CONTENIDO, no de su nombre.

    Con el nombre, dos archivos distintos llamados igual se pisaban, y la
    terminal y el servidor daban ids distintos al mismo archivo, así que una
    transacción podía entrar dos veces.
    """
    if isinstance(contenido, str):
        contenido = contenido.encode("utf-8")
    return "ext-" + hashlib.sha256(contenido).hexdigest()[:16]


def _id_linea(cliente_id, extracto_id, numero_linea, texto_linea):
    """
    Identificador estable de una línea de entrada.

    Sale del texto de ENTRADA y de su posición, nunca de lo que respondió el
    modelo: el modelo redacta distinto en cada corrida, y un id que dependa de
    eso cambia al reprocesar. La posición distingue dos líneas idénticas que
    pueden aparecer legítimamente en un mismo extracto.
    """
    base = json.dumps([cliente_id, extracto_id, numero_linea, texto_linea], ensure_ascii=False)
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def guardar_linea(cliente_id, extracto_id, numero_linea, texto_linea, movimientos, db_path=DB_PATH):
    """
    Guarda los movimientos que salieron de UNA línea del extracto.

    `movimientos` es la salida ya anonimizada del pipeline. Solo reemplaza las
    filas de esa línea: si otra línea falla al reprocesar, sus filas anteriores
    siguen intactas. Antes se borraba el extracto entero y se guardaba solo lo
    que había salido bien, así que una línea fallida desaparecía en silencio.

    Borrar y volver a insertar ocurre en una sola transacción. Solo se guardan
    los elementos financieros. Devuelve cuántos se guardaron.
    """
    linea_id = _id_linea(cliente_id, extracto_id, numero_linea, texto_linea)
    financieros = [m for m in movimientos if m.get("es_movimiento_financiero")]

    inicializar_db(db_path)
    conexion = obtener_conexion(db_path)
    fecha_ingesta = datetime.now(timezone.utc).isoformat()
    try:
        conexion.execute("DELETE FROM movimientos WHERE linea_id = ?", (linea_id,))
        for posicion, item in enumerate(financieros):
            datos = item.get("movimiento") or {}
            conexion.execute(
                """
                INSERT INTO movimientos (
                    movimiento_id, cliente_id, extracto_id, fecha_ingesta,
                    nombre_remitente, tipo, categoria, monto, moneda,
                    nombre_destinatario, entidad, fecha, descripcion,
                    requiere_revision_humana, motivo_revision,
                    linea_id, numero_linea
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    hashlib.sha256(f"{linea_id}:{posicion}".encode("utf-8")).hexdigest(),
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
                    linea_id,
                    numero_linea,
                ),
            )
        conexion.commit()
    finally:
        conexion.close()
    return len(financieros)


def obtener_movimientos_cliente(cliente_id, db_path=DB_PATH):
    """Devuelve todos los movimientos guardados de un cliente, ordenados por fecha."""
    inicializar_db(db_path)
    conexion = obtener_conexion(db_path)
    filas = conexion.execute(
        "SELECT * FROM movimientos_efectivos WHERE cliente_id = ? ORDER BY fecha",
        (cliente_id,),
    ).fetchall()
    conexion.close()

    movimientos = []
    for fila in filas:
        datos = dict(fila)
        # SQLite guarda los booleanos como 0/1; se devuelven como bool.
        for campo in ("requiere_revision_humana", "pendiente"):
            if datos.get(campo) is not None:
                datos[campo] = bool(datos[campo])
        movimientos.append(datos)
    return movimientos


def borrar_cliente(cliente_id, db_path=DB_PATH):
    """Elimina todos los movimientos de un titular. Devuelve cuántos borró."""
    inicializar_db(db_path)
    conexion = obtener_conexion(db_path)
    cursor = conexion.execute("DELETE FROM movimientos WHERE cliente_id = ?", (cliente_id,))
    # Sin esto, volver a cargar los mismos extractos reaplicaría decisiones
    # viejas: los ids son estables y coincidirían.
    conexion.execute("DELETE FROM revisiones WHERE cliente_id = ?", (cliente_id,))
    conexion.execute("DELETE FROM lecturas WHERE cliente_id = ?", (cliente_id,))
    conexion.commit()
    conexion.close()
    return cursor.rowcount


def leer_lecturas(cliente_id, db_path=DB_PATH):
    """Lecturas guardadas del titular: {periodo: {"huella", "texto", "generado_en"}}."""
    inicializar_db(db_path)
    conexion = obtener_conexion(db_path)
    try:
        return {
            f["periodo"]: {"huella": f["huella"], "texto": f["texto"], "generado_en": f["generado_en"]}
            for f in conexion.execute(
                "SELECT periodo, huella, texto, generado_en FROM lecturas WHERE cliente_id = ?", (cliente_id,)
            )
        }
    finally:
        conexion.close()


def guardar_lectura(cliente_id, periodo, huella, texto, db_path=DB_PATH):
    inicializar_db(db_path)
    conexion = obtener_conexion(db_path)
    try:
        conexion.execute(
            "INSERT OR REPLACE INTO lecturas VALUES (?, ?, ?, ?, ?)",
            (cliente_id, periodo, huella, texto, datetime.now(timezone.utc).isoformat()),
        )
        conexion.commit()
    finally:
        conexion.close()
