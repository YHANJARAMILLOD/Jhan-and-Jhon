import argparse
from pathlib import Path
import pandas as pd
from Constantes.casos_prueba import CASOS_PRUEBA
from Evaluacion.evaluacion import ejecutar_casos

CARPETA_DATOS = Path(__file__).resolve().parent.parent / "datos"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ejecuta los casos de prueba con el pipeline completo.")
    parser.add_argument("--sin-rag", action="store_true", help="Revisa la categoría sin ejemplos del RAG.")
    args = parser.parse_args()

    resultados = ejecutar_casos(CASOS_PRUEBA(), usar_rag=not args.sin_rag)

    nombre = "resultados_casos_sin_rag.csv" if args.sin_rag else "resultados_casos.csv"
    ruta_resultados = CARPETA_DATOS / nombre
    ruta_resultados.parent.mkdir(parents=True, exist_ok=True)
    resultados.to_csv(ruta_resultados, index=False, encoding="utf-8-sig")

    with pd.option_context("display.max_columns", None, "display.width", 250):
        print(resultados.drop(columns=["texto"]))
    print(f"\nResultados guardados en: {ruta_resultados}")
