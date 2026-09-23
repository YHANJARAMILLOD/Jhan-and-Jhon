import pandas as pd
from Pipeline.pipeline import procesar_movimiento
from Constantes.Principales_constantes import COLUMNAS_RESULTADOS

COLUMNAS_RESULTADOS = COLUMNAS_RESULTADOS()


def ejecutar_casos(casos):
    """
    Procesa cada caso con el pipeline completo y devuelve un DataFrame con
    una fila por movimiento detectado.

    Si un caso falla (validación, JSON inválido, error de conexión...), no
    se detiene la ejecución: se agrega una fila con la columna "error"
    para que el fallo quede registrado y los demás casos se sigan procesando.
    """
    filas = []
    for caso in casos:
        base = {"caso": caso["caso"], "texto": caso["texto"]}
        try:
            resultado = procesar_movimiento(caso["texto"])
        except Exception as error:
            filas.append({**base, "error": f"{type(error).__name__}: {error}"})
            continue

        elementos = zip(resultado["revisado"], resultado["categorias_extraidas"])
        for indice, (item, categoria_extraida) in enumerate(elementos, start=1):
            filas.append({
                **base,
                "indice": indice,
                "es_movimiento_financiero": item["es_movimiento_financiero"],
                **(item["movimiento"] or {}),
                "categoria_extraida": categoria_extraida,
                "error": None,
            })

    return pd.DataFrame(filas, columns=COLUMNAS_RESULTADOS)
