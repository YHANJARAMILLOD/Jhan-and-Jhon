"""
Resumen en lenguaje natural del histórico de un cliente.

Las cifras las calcula Agregacion (SQL determinístico); aquí el LLM solo
redacta sobre ellas. Si el LLM falla, las métricas siguen disponibles: el
resumen es una capa de presentación, no la fuente de los números.
"""
import json

from Agregacion.agregacion import resumen_cliente
from Modelos.consultas_llm import consulta_llm_texto
from Prompts import principales_prompts, prompts_secundarios

# Las descripciones completas no aportan al resumen y alargan el prompt sin
# necesidad; se recortan para acotar también la superficie de inyección.
LIMITE_DESCRIPCION = 120


def _recortar_descripciones(metricas):
    for clave in ("anomalias", "para_revision"):
        for movimiento in metricas.get(clave, []):
            descripcion = movimiento.get("descripcion")
            if isinstance(descripcion, str) and len(descripcion) > LIMITE_DESCRIPCION:
                movimiento["descripcion"] = descripcion[:LIMITE_DESCRIPCION] + "..."
    return metricas


def generar_resumen(cliente_id, granularidad="mes", max_tokens=3000, db_path=None):
    """
    Devuelve (texto, metricas) para un cliente.

    `texto` es la redacción del LLM y `metricas` el diccionario con las cifras
    que se le entregaron, para poder contrastar lo que dice contra los datos.
    """
    metricas = (
        resumen_cliente(cliente_id, granularidad, db_path)
        if db_path
        else resumen_cliente(cliente_id, granularidad)
    )

    if not metricas["total_movimientos"]:
        raise ValueError(f"El cliente '{cliente_id}' no tiene movimientos guardados.")

    _recortar_descripciones(metricas)
    prompt = prompts_secundarios.PROMPT_GENERAR_RESUMEN(
        json.dumps(metricas, ensure_ascii=False, indent=2)
    )
    texto = consulta_llm_texto(
        prompt, principales_prompts.PROMPT_RESUMEN_FINANCIERO(), max_tokens
    )
    return texto, metricas
