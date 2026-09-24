import pytest
from Constantes.casos_prueba import CASOS_PRUEBA


@pytest.fixture(scope="session")
def resultados():
    """Ejecuta los 5 casos una sola vez y comparte el DataFrame con todos los tests."""
    # Import diferido: así los tests sin LLM (-m "not llm") no necesitan GROQ_API_KEY.
    from Evaluacion.evaluacion import ejecutar_casos
    return ejecutar_casos(CASOS_PRUEBA())
