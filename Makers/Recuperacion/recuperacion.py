import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import ollama

from Anonimizacion.anonimizacion import anonimizar_movimiento
from Constantes.Principales_constantes import (
    CATEGORIAS_PERMITIDAS,
    MODELO_EMBEDDINGS,
    RAG_TOP_K,
    RAG_UMBRAL_SIMILITUD,
)
from Constantes.ejemplos_categorias import EJEMPLOS_CATEGORIAS

CATEGORIAS_PERMITIDAS = CATEGORIAS_PERMITIDAS()
MODELO_EMBEDDINGS = MODELO_EMBEDDINGS()
RAG_TOP_K = RAG_TOP_K()
RAG_UMBRAL_SIMILITUD = RAG_UMBRAL_SIMILITUD()

# Base propia del RAG, separada de datos/movimientos.db (Almacenamiento).
RAG_DB_PATH = Path(__file__).resolve().parent.parent.parent / "datos" / "rag_categorias.db"


def obtener_contraparte(datos):
    """
    Nombre de la contraparte, que es el que no se anonimiza: el destinatario
    en un egreso y el remitente en un ingreso. None si el tipo es desconocido.
    """
    tipo = datos.get("tipo")
    if tipo == "egreso":
        return datos.get("nombre_destinatario")
    if tipo == "ingreso":
        return datos.get("nombre_remitente")
    return None


def texto_para_embedding(tipo, contraparte, entidad, descripcion):
    """
    Texto que representa un movimiento en el índice y en las consultas.

    Sin etiquetas ("tipo:", "descripcion:"...): al ser iguales en todos los
    textos inflan la similitud entre movimientos que no se parecen. El tipo
    no se incluye porque ya se filtra en recuperar_ejemplos.
    """
    return " · ".join(parte for parte in (contraparte, entidad, descripcion) if parte)


def embeddings_ollama(textos, modelo=MODELO_EMBEDDINGS):
    """Calcula los embeddings en local con Ollama (no salen datos a la nube)."""
    respuesta = ollama.embed(model=modelo, input=textos)
    return respuesta["embeddings"]


def _normalizar(vectores):
    matriz = np.asarray(vectores, dtype=np.float32)
    normas = np.linalg.norm(matriz, axis=1, keepdims=True)
    normas[normas == 0] = 1
    return matriz / normas


def _generar_ejemplo_id(tipo, contraparte, entidad, descripcion):
    base = json.dumps(
        [tipo, contraparte, entidad, descripcion], ensure_ascii=False
    ).lower()
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _obtener_conexion(db_path):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conexion = sqlite3.connect(db_path)
    conexion.row_factory = sqlite3.Row
    return conexion


def inicializar_indice(db_path=RAG_DB_PATH):
    """
    Crea las tablas del RAG y carga los ejemplos semilla que falten.

    Los embeddings se guardan por modelo junto al texto que se usó: si se
    cambia MODELO_EMBEDDINGS o texto_para_embedding, se recalculan sin
    perder los ejemplos.
    """
    conexion = _obtener_conexion(db_path)
    conexion.executescript(
        """
        CREATE TABLE IF NOT EXISTS ejemplos (
            ejemplo_id TEXT PRIMARY KEY,
            tipo TEXT,
            contraparte TEXT,
            entidad TEXT,
            descripcion TEXT NOT NULL,
            categoria TEXT NOT NULL,
            origen TEXT NOT NULL,
            fecha_creacion TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS embeddings (
            ejemplo_id TEXT NOT NULL,
            modelo TEXT NOT NULL,
            texto TEXT NOT NULL,
            vector TEXT NOT NULL,
            PRIMARY KEY (ejemplo_id, modelo)
        );
        """
    )
    fecha = datetime.now(timezone.utc).isoformat()
    for ejemplo in EJEMPLOS_CATEGORIAS():
        campos = (ejemplo["tipo"], ejemplo["contraparte"], ejemplo["entidad"], ejemplo["descripcion"])
        # OR IGNORE: una corrección humana de un ejemplo semilla no se pisa.
        conexion.execute(
            "INSERT OR IGNORE INTO ejemplos VALUES (?, ?, ?, ?, ?, ?, 'semilla', ?)",
            (_generar_ejemplo_id(*campos), *campos, ejemplo["categoria"], fecha),
        )
    conexion.commit()
    conexion.close()


def agregar_ejemplo(datos, categoria, origen="humano", db_path=RAG_DB_PATH):
    """
    Agrega (o corrige) un ejemplo confirmado por una persona.

    `datos` es el diccionario "movimiento" de un elemento de la salida. Se
    anonimiza antes de guardarlo, así que el nombre del cliente nunca queda
    en la base del RAG. Si ya existía un ejemplo con el mismo contenido, se
    reemplaza su categoría.

    Solo deben agregarse movimientos cuya categoría se haya verificado: el
    revisor copia lo que encuentra aquí, incluidos los errores.
    """
    if categoria not in CATEGORIAS_PERMITIDAS:
        raise ValueError(f"Categoría no permitida: {categoria}.")
    if categoria == "ingreso_laboral" and datos.get("tipo") != "ingreso":
        raise ValueError("'ingreso_laboral' solo aplica a ingresos.")

    anonimo = anonimizar_movimiento(
        {"es_movimiento_financiero": True, "movimiento": datos}
    )["movimiento"]
    descripcion = anonimo.get("descripcion")
    if not isinstance(descripcion, str) or not descripcion.strip():
        raise ValueError("El ejemplo necesita una descripción.")

    campos = (anonimo.get("tipo"), obtener_contraparte(anonimo), anonimo.get("entidad"), descripcion)
    ejemplo_id = _generar_ejemplo_id(*campos)

    inicializar_indice(db_path)
    conexion = _obtener_conexion(db_path)
    conexion.execute(
        "INSERT OR REPLACE INTO ejemplos VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (ejemplo_id, *campos, categoria, origen, datetime.now(timezone.utc).isoformat()),
    )
    conexion.commit()
    conexion.close()
    return ejemplo_id


def cargar_indice(db_path=RAG_DB_PATH, modelo=MODELO_EMBEDDINGS, funcion_embeddings=None):
    """
    Devuelve (ejemplos, matriz) con los vectores normalizados. Calcula y
    guarda los embeddings que falten para el modelo indicado.
    """
    funcion_embeddings = funcion_embeddings or (lambda textos: embeddings_ollama(textos, modelo))
    inicializar_indice(db_path)
    conexion = _obtener_conexion(db_path)
    filas = [
        dict(fila)
        for fila in conexion.execute(
            """
            SELECT e.*, v.texto AS texto_embedding, v.vector FROM ejemplos e
            LEFT JOIN embeddings v ON v.ejemplo_id = e.ejemplo_id AND v.modelo = ?
            ORDER BY e.ejemplo_id
            """,
            (modelo,),
        )
    ]

    for fila in filas:
        fila["texto"] = texto_para_embedding(
            fila["tipo"], fila["contraparte"], fila["entidad"], fila["descripcion"]
        )
    faltantes = [fila for fila in filas if fila.pop("texto_embedding") != fila["texto"]]
    if faltantes:
        vectores = funcion_embeddings([fila["texto"] for fila in faltantes])
        for fila, vector in zip(faltantes, vectores):
            fila["vector"] = json.dumps([float(valor) for valor in vector])
            conexion.execute(
                "INSERT OR REPLACE INTO embeddings VALUES (?, ?, ?, ?)",
                (fila["ejemplo_id"], modelo, fila["texto"], fila["vector"]),
            )
        conexion.commit()
    conexion.close()

    if not filas:
        return [], np.empty((0, 0), dtype=np.float32)

    matriz = _normalizar([json.loads(fila.pop("vector")) for fila in filas])
    return filas, matriz


def recuperar_ejemplos(
    movimientos,
    k=RAG_TOP_K,
    umbral=RAG_UMBRAL_SIMILITUD,
    db_path=RAG_DB_PATH,
    modelo=MODELO_EMBEDDINGS,
    funcion_embeddings=None,
):
    """
    Busca, para cada movimiento (ya anonimizado), los ejemplos más parecidos.

    Devuelve una lista alineada con `movimientos`: en cada posición, hasta
    `k` ejemplos con similitud >= `umbral`, del mismo tipo que el movimiento
    cuando el tipo se conoce. Los elementos no financieros reciben [].
    """
    funcion_embeddings = funcion_embeddings or (lambda textos: embeddings_ollama(textos, modelo))
    resultado = [[] for _ in movimientos]

    consultas = {}
    for indice, item in enumerate(movimientos):
        datos = item.get("movimiento") if item.get("es_movimiento_financiero") else None
        if datos:
            consultas[indice] = datos
    if not consultas:
        return resultado

    ejemplos, matriz = cargar_indice(db_path, modelo, funcion_embeddings)
    if not ejemplos:
        return resultado

    textos = [
        texto_para_embedding(d.get("tipo"), obtener_contraparte(d), d.get("entidad"), d.get("descripcion"))
        for d in consultas.values()
    ]
    similitudes = _normalizar(funcion_embeddings(textos)) @ matriz.T

    for (indice, datos), fila_similitud in zip(consultas.items(), similitudes):
        for posicion in np.argsort(-fila_similitud):
            ejemplo = ejemplos[posicion]
            similitud = float(fila_similitud[posicion])
            if similitud < umbral or len(resultado[indice]) >= k:
                break
            if datos.get("tipo") and ejemplo["tipo"] and ejemplo["tipo"] != datos.get("tipo"):
                continue
            resultado[indice].append({
                "tipo": ejemplo["tipo"],
                "contraparte": ejemplo["contraparte"],
                "entidad": ejemplo["entidad"],
                "descripcion": ejemplo["descripcion"],
                "categoria": ejemplo["categoria"],
                "similitud": round(similitud, 3),
            })

    return resultado


def formatear_ejemplos(ejemplos_por_movimiento):
    """JSON de ejemplos agrupados por número de movimiento, o None si no hay."""
    grupos = [
        {"movimiento": indice, "ejemplos": ejemplos}
        for indice, ejemplos in enumerate(ejemplos_por_movimiento, start=1)
        if ejemplos
    ]
    if not grupos:
        return None
    return json.dumps(grupos, ensure_ascii=False, indent=2)
