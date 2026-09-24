"""
Exporta a JSON lo que necesita el dashboard estático.

El dashboard es solo lectura y se despliega como sitio estático, así que no
consulta la base: consume este archivo. Hay que volver a exportar cada vez
que se procesen movimientos nuevos.

AVISO DE PRIVACIDAD: el JSON lleva los nombres del cliente enmascarados,
pero los montos, las fechas y las contrapartes (Netflix, Falabella...) van
en claro. No publiques un export de un cliente real en una URL pública.
"""
import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

from Agregacion.agregacion import (
    detectar_anomalias,
    movimientos_para_revision,
    resumen_por_periodo,
    top_categorias,
)
from Almacenamiento.almacenamiento import obtener_movimientos_cliente

RUTA_POR_DEFECTO = Path(__file__).resolve().parent.parent.parent / "dashboard" / "datos.json"


def _totales_por_moneda(periodos):
    """Totales de todo el histórico. Cada moneda se totaliza por separado."""
    totales = {}
    for periodo in periodos:
        acumulado = totales.setdefault(
            periodo["moneda"],
            {"moneda": periodo["moneda"], "ingresos": 0.0, "egresos": 0.0,
             "balance": 0.0, "n_movimientos": 0},
        )
        acumulado["ingresos"] += periodo["ingresos"]
        acumulado["egresos"] += periodo["egresos"]
        acumulado["n_movimientos"] += periodo["n_movimientos"]

    for acumulado in totales.values():
        acumulado["balance"] = acumulado["ingresos"] - acumulado["egresos"]

    return sorted(totales.values(), key=lambda t: -t["n_movimientos"])


def _ordenar_por_fecha_desc(movimientos):
    """Más recientes primero. Los que no tienen fecha van al final."""
    return sorted(movimientos, key=lambda m: (m["fecha"] is not None, m["fecha"] or ""), reverse=True)


def construir_datos_dashboard(cliente_id, granularidad="mes", incluir_texto=True, db_path=None):
    """
    Arma el diccionario que consume el dashboard.

    A diferencia de resumen_cliente(), aquí las categorías van completas (sin
    top 5): si se recortan, los porcentajes no suman 100 y el gráfico miente.
    """
    argumentos = {"db_path": db_path} if db_path else {}

    periodos = resumen_por_periodo(cliente_id, granularidad, **argumentos)
    if not periodos:
        raise ValueError(f"El cliente '{cliente_id}' no tiene movimientos guardados.")

    movimientos = obtener_movimientos_cliente(cliente_id, **argumentos)
    totales = _totales_por_moneda(periodos)

    datos = {
        "generado": datetime.now(timezone.utc).isoformat(),
        "cliente_id": cliente_id,
        "granularidad": granularidad,
        "moneda_principal": totales[0]["moneda"] if totales else None,
        "totales": totales,
        "periodos": periodos,
        "categorias_egreso": top_categorias(cliente_id, "egreso", limite=None, **argumentos),
        "categorias_ingreso": top_categorias(cliente_id, "ingreso", limite=None, **argumentos),
        "anomalias": detectar_anomalias(cliente_id, **argumentos),
        "para_revision": movimientos_para_revision(cliente_id, **argumentos),
        "movimientos": _ordenar_por_fecha_desc(movimientos),
        "resumen_texto": None,
    }

    if incluir_texto:
        # El texto es un extra: si Groq falla, el dashboard funciona igual con
        # las cifras, que es lo que de verdad importa.
        try:
            from Resumen.resumen import generar_resumen

            datos["resumen_texto"], _ = generar_resumen(cliente_id, granularidad, db_path=db_path)
        except Exception as error:
            warnings.warn(f"No se pudo generar el resumen en texto: {type(error).__name__}: {error}")

    return datos


def exportar_dashboard(cliente_id, ruta=None, granularidad="mes", incluir_texto=True, db_path=None):
    """Escribe el JSON del dashboard y devuelve (ruta, datos)."""
    ruta = Path(ruta) if ruta else RUTA_POR_DEFECTO
    datos = construir_datos_dashboard(cliente_id, granularidad, incluir_texto, db_path)

    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    return ruta, datos
