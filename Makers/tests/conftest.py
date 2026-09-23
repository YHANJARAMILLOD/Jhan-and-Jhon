import pytest
from Constantes.casos_prueba import CASOS_PRUEBA
from Evaluacion.evaluacion import ejecutar_casos


@pytest.fixture(scope="session")
def resultados():
    """Ejecuta los 5 casos una sola vez y comparte el DataFrame con todos los tests."""
    return ejecutar_casos(CASOS_PRUEBA())
