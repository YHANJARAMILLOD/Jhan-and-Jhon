import hashlib
import json
import numpy as np
import pytest
from Recuperacion.recuperacion import (
    agregar_ejemplo,
    cargar_indice,
    formatear_ejemplos,
    recuperar_ejemplos,
)


def embeddings_falsos(textos):
    """Bolsa de palabras con hashing: determinista y sin Ollama."""
    vectores = []
    for texto in textos:
        vector = np.zeros(256)
        for palabra in texto.lower().replace(":", " ").split():
            vector[int(hashlib.md5(palabra.encode()).hexdigest(), 16) % 256] += 1
        vectores.append(vector.tolist())
    return vectores


@pytest.fixture
def db(tmp_path):
    return tmp_path / "rag.db"


def movimiento(tipo, contraparte, descripcion, entidad=None):
    return {
        "es_movimiento_financiero": True,
        "movimiento": {
            "tipo": tipo,
            "nombre_remitente": contraparte if tipo == "ingreso" else "Jua*******",
            "nombre_destinatario": contraparte if tipo == "egreso" else "Jua*******",
            "entidad": entidad,
            "descripcion": descripcion,
        },
    }


def test_recupera_ejemplo_de_la_misma_contraparte(db):
    (ejemplos,) = recuperar_ejemplos(
        [movimiento("egreso", "Netflix", "Suscripción mensual Netflix")],
        umbral=0.3, db_path=db, funcion_embeddings=embeddings_falsos,
    )
    assert ejemplos, "Debe recuperar al menos un ejemplo."
    assert ejemplos[0]["contraparte"] == "Netflix"
    assert ejemplos[0]["categoria"] == "entretenimiento"


def test_respeta_el_tipo_y_k(db):
    (ejemplos,) = recuperar_ejemplos(
        [movimiento("ingreso", None, "Pago de nómina")],
        k=2, umbral=0.0, db_path=db, funcion_embeddings=embeddings_falsos,
    )
    assert len(ejemplos) == 2
    assert all(ejemplo["tipo"] == "ingreso" for ejemplo in ejemplos)
    assert ejemplos[0]["categoria"] == "ingreso_laboral"


def test_umbral_alto_no_devuelve_nada(db):
    resultado = recuperar_ejemplos(
        [movimiento("egreso", "Netflix", "Suscripción mensual Netflix"),
         {"es_movimiento_financiero": False, "movimiento": None}],
        umbral=1.01, db_path=db, funcion_embeddings=embeddings_falsos,
    )
    assert resultado == [[], []]
    assert formatear_ejemplos(resultado) is None


def test_formatear_agrupa_por_movimiento():
    texto = formatear_ejemplos([[], [{"categoria": "transporte"}]])
    assert json.loads(texto) == [{"movimiento": 2, "ejemplos": [{"categoria": "transporte"}]}]


def test_agregar_ejemplo_anonimiza_y_se_recupera(db):
    datos = {
        "tipo": "egreso",
        "nombre_remitente": "Juan Pérez",
        "nombre_destinatario": "Merqueo",
        "entidad": None,
        "descripcion": "Pedido de mercado de Juan Pérez en Merqueo",
    }
    agregar_ejemplo(datos, "compras", db_path=db)

    ejemplos, matriz = cargar_indice(db, funcion_embeddings=embeddings_falsos)
    nuevo = [e for e in ejemplos if e["origen"] == "humano"]
    assert len(nuevo) == 1
    assert nuevo[0]["contraparte"] == "Merqueo"
    assert "Juan" not in nuevo[0]["descripcion"]
    assert matriz.shape[0] == len(ejemplos)

    (recuperados,) = recuperar_ejemplos(
        [movimiento("egreso", "Merqueo", "Pedido de mercado en Merqueo")],
        umbral=0.3, db_path=db, funcion_embeddings=embeddings_falsos,
    )
    assert recuperados[0]["contraparte"] == "Merqueo"
    assert recuperados[0]["categoria"] == "compras"


def test_agregar_ejemplo_valida_categoria(db):
    with pytest.raises(ValueError):
        agregar_ejemplo({"tipo": "egreso", "descripcion": "x"}, "inventada", db_path=db)
    with pytest.raises(ValueError):
        agregar_ejemplo({"tipo": "egreso", "descripcion": "x"}, "ingreso_laboral", db_path=db)
