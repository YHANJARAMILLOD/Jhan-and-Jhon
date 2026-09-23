from pathlib import Path
import pandas as pd
from Constantes.casos_prueba import CASOS_PRUEBA
from Evaluacion.evaluacion import ejecutar_casos

RUTA_RESULTADOS = Path(__file__).resolve().parent.parent / "datos" / "resultados_casos.csv"

if __name__ == "__main__":
    resultados = ejecutar_casos(CASOS_PRUEBA())

    RUTA_RESULTADOS.parent.mkdir(parents=True, exist_ok=True)
    resultados.to_csv(RUTA_RESULTADOS, index=False, encoding="utf-8-sig")

    with pd.option_context("display.max_columns", None, "display.width", 250):
        print(resultados.drop(columns=["texto"]))
    print(f"\nResultados guardados en: {RUTA_RESULTADOS}")
