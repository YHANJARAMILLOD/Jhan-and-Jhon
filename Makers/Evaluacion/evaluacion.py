import pandas as pd
from Pipeline.pipeline import procesar_movimiento
from Constantes.Principales_constantes import COLUMNAS_RESULTADOS

COLUMNAS_RESULTADOS = COLUMNAS_RESULTADOS()


def ejecutar_casos(casos, usar_rag=True):
    """
    Procesa cada caso con el pipeline completo y devuelve un DataFrame con
    una fila por movimiento detectado.

    Si un caso falla (validación, JSON inválido, error de conexión...), no
    se detiene la ejecución: se agrega una fila con la columna "error"
    para que el fallo quede registrado y los demás casos se sigan procesando.

    La columna "ejemplos_rag" indica cuántos ejemplos del RAG recibió el
    revisor para cada movimiento.
    """
    filas = []
    for caso in casos:
        base = {"caso": caso["caso"], "texto": caso["texto"]}
        try:
            resultado = procesar_movimiento(caso["texto"], usar_rag=usar_rag)
        except Exception as error:
            filas.append({**base, "error": f"{type(error).__name__}: {error}"})
            continue

        elementos = zip(resultado["revisado"], resultado["categorias_extraidas"], resultado["ejemplos_rag"])
        for indice, (item, categoria_extraida, ejemplos) in enumerate(elementos, start=1):
            filas.append({
                **base,
                "indice": indice,
                "es_movimiento_financiero": item["es_movimiento_financiero"],
                **(item["movimiento"] or {}),
                "categoria_extraida": categoria_extraida,
                "ejemplos_rag": len(ejemplos),
                "error": None,
            })

    return pd.DataFrame(filas, columns=COLUMNAS_RESULTADOS)
