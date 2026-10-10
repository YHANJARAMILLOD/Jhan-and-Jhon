import json
import re
import warnings
from Constantes.Principales_constantes import TAMANO_LOTE
from Prompts import principales_prompts, prompts_secundarios
from Modelos.consultas_llm import extraer_movimiento, consulta_llm
from Validaciones.validaciones import (
    marcar_formato_ambiguo, marcar_inyeccion, normalizar_motivos, resolver_ambiguedad_cop, validar_revision,
    validate_financial_movement,
)
from Anonimizacion.anonimizacion import anonimizar_movimiento
from Recuperacion.recuperacion import recuperar_ejemplos, formatear_ejemplos
from Seguridad.inyeccion import detectar_inyeccion, sanear


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
        resolver_ambiguedad_cop(analisis, texto)
        marcar_formato_ambiguo(analisis, texto)
        # Va después de la regla COP: una línea con inyección nunca debe
        # quedar sin marca, aunque su monto sea inequívoco.
        marcar_inyeccion(analisis, texto)
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


# ───────────────────────── Lotes ─────────────────────────


TAMANO_LOTE = TAMANO_LOTE()
_CIFRA = re.compile(r"\d[\d.,]*\d|\d")


def _lecturas_de_cifras(texto):
    """Todos los valores que pueden representar las cifras de un texto."""
    valores = set()
    for cifra in _CIFRA.findall(texto):
        candidatos = {
            cifra.replace(".", "").replace(",", "."),   # 120.000,00 -> 120000.00
            cifra.replace(",", ""),                      # 1,234.56   -> 1234.56
            cifra.replace(".", "").replace(",", ""),     # 58.900     -> 58900
        }
        for candidato in candidatos:
            try:
                valores.add(round(float(candidato), 2))
            except ValueError:
                pass
    return valores


def _corresponde(movimiento, texto_fila):
    """El monto del movimiento aparece en la fila que se le asignó."""
    monto = (movimiento.get("movimiento") or {}).get("monto")
    return isinstance(monto, (int, float)) and round(float(monto), 2) in _lecturas_de_cifras(texto_fila)


def procesar_en_lotes(filas, usar_rag=True, tamano=TAMANO_LOTE):
    """
    Procesa filas de un extracto de varias en varias. Genera, por cada fila y
    en orden, (numero, texto, resultado, error): resultado tiene la forma de
    procesar_movimiento pero solo con los movimientos de esa fila.

    Un lote se acepta solo si sale un movimiento por fila, en orden, y el monto
    de cada uno aparece en su fila. Si no, ese lote se reprocesa fila por fila:
    más lento, pero nunca se asigna un movimiento a la fila equivocada.

    Las filas con texto de inyección van siempre solas: dentro de un lote, la
    marca de manipulación caería sobre todos los movimientos del lote.
    """
    def una_por_una(grupo):
        for numero, texto in grupo:
            try:
                yield numero, texto, procesar_movimiento(texto, usar_rag=usar_rag), None
            except Exception as error:
                yield numero, texto, None, error

    pendientes = []

    def vaciar():
        grupo = list(pendientes)
        pendientes.clear()
        if not grupo:
            return
        if len(grupo) == 1:
            yield from una_por_una(grupo)
            return
        try:
            resultado = procesar_movimiento("\n".join(t for _, t in grupo), usar_rag=usar_rag)
        except Exception:
            yield from una_por_una(grupo)
            return

        revisado = resultado["revisado"]
        if len(revisado) != len(grupo) or not all(
            m.get("es_movimiento_financiero") and _corresponde(m, texto)
            for m, (_, texto) in zip(revisado, grupo)
        ):
            yield from una_por_una(grupo)
            return

        for i, (numero, texto) in enumerate(grupo):
            yield numero, texto, {
                "revisado": [revisado[i]],
                "ejemplos_rag": [resultado["ejemplos_rag"][i]] if i < len(resultado["ejemplos_rag"]) else [[]],
                "categorias_extraidas": [resultado["categorias_extraidas"][i]],
                "anonimizado": [resultado["anonimizado"][i]],
            }, None

    for numero, texto in filas:
        if detectar_inyeccion(sanear(texto)):
            yield from vaciar()
            yield from una_por_una([(numero, texto)])
            continue
        pendientes.append((numero, texto))
        if len(pendientes) >= tamano:
            yield from vaciar()
    yield from vaciar()
