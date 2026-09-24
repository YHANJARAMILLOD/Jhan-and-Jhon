import json
import warnings
from Prompts import principales_prompts, prompts_secundarios
from Modelos.consultas_llm import extraer_movimiento, consulta_llm
from Validaciones.validaciones import validate_financial_movement, validar_revision, normalizar_motivos
from Anonimizacion.anonimizacion import anonimizar_movimiento
from Recuperacion.recuperacion import recuperar_ejemplos, formatear_ejemplos


def obtener_ejemplos_rag(anonimizado):
    """
    Recupera ejemplos parecidos para el revisor. El RAG es un apoyo: si falla
    (Ollama apagado, modelo de embeddings no descargado...) se avisa y el
    flujo continúa sin ejemplos.
    """
    try:
        return recuperar_ejemplos(anonimizado)
    except Exception as error:
        warnings.warn(f"RAG no disponible, se revisa sin ejemplos: {type(error).__name__}: {error}")
        return [[] for _ in anonimizado]


def procesar_movimiento(texto, usar_rag=True):
    """
    Ejecuta el flujo completo sobre un texto: extracción (Ollama), validación,
    anonimización, recuperación de ejemplos (RAG), revisión de categoría
    (Groq) y validación de la revisión.

    Devuelve un diccionario con el resultado de cada etapa. Si alguna
    validación falla, se propaga el ValueError indicando la etapa
    ([extraccion] o [revision]).
    """
    try:
        analisis = extraer_movimiento(movimiento=texto, prompt=principales_prompts.PROMPT_EXTRAER_MOVIMIENTO())
        # El extractor a veces inventa motivos: se normalizan antes de validar
        # para no descartar el movimiento completo por eso.
        normalizar_motivos(analisis)
        validate_financial_movement(analisis, texto)
    except ValueError as error:
        raise ValueError(f"[extraccion] {error}") from error

    categorias_extraidas = [
        (item["movimiento"] or {}).get("categoria") for item in analisis
    ]
    anonimizado = anonimizar_movimiento(analisis)
    ejemplos_rag = obtener_ejemplos_rag(anonimizado) if usar_rag else [[] for _ in anonimizado]

    prompt = prompts_secundarios.PROMPT_CORREGIR_CATEGORIA(
        json.dumps(anonimizado, ensure_ascii=False, indent=2),
        formatear_ejemplos(ejemplos_rag),
    )
    try:
        revisado = consulta_llm(prompt, principales_prompts.PROMPT_REVISAR_CATEGORIA())
        validate_financial_movement(revisado, texto)
        validar_revision(anonimizado, revisado)
    except ValueError as error:
        raise ValueError(f"[revision] {error}") from error

    return {
        "categorias_extraidas": categorias_extraidas,
        "anonimizado": anonimizado,
        "ejemplos_rag": ejemplos_rag,
        "revisado": revisado,
    }
