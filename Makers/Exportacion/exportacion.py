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
import os
import tempfile
import warnings
from datetime import datetime, timezone
from pathlib import Path

from Agregacion.agregacion import (
    PERIODO_SIN_FECHA,
    detectar_anomalias,
    resumen_por_periodo,
    top_categorias,
)
from Almacenamiento.almacenamiento import obtener_movimientos_cliente
from Revision.revision import elementos_revision

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


VISTA_TODO = "todo"


def _insumos(cliente_id, granularidad, db_path):
    """Lo que comparten todas las vistas. Se consulta una sola vez."""
    argumentos = {"db_path": db_path} if db_path else {}
    periodos = resumen_por_periodo(cliente_id, granularidad, **argumentos)
    if not periodos:
        raise ValueError(f"El cliente '{cliente_id}' no tiene movimientos guardados.")
    totales = _totales_por_moneda(periodos)
    return {
        "periodos": periodos,
        "movimientos": obtener_movimientos_cliente(cliente_id, **argumentos),
        "anomalias": detectar_anomalias(cliente_id, **argumentos),
        "moneda_principal": totales[0]["moneda"] if totales else None,
        "argumentos": argumentos,
    }


def periodos_de_vista(insumos):
    """Periodos con fecha, en orden: cada uno es una vista que se puede elegir."""
    return sorted({p["periodo"] for p in insumos["periodos"] if p["periodo"] != PERIODO_SIN_FECHA})


def _vista(cliente_id, periodo, insumos):
    """
    Cifras de una vista: todo el histórico o un periodo concreto.

    Las anomalías se detectan contra todo el historial del titular y después se
    filtran por periodo: un gasto es inusual respecto a su comportamiento
    habitual, no solo respecto al de ese mes.
    """
    todo = periodo == VISTA_TODO

    def del_periodo(fecha):
        return todo or (fecha or "")[:len(periodo)] == periodo

    periodos = insumos["periodos"] if todo else [p for p in insumos["periodos"] if p["periodo"] == periodo]
    movimientos = [m for m in insumos["movimientos"] if del_periodo(m["fecha"])]
    vigentes = [m for m in movimientos if m.get("decision") != "descartado"]
    moneda = insumos["moneda_principal"]
    filtro = None if todo else periodo

    return {
        "periodo": periodo,
        "totales": _totales_por_moneda(periodos),
        "periodos": periodos,
        # Completas, sin top 5: si se recortan, los porcentajes no suman 100.
        "categorias_egreso": top_categorias(cliente_id, "egreso", None, periodo=filtro, **insumos["argumentos"]),
        "categorias_ingreso": top_categorias(cliente_id, "ingreso", None, periodo=filtro, **insumos["argumentos"]),
        "anomalias": [a for a in insumos["anomalias"] if del_periodo(a["fecha"])],
        # Los totales solo suman movimientos con monto: contar desde ellos daba
        # un número distinto al de la tabla.
        "total_movimientos": len(vigentes),
        "movimientos_descartados": len(movimientos) - len(vigentes),
        "movimientos_sin_monto": sum(1 for m in vigentes if m["monto"] is None),
        # Suman en el total histórico pero no caen en ningún mes.
        "movimientos_sin_fecha": sum(1 for m in vigentes if m["fecha"] is None and m["monto"] is not None),
        # Cuánto de lo sumado sigue sin confirmar. Se cuenta, pero se avisa.
        "monto_pendiente": sum(
            m["monto"] for m in vigentes
            if m.get("pendiente") and m["monto"] is not None and m["moneda"] == moneda
        ),
    }


def construir_vista(cliente_id, periodo, granularidad="mes", db_path=None):
    """Una sola vista. La usa el endpoint de lecturas."""
    insumos = _insumos(cliente_id, granularidad, db_path)
    if periodo != VISTA_TODO and periodo not in periodos_de_vista(insumos):
        raise ValueError("Ese periodo no tiene movimientos.")
    return _vista(cliente_id, periodo, insumos)


def construir_datos_dashboard(cliente_id, granularidad="mes", incluir_texto=True, db_path=None):
    """
    Arma el diccionario que consume el dashboard: una vista por periodo y otra
    con todo el histórico. Cambiar de periodo en el navegador es elegir otra
    vista ya calculada: no hace falta pedir nada al servidor ni a Groq.

    Con incluir_texto se vuelve a redactar la lectura del histórico completo.
    Sin él, se usan las lecturas guardadas, marcando las que ya no corresponden
    a las cifras actuales.
    """
    insumos = _insumos(cliente_id, granularidad, db_path)
    periodos = periodos_de_vista(insumos)
    vistas = {VISTA_TODO: _vista(cliente_id, VISTA_TODO, insumos)}
    for periodo in periodos:
        vistas[periodo] = _vista(cliente_id, periodo, insumos)
    revision = elementos_revision(cliente_id, **insumos["argumentos"])

    from Resumen.resumen import lectura, lecturas_guardadas

    if incluir_texto:
        # La lectura es un extra: si Groq falla, el dashboard funciona igual.
        try:
            lectura(cliente_id, VISTA_TODO, vistas[VISTA_TODO], revision, forzar=True, db_path=db_path)
        except Exception as error:
            warnings.warn(f"No se pudo redactar la lectura: {type(error).__name__}: {error}")

    return {
        "generado": datetime.now(timezone.utc).isoformat(),
        "cliente_id": cliente_id,
        "granularidad": granularidad,
        "moneda_principal": insumos["moneda_principal"],
        "periodos_disponibles": periodos,
        "vistas": vistas,
        # La revisión es una sola lista de pendientes, no se parte por mes: un
        # caso sin fecha, por ejemplo, no pertenece a ninguno.
        "revision": revision,
        # Incluye los descartados, para mostrarlos tachados en el libro.
        "movimientos": _ordenar_por_fecha_desc(insumos["movimientos"]),
        "lecturas": lecturas_guardadas(cliente_id, vistas, db_path),
    }


def exportar_dashboard(cliente_id, ruta=None, granularidad="mes", incluir_texto=True, db_path=None):
    """
    Escribe el JSON del dashboard y devuelve (ruta, datos).

    Se escribe a un temporal y se renombra: el servidor atiende varias
    peticiones a la vez y el navegador nunca debe leer un archivo a medias.
    """
    ruta = Path(ruta) if ruta else RUTA_POR_DEFECTO
    datos = construir_datos_dashboard(cliente_id, granularidad, incluir_texto, db_path)

    ruta.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporal = tempfile.mkstemp(dir=ruta.parent, prefix=".datos-", suffix=".json")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
            json.dump(datos, archivo, ensure_ascii=False, indent=2)
        os.replace(temporal, ruta)
    except BaseException:
        Path(temporal).unlink(missing_ok=True)
        raise
    return ruta, datos
