"""
Revisión humana de los movimientos marcados por el pipeline.

Las decisiones se guardan en la tabla "revisiones" y nunca sobrescriben lo
extraído: los cálculos leen la vista "movimientos_vigentes", que aplica las
correcciones y excluye lo descartado. Así cada decisión cambia los totales al
instante, sin que el titular tenga que descontar nada a mano, y se puede
deshacer.
"""
import json
import math
import warnings
from datetime import datetime, timezone

from Almacenamiento.almacenamiento import DB_PATH, inicializar_db, obtener_conexion
from Constantes.Principales_constantes import (
    CATEGORIAS_PERMITIDAS, MONEDAS_PERMITIDAS, TIPOS_PERMITIDOS,
)

CATEGORIAS_PERMITIDAS = CATEGORIAS_PERMITIDAS()
MONEDAS_PERMITIDAS = MONEDAS_PERMITIDAS()
TIPOS_PERMITIDOS = TIPOS_PERMITIDOS()

ACCIONES = {"confirmar", "descartar", "duplicado_si", "duplicado_no", "corregir", "deshacer"}
CAMPOS_CORREGIBLES = {"monto", "moneda", "fecha", "tipo", "categoria"}
# Sin estos tres un movimiento no puede sumarse: no tiene sentido darlo por bueno.
CAMPOS_ESENCIALES = ("monto", "tipo", "moneda")
MAX_IDS = 10
MAX_MONTO = 1e12


def _filas(db_path, sql, parametros=()):
    inicializar_db(db_path)
    conexion = obtener_conexion(db_path)
    try:
        return [dict(f) for f in conexion.execute(sql, parametros).fetchall()]
    finally:
        conexion.close()


def _contraparte(m):
    if m.get("tipo") == "ingreso":
        return m.get("nombre_remitente") or m.get("entidad")
    return m.get("nombre_destinatario") or m.get("entidad")


def _motivos(m):
    return [x.strip() for x in str(m.get("motivo_revision") or "").split(",") if x.strip()]


# ───────────────────────── Lectura ─────────────────────────

def elementos_revision(cliente_id, db_path=DB_PATH):
    """
    Movimientos marcados, agrupados como los ve el titular.

    Los posibles duplicados de una misma línea se agrupan en un solo elemento:
    la pregunta es "¿es el mismo pago?", no "¿es válido cada uno?". Devuelve
    {"pendientes": [...], "resueltos": [...]}.
    """
    filas = _filas(
        db_path,
        """
        SELECT * FROM movimientos_efectivos
        WHERE cliente_id = ? AND requiere_revision_humana = 1
        ORDER BY numero_linea, movimiento_id
        """,
        (cliente_id,),
    )

    grupos = {}
    for m in filas:
        if "posible_duplicado" in _motivos(m):
            clave = ("dup", m["linea_id"], m["tipo"], m["monto"], m["moneda"], m["fecha"])
        else:
            clave = ("uno", m["movimiento_id"])
        grupos.setdefault(clave, []).append(m)

    pendientes, resueltos = [], []
    for clave, miembros in grupos.items():
        base = miembros[0]
        duplicado = clave[0] == "dup" and len(miembros) > 1
        elemento = {
            "clave": base["movimiento_id"],
            "caso": "duplicado" if duplicado else "individual",
            "ids": [m["movimiento_id"] for m in miembros],
            "repeticiones": len(miembros),
            "motivos": _motivos(base),
            "movimiento": {
                "fecha": base["fecha"], "tipo": base["tipo"], "categoria": base["categoria"],
                "monto": base["monto"], "moneda": base["moneda"],
                "descripcion": base["descripcion"], "contraparte": _contraparte(base),
            },
            "faltantes": [c for c in ("monto", "tipo", "moneda", "categoria", "fecha") if base.get(c) is None],
            "decisiones": [m["decision"] for m in miembros],
        }
        (pendientes if any(m["pendiente"] for m in miembros) else resueltos).append(elemento)

    return {"pendientes": pendientes, "resueltos": resueltos}


# ───────────────────────── Validación ─────────────────────────

def _validar_correcciones(valores, actual):
    if not isinstance(valores, dict) or not valores:
        raise ValueError("No se recibió ningún dato para corregir.")
    desconocidos = set(valores) - CAMPOS_CORREGIBLES
    if desconocidos:
        raise ValueError(f"No se pueden corregir estos campos: {', '.join(sorted(desconocidos))}.")

    limpio = {}
    if "monto" in valores:
        monto = valores["monto"]
        if isinstance(monto, bool) or not isinstance(monto, (int, float)) or not math.isfinite(monto):
            raise ValueError("El monto debe ser un número.")
        if not 0 < monto < MAX_MONTO:
            raise ValueError("El monto debe ser mayor que cero.")
        limpio["monto"] = round(float(monto), 2)
    if "moneda" in valores:
        moneda = str(valores["moneda"] or "").upper()
        if moneda not in MONEDAS_PERMITIDAS:
            raise ValueError("Moneda no permitida.")
        limpio["moneda"] = moneda
    if "fecha" in valores:
        fecha = valores["fecha"]
        try:
            limpio["fecha"] = datetime.strptime(str(fecha), "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            raise ValueError("La fecha debe tener el formato AAAA-MM-DD.") from None
    if "tipo" in valores:
        if valores["tipo"] not in TIPOS_PERMITIDOS:
            raise ValueError("El tipo debe ser ingreso o egreso.")
        limpio["tipo"] = valores["tipo"]
    if "categoria" in valores:
        if valores["categoria"] not in CATEGORIAS_PERMITIDAS:
            raise ValueError("Categoría no permitida.")
        limpio["categoria"] = valores["categoria"]

    tipo_final = limpio.get("tipo", actual.get("tipo"))
    if limpio.get("categoria", actual.get("categoria")) == "ingreso_laboral" and tipo_final != "ingreso":
        raise ValueError("«Ingreso laboral» solo aplica a ingresos.")
    return limpio


def _exigir_esenciales(movimiento, correcciones=None):
    final = {**movimiento, **(correcciones or {})}
    faltan = [c for c in CAMPOS_ESENCIALES if final.get(c) is None]
    if faltan:
        raise ValueError(f"Antes de darlo por bueno, completa: {', '.join(faltan)}.")


# ───────────────────────── Escritura ─────────────────────────

def _guardar_revisiones(db_path, filas):
    inicializar_db(db_path)
    conexion = obtener_conexion(db_path)
    try:
        conexion.executemany(
            """
            INSERT OR REPLACE INTO revisiones
                (movimiento_id, cliente_id, decision, correcciones, ejemplo_rag_id, revisado_en)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            filas,
        )
        conexion.commit()
    finally:
        conexion.close()


def aplicar(cliente_id, accion, ids, valores=None, db_path=DB_PATH, rag_db_path=None):
    """
    Aplica una decisión del titular. Lanza ValueError con un mensaje legible si
    la petición no es válida. Devuelve cuántos movimientos cambió.

    Solo se pueden revisar movimientos que el pipeline marcó y que pertenecen al
    titular indicado: el id lo manda el navegador y no se da por bueno.
    """
    if accion not in ACCIONES:
        raise ValueError("Acción desconocida.")
    if (not isinstance(ids, list) or not ids or len(ids) > MAX_IDS
            or not all(isinstance(i, str) and i for i in ids)):
        raise ValueError("Movimientos inválidos.")
    ids = sorted(set(ids))

    marcadores = ",".join("?" * len(ids))
    filas = _filas(
        db_path,
        f"""
        SELECT * FROM movimientos_efectivos
        WHERE cliente_id = ? AND requiere_revision_humana = 1 AND movimiento_id IN ({marcadores})
        ORDER BY numero_linea, movimiento_id
        """,
        (cliente_id, *ids),
    )
    if len(filas) != len(ids):
        raise ValueError("Alguno de esos movimientos no existe o no está marcado para revisión.")

    ahora = datetime.now(timezone.utc).isoformat()

    if accion == "deshacer":
        return _deshacer(cliente_id, ids, db_path, rag_db_path)

    if accion in ("duplicado_si", "duplicado_no") and len(filas) < 2:
        raise ValueError("Un duplicado necesita al menos dos movimientos.")

    if accion == "confirmar":
        for m in filas:
            _exigir_esenciales(m)
        nuevas = [(m["movimiento_id"], cliente_id, "confirmado", None, None, ahora) for m in filas]
    elif accion == "descartar":
        nuevas = [(m["movimiento_id"], cliente_id, "descartado", None, None, ahora) for m in filas]
    elif accion == "duplicado_no":
        for m in filas:
            _exigir_esenciales(m)
        nuevas = [(m["movimiento_id"], cliente_id, "confirmado", None, None, ahora) for m in filas]
    elif accion == "duplicado_si":
        # Se conserva el primero y se descartan las copias. Ninguno se borra:
        # el descartado queda en el libro, tachado.
        _exigir_esenciales(filas[0])
        nuevas = [(filas[0]["movimiento_id"], cliente_id, "confirmado", None, None, ahora)]
        nuevas += [(m["movimiento_id"], cliente_id, "descartado", None, None, ahora) for m in filas[1:]]
    else:  # corregir
        if len(filas) != 1:
            raise ValueError("Se corrige un movimiento a la vez.")
        m = filas[0]
        correcciones = _validar_correcciones(valores, m)
        _exigir_esenciales(m, correcciones)
        ejemplo = _aprender_categoria(m, correcciones, rag_db_path)
        nuevas = [(m["movimiento_id"], cliente_id, "corregido",
                   json.dumps(correcciones, ensure_ascii=False), ejemplo, ahora)]

    _guardar_revisiones(db_path, nuevas)
    return len(nuevas)


def _aprender_categoria(movimiento, correcciones, rag_db_path):
    """
    Una categoría corregida por una persona pasa a ser un ejemplo del RAG, para
    que el revisor acierte la próxima vez. Si el RAG falla, la corrección se
    guarda igual: es una ayuda, no un requisito.
    """
    categoria = correcciones.get("categoria")
    if not categoria or categoria == movimiento.get("categoria"):
        return None
    try:
        from Recuperacion.recuperacion import agregar_ejemplo

        datos = {**movimiento, **correcciones}
        argumentos = {"db_path": rag_db_path} if rag_db_path else {}
        return agregar_ejemplo(datos, categoria, origen="humano", **argumentos)
    except Exception as error:
        warnings.warn(f"No se pudo agregar el ejemplo al RAG: {type(error).__name__}: {error}")
        return None


def _deshacer(cliente_id, ids, db_path, rag_db_path):
    marcadores = ",".join("?" * len(ids))
    previas = _filas(
        db_path,
        f"SELECT ejemplo_rag_id FROM revisiones WHERE cliente_id = ? AND movimiento_id IN ({marcadores})",
        (cliente_id, *ids),
    )
    for fila in previas:
        if fila["ejemplo_rag_id"]:
            try:
                from Recuperacion.recuperacion import quitar_ejemplo

                argumentos = {"db_path": rag_db_path} if rag_db_path else {}
                quitar_ejemplo(fila["ejemplo_rag_id"], **argumentos)
            except Exception as error:
                warnings.warn(f"No se pudo retirar el ejemplo del RAG: {type(error).__name__}: {error}")

    inicializar_db(db_path)
    conexion = obtener_conexion(db_path)
    try:
        borradas = conexion.execute(
            f"DELETE FROM revisiones WHERE cliente_id = ? AND movimiento_id IN ({marcadores})",
            (cliente_id, *ids),
        ).rowcount
        conexion.commit()
    finally:
        conexion.close()
    return borradas
