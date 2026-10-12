"""
Lecturas en lenguaje natural de cada vista del estado de cuenta.

Las cifras salen de SQL (Exportacion); aquí el modelo solo las redacta. Cada
lectura se guarda con una huella de las cifras con que se escribió: mientras
esas cifras no cambien sigue vigente, y no hay que volver a llamar a Groq.
"""
import hashlib
import json

from Almacenamiento.almacenamiento import DB_PATH, guardar_lectura, leer_lecturas
from Modelos.consultas_llm import consulta_llm_texto
from Prompts import principales_prompts, prompts_secundarios

# Las descripciones completas no aportan a la lectura y alargan el prompt; se
# recortan, lo que también acota la superficie de inyección.
LIMITE_DESCRIPCION = 120
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def huella(vista):
    """Cambia si y solo si cambian las cifras de la vista."""
    contenido = json.dumps(vista, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(contenido.encode("utf-8")).hexdigest()[:16]


def nombre_periodo(periodo):
    if periodo == "todo":
        return "todo el periodo registrado"
    anio, _, mes = periodo.partition("-")
    return f"{MESES[int(mes) - 1]} de {anio}" if mes else anio


def _recortar(texto):
    if isinstance(texto, str) and len(texto) > LIMITE_DESCRIPCION:
        return texto[:LIMITE_DESCRIPCION] + "..."
    return texto


def metricas_para_lectura(vista, revision):
    """Lo que recibe el modelo: la vista y los casos pendientes de ese periodo."""
    periodo = vista["periodo"]

    def del_periodo(fecha):
        return periodo == "todo" or (fecha or "")[:len(periodo)] == periodo

    anomalias = [{**a, "descripcion": _recortar(a.get("descripcion"))} for a in vista["anomalias"]]
    pendientes = [
        {"fecha": e["movimiento"]["fecha"], "descripcion": _recortar(e["movimiento"]["descripcion"]),
         "monto": e["movimiento"]["monto"], "moneda": e["movimiento"]["moneda"],
         "motivos": e["motivos"], "repeticiones": e["repeticiones"]}
        for e in revision.get("pendientes", []) if del_periodo(e["movimiento"]["fecha"])
    ]
    return {**vista, "alcance": nombre_periodo(periodo), "anomalias": anomalias, "para_revision": pendientes}


def redactar(metricas, max_tokens=3000):
    texto = consulta_llm_texto(
        prompts_secundarios.PROMPT_GENERAR_RESUMEN(json.dumps(metricas, ensure_ascii=False, indent=2)),
        principales_prompts.PROMPT_RESUMEN_FINANCIERO(),
        max_tokens,
    )
    if not texto:
        raise ValueError("El modelo devolvió una lectura vacía.")
    return texto


def lectura(cliente_id, periodo, vista, revision, forzar=False, db_path=None):
    """
    La lectura de un periodo, como {"texto", "vigente"}.

    La primera vez se redacta y se guarda. Después se devuelve la guardada, con
    "vigente" en falso si las cifras cambiaron desde que se escribió. Solo se
    vuelve a llamar a Groq si se pide expresamente con forzar: así revisar un
    movimiento nunca cuesta una llamada.
    """
    db_path = db_path or DB_PATH
    actual = huella(vista)
    guardada = leer_lecturas(cliente_id, db_path).get(periodo)
    if guardada and not forzar:
        return {"texto": guardada["texto"], "vigente": guardada["huella"] == actual}

    texto = redactar(metricas_para_lectura(vista, revision))
    guardar_lectura(cliente_id, periodo, actual, texto, db_path)
    return {"texto": texto, "vigente": True}


def lecturas_guardadas(cliente_id, vistas, db_path=None):
    """Las lecturas guardadas de las vistas existentes, indicando si siguen vigentes."""
    return {
        periodo: {"texto": guardada["texto"], "vigente": guardada["huella"] == huella(vistas[periodo])}
        for periodo, guardada in leer_lecturas(cliente_id, db_path or DB_PATH).items()
        if periodo in vistas
    }
