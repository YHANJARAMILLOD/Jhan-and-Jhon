import json
from Prompts import principales_prompts, prompts_secundarios
from Modelos.consultas_llm import extraer_movimiento, consulta_llm
from Validaciones.validaciones import validate_financial_movement, validar_revision
from Anonimizacion.anonimizacion import anonimizar_movimiento


def procesar_movimiento(texto):
    """
    Ejecuta el flujo completo sobre un texto: extracción (Ollama), validación,
    anonimización, revisión de categoría (Groq) y validación de la revisión.

    Devuelve un diccionario con el resultado de cada etapa. Si alguna
    validación falla, se propaga el ValueError indicando la etapa
    ([extraccion] o [revision]).
    """
    try:
        analisis = extraer_movimiento(movimiento=texto, prompt=principales_prompts.PROMPT_EXTRAER_MOVIMIENTO())
        validate_financial_movement(analisis, texto)
    except ValueError as error:
        raise ValueError(f"[extraccion] {error}") from error

    categorias_extraidas = [
        (item["movimiento"] or {}).get("categoria") for item in analisis
    ]
    anonimizado = anonimizar_movimiento(analisis)

    prompt = prompts_secundarios.PROMPT_CORREGIR_CATEGORIA(json.dumps(anonimizado, ensure_ascii=False, indent=2))
    try:
        revisado = consulta_llm(prompt, principales_prompts.PROMPT_REVISAR_CATEGORIA())
        validate_financial_movement(revisado, texto)
        validar_revision(anonimizado, revisado)
    except ValueError as error:
        raise ValueError(f"[revision] {error}") from error

    return {
        "categorias_extraidas": categorias_extraidas,
        "anonimizado": anonimizado,
        "revisado": revisado,
    }
