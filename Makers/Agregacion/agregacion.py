"""
Agregación de los movimientos guardados: totales por periodo, categorías
principales y anomalías. Todo se calcula con SQL y Python, sin LLM: los
números del resumen deben ser reproducibles y auditables.
"""
import statistics

from Almacenamiento.almacenamiento import DB_PATH, inicializar_db, obtener_conexion

# Los movimientos sin fecha no se descartan: se agrupan aparte para que el
# resumen pueda decir cuántos quedaron fuera del análisis temporal.
PERIODO_SIN_FECHA = "sin_fecha"

_LONGITUD_PERIODO = {"mes": 7, "anio": 4}


def _consultar(db_path, sql, parametros):
    inicializar_db(db_path)
    conexion = obtener_conexion(db_path)
    filas = conexion.execute(sql, parametros).fetchall()
    conexion.close()
    return filas


def resumen_por_periodo(cliente_id, granularidad="mes", db_path=DB_PATH):
    """
    Ingresos, egresos y balance por periodo y moneda.

    `granularidad`: "mes" (YYYY-MM) o "anio" (YYYY). Los montos no se suman
    entre monedas distintas: cada moneda se reporta por separado.
    """
    if granularidad not in _LONGITUD_PERIODO:
        raise ValueError(f"Granularidad no soportada: {granularidad}. Usa 'mes' o 'anio'.")

    filas = _consultar(
        db_path,
        f"""
        SELECT
            COALESCE(substr(fecha, 1, {_LONGITUD_PERIODO[granularidad]}), '{PERIODO_SIN_FECHA}') AS periodo,
            moneda, tipo, COUNT(*) AS n, SUM(monto) AS total
        FROM movimientos_vigentes
        WHERE cliente_id = ? AND monto IS NOT NULL
        GROUP BY periodo, moneda, tipo
        ORDER BY periodo, moneda
        """,
        (cliente_id,),
    )

    periodos = {}
    for fila in filas:
        clave = (fila["periodo"], fila["moneda"])
        resumen = periodos.setdefault(
            clave,
            {
                "periodo": fila["periodo"],
                "moneda": fila["moneda"],
                "ingresos": 0.0,
                "egresos": 0.0,
                "balance": 0.0,
                "n_movimientos": 0,
            },
        )
        if fila["tipo"] in ("ingreso", "egreso"):
            resumen[fila["tipo"] + "s"] = fila["total"]
        resumen["n_movimientos"] += fila["n"]

    for resumen in periodos.values():
        resumen["balance"] = resumen["ingresos"] - resumen["egresos"]

    return sorted(periodos.values(), key=lambda r: (r["periodo"], r["moneda"] or ""))


def top_categorias(cliente_id, tipo="egreso", limite=5, db_path=DB_PATH, periodo=None):
    """
    Categorías ordenadas por monto total, con su peso sobre el total del
    tipo y la moneda correspondientes. Con `periodo` ("2026-10" o "2026"),
    solo cuenta los movimientos de ese periodo.
    """
    filtro, parametros = "", [cliente_id, tipo]
    if periodo:
        filtro = "AND substr(fecha, 1, ?) = ?"
        parametros += [len(periodo), periodo]
    filas = _consultar(
        db_path,
        f"""
        SELECT categoria, moneda, COUNT(*) AS n, SUM(monto) AS total
        FROM movimientos_vigentes
        WHERE cliente_id = ? AND tipo = ? AND monto IS NOT NULL AND categoria IS NOT NULL {filtro}
        GROUP BY categoria, moneda
        ORDER BY total DESC
        """,
        parametros,
    )

    totales_por_moneda = {}
    for fila in filas:
        totales_por_moneda[fila["moneda"]] = totales_por_moneda.get(fila["moneda"], 0.0) + fila["total"]

    categorias = [
        {
            "categoria": fila["categoria"],
            "moneda": fila["moneda"],
            "total": fila["total"],
            "n_movimientos": fila["n"],
            "porcentaje": round(100 * fila["total"] / totales_por_moneda[fila["moneda"]], 1)
            if totales_por_moneda.get(fila["moneda"])
            else None,
        }
        for fila in filas
    ]
    return categorias[:limite] if limite else categorias


def detectar_anomalias(cliente_id, umbral_desviaciones=2.0, minimo_historico=5, db_path=DB_PATH):
    """
    Movimientos cuyo monto se aleja del comportamiento habitual del cliente.

    Se compara cada monto con la media y la desviación estándar de los
    movimientos del mismo tipo y moneda. Hace falta un histórico mínimo
    (`minimo_historico`) para que la estadística signifique algo.

    Limitación conocida: la propia anomalía infla la desviación, así que dos
    valores extremos parecidos pueden enmascararse entre sí. Es una detección
    orientativa, no una prueba.
    """
    filas = _consultar(
        db_path,
        """
        SELECT movimiento_id, fecha, tipo, categoria, monto, moneda,
               nombre_destinatario, descripcion
        FROM movimientos_vigentes
        WHERE cliente_id = ? AND monto IS NOT NULL AND tipo IS NOT NULL
        """,
        (cliente_id,),
    )

    grupos = {}
    for fila in filas:
        grupos.setdefault((fila["tipo"], fila["moneda"]), []).append(dict(fila))

    anomalias = []
    for (tipo, moneda), movimientos in grupos.items():
        montos = [m["monto"] for m in movimientos]
        if len(montos) < minimo_historico:
            continue

        media = statistics.fmean(montos)
        desviacion = statistics.stdev(montos)
        if desviacion == 0:
            continue

        for movimiento in movimientos:
            z = (movimiento["monto"] - media) / desviacion
            if z >= umbral_desviaciones:
                anomalias.append({
                    **movimiento,
                    "desviaciones": round(z, 2),
                    "media_del_grupo": round(media, 2),
                    "veces_la_media": round(movimiento["monto"] / media, 1),
                })

    return sorted(anomalias, key=lambda a: -a["desviaciones"])


def movimientos_para_revision(cliente_id, db_path=DB_PATH):
    """Movimientos marcados para revisión que el titular todavía no resolvió."""
    filas = _consultar(
        db_path,
        """
        SELECT movimiento_id, fecha, tipo, categoria, monto, moneda,
               descripcion, motivo_revision
        FROM movimientos_efectivos
        WHERE cliente_id = ? AND pendiente = 1
        ORDER BY fecha
        """,
        (cliente_id,),
    )
    return [dict(fila) for fila in filas]
