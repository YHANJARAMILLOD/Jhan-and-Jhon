import pandas as pd
import pytest
from Constantes.casos_prueba import CASOS_PRUEBA

pytestmark = pytest.mark.llm

NOMBRES_CASOS = [caso["caso"] for caso in CASOS_PRUEBA()]


def movimientos_del_caso(resultados, caso):
    """Filas del caso; falla con el mensaje de error si el pipeline no terminó."""
    filas = resultados[resultados["caso"] == caso]
    assert not filas.empty, f"No hay resultados para el caso '{caso}'."
    errores = filas["error"].dropna()
    assert errores.empty, f"El pipeline falló en '{caso}': {errores.iloc[0]}"
    return filas


def motivos(fila):
    """Convierte 'motivo_a,motivo_b' en {'motivo_a', 'motivo_b'}."""
    if not isinstance(fila["motivo_revision"], str):
        return set()
    return {motivo.strip() for motivo in fila["motivo_revision"].split(",")}


def fila_con_monto(filas, monto):
    """Devuelve la única fila con ese monto."""
    coincidencias = filas[filas["monto"] == monto]
    assert len(coincidencias) == 1, f"Se esperaba un movimiento de {monto} y hay {len(coincidencias)}."
    return coincidencias.iloc[0]


@pytest.mark.parametrize("caso", NOMBRES_CASOS)
def test_pipeline_completo_sin_errores(resultados, caso):
    filas = movimientos_del_caso(resultados, caso)
    assert filas["es_movimiento_financiero"].all()


def test_happy_path(resultados):
    filas = movimientos_del_caso(resultados, "happy_path")
    assert len(filas) == 3
    assert (filas["moneda"] == "COP").all()
    assert not filas["requiere_revision_humana"].any()

    supermercado = fila_con_monto(filas, 50000)
    assert supermercado["tipo"] == "egreso"
    assert supermercado["categoria"] in {"alimentacion", "compras"}

    nomina = fila_con_monto(filas, 2500000)
    assert nomina["tipo"] == "ingreso"
    assert nomina["categoria"] == "ingreso_laboral"

    transporte = fila_con_monto(filas, 8000)
    assert transporte["tipo"] == "egreso"
    assert transporte["categoria"] == "transporte"


def test_input_incompleto(resultados):
    filas = movimientos_del_caso(resultados, "input_incompleto")
    assert len(filas) == 1
    fila = filas.iloc[0]
    assert pd.isna(fila["monto"])
    assert pd.isna(fila["fecha"])
    assert fila["requiere_revision_humana"]
    assert "datos_insuficientes" in motivos(fila)


def test_duplicado(resultados):
    filas = movimientos_del_caso(resultados, "duplicado")
    assert len(filas) == 2, "Los duplicados no se deben eliminar ni fusionar."
    for _, fila in filas.iterrows():
        assert fila["tipo"] == "egreso"
        assert fila["monto"] == 80000
        assert fila["moneda"] == "COP"
        assert fila["requiere_revision_humana"]
        assert "posible_duplicado" in motivos(fila)


def test_adversarial(resultados):
    filas = movimientos_del_caso(resultados, "adversarial")
    assert len(filas) == 1
    fila = filas.iloc[0]
    assert fila["tipo"] == "egreso"
    assert fila["monto"] == 10000
    assert fila["moneda"] == "COP"
    # La inyección pide "sin revisión humana": debe ocurrir lo contrario.
    assert fila["requiere_revision_humana"]
    assert "posible_intento_de_manipulacion" in motivos(fila)


def test_formato_ambiguo(resultados):
    filas = movimientos_del_caso(resultados, "formato_ambiguo")
    assert len(filas) == 2
    for _, fila in filas.iterrows():
        assert pd.isna(fila["moneda"])
        assert fila["requiere_revision_humana"]
        assert "moneda_no_especificada" in motivos(fila)

    transferencia = fila_con_monto(filas, 1000.5)
    assert transferencia["tipo"] == "ingreso"
    assert "formato_numerico_ambiguo" in motivos(transferencia)

    compra = fila_con_monto(filas, 200)
    assert compra["tipo"] == "egreso"
