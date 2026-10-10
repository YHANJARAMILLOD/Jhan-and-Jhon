"""
Consultas precisas sobre los movimientos guardados, para el asistente.

Las cifras que cita el asistente salen de aquí, de SQL parametrizado. El LLM
solo propone filtros, que se validan contra listas cerradas antes de llegar;
nunca calcula ni escribe SQL. Las condiciones del WHERE son texto fijo: lo
único variable son los valores, que van siempre como parámetros.
"""
from Almacenamiento.almacenamiento import DB_PATH, inicializar_db, obtener_conexion

LIMITE_MOVIMIENTOS = 8


def _filas(db_path, sql, parametros):
    inicializar_db(db_path)
    conexion = obtener_conexion(db_path)
    filas = [dict(f) for f in conexion.execute(sql, parametros).fetchall()]
    conexion.close()
    return filas


def _contraparte(m):
    # En un egreso la contraparte es el destinatario; en un ingreso, el
    # remitente. El otro campo lleva al titular enmascarado.
    if m.get("tipo") == "ingreso":
        return m.get("nombre_remitente") or m.get("entidad")
    return m.get("nombre_destinatario") or m.get("entidad")


def periodos_disponibles(cliente_id, db_path=DB_PATH):
    """Meses (YYYY-MM) con movimientos fechados, en orden."""
    filas = _filas(
        db_path,
        """
        SELECT DISTINCT substr(fecha, 1, 7) AS periodo FROM movimientos_vigentes
        WHERE cliente_id = ? AND fecha IS NOT NULL
        ORDER BY periodo
        """,
        (cliente_id,),
    )
    return [f["periodo"] for f in filas]


def version_datos(cliente_id, db_path=DB_PATH):
    """
    Cambia cada vez que se guardan movimientos o el titular revisa uno: sirve de
    clave de caché. Sin las revisiones, el asistente seguiría respondiendo con
    cifras de antes de una corrección.
    """
    fila = _filas(
        db_path,
        """
        SELECT
            (SELECT COUNT(*) FROM movimientos WHERE cliente_id = ?) AS n,
            (SELECT MAX(fecha_ingesta) FROM movimientos WHERE cliente_id = ?) AS ultima,
            (SELECT COUNT(*) FROM revisiones WHERE cliente_id = ?) AS r,
            (SELECT MAX(revisado_en) FROM revisiones WHERE cliente_id = ?) AS ultima_revision
        """,
        (cliente_id, cliente_id, cliente_id, cliente_id),
    )[0]
    return f"{fila['n']}:{fila['ultima']}:{fila['r']}:{fila['ultima_revision']}"


def consultar(cliente_id, periodo=None, categoria=None, tipo=None, db_path=DB_PATH):
    """
    Totales, desglose por categoría y movimientos principales para los
    filtros dados. Todos los filtros son opcionales.
    """
    condiciones = ["cliente_id = ?", "monto IS NOT NULL"]
    parametros = [cliente_id]
    if periodo:
        condiciones.append("substr(fecha, 1, 7) = ?")
        parametros.append(periodo)
    if categoria:
        condiciones.append("categoria = ?")
        parametros.append(categoria)
    if tipo:
        condiciones.append("tipo = ?")
        parametros.append(tipo)
    donde = " AND ".join(condiciones)

    totales = {}
    for f in _filas(db_path, f"""
        SELECT moneda, tipo, COUNT(*) AS n, SUM(monto) AS total
        FROM movimientos_vigentes WHERE {donde} GROUP BY moneda, tipo
    """, parametros):
        t = totales.setdefault(f["moneda"], {"moneda": f["moneda"], "ingresos": 0.0,
                                             "egresos": 0.0, "n_movimientos": 0})
        if f["tipo"] in ("ingreso", "egreso"):
            t[f["tipo"] + "s"] = f["total"]
        t["n_movimientos"] += f["n"]
    for t in totales.values():
        t["balance"] = t["ingresos"] - t["egresos"]

    por_categoria = _filas(db_path, f"""
        SELECT categoria, tipo, moneda, COUNT(*) AS n_movimientos, SUM(monto) AS total
        FROM movimientos_vigentes WHERE {donde} AND categoria IS NOT NULL
        GROUP BY categoria, tipo, moneda ORDER BY total DESC
    """, parametros)

    movimientos = [
        {
            "fecha": m["fecha"],
            "tipo": m["tipo"],
            "categoria": m["categoria"],
            "monto": m["monto"],
            "moneda": m["moneda"],
            "contraparte": _contraparte(m),
            "descripcion": m["descripcion"],
            # Si sigue pendiente, no si alguna vez se marcó: una vez que el
            # titular decide, el asistente no debe seguir avisando.
            "pendiente_de_revision": bool(m["pendiente"]),
        }
        for m in _filas(db_path, f"""
            SELECT * FROM movimientos_vigentes WHERE {donde} ORDER BY monto DESC LIMIT ?
        """, [*parametros, LIMITE_MOVIMIENTOS])
    ]

    return {
        "filtros": {"periodo": periodo, "categoria": categoria, "tipo": tipo},
        "totales": list(totales.values()),
        "por_categoria": por_categoria,
        "movimientos_principales": movimientos,
    }
