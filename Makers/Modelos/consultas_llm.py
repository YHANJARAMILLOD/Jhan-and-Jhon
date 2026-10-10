import os
import json
from dotenv import load_dotenv
from pathlib import Path
import ollama
from groq import Groq
from Constantes.Principales_constantes import (
    MODELO_EXTRACCION, MODELO_REVISION,
    OPCIONES_EXTRACCION, PENSAR_EN_EXTRACCION, TIMEOUT_OLLAMA,
)

MODELO_EXTRACCION = MODELO_EXTRACCION()
MODELO_REVISION = MODELO_REVISION()
OPCIONES_EXTRACCION = OPCIONES_EXTRACCION()
PENSAR_EN_EXTRACCION = PENSAR_EN_EXTRACCION()

# Cliente propio para poder fijar el timeout; ollama.chat() no lo expone.
ollama_cliente = ollama.Client(timeout=TIMEOUT_OLLAMA())

RUTA_ENV = Path(__file__).resolve().parent.parent.parent / '.env'
_groq = None


def cliente_groq():
    """
    Cliente de Groq, creado la primera vez que se necesita.

    Crearlo al importar obligaba a tener la clave incluso para abrir el
    dashboard, que no llama a Groq. Ahora el servidor arranca sin ella y solo
    fallan, con un mensaje claro, las operaciones que de verdad la usan.
    """
    global _groq
    if _groq is None:
        load_dotenv(dotenv_path=RUTA_ENV)
        clave = os.getenv("GROQ_API_KEY")
        if not clave:
            raise RuntimeError(
                "Falta GROQ_API_KEY. Agrégala al archivo .env de la raíz del proyecto."
            )
        _groq = Groq(api_key=clave)
    return _groq


def _anulable(tipo):
    return {"type": [tipo, "null"]}


# Forma de la respuesta del extractor. Ollama restringe la generación a este
# esquema: sin él, qwen3 a veces cerraba con "```" a mitad de un movimiento y
# el JSON quedaba cortado. Los valores permitidos los sigue revisando
# validate_financial_movement.
_CAMPOS = {
    "nombre_remitente": _anulable("string"), "tipo": _anulable("string"),
    "categoria": _anulable("string"), "monto": _anulable("number"),
    "moneda": _anulable("string"), "nombre_destinatario": _anulable("string"),
    "entidad": _anulable("string"), "fecha": _anulable("string"),
    "descripcion": _anulable("string"), "requiere_revision_humana": {"type": "boolean"},
    "motivo_revision": _anulable("string"),
}
ESQUEMA_EXTRACCION = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "es_movimiento_financiero": {"type": "boolean"},
            "movimiento": {"type": ["object", "null"], "properties": _CAMPOS, "required": list(_CAMPOS)},
        },
        "required": ["es_movimiento_financiero", "movimiento"],
    },
}


def extraer_movimiento(movimiento, prompt):
    respuesta = ollama_cliente.chat(
        model=MODELO_EXTRACCION,
        messages=[
            {
                "role": "system",
                "content": prompt
            },
            {
                "role": "user",
                "content": movimiento
            }
        ],
        think=PENSAR_EN_EXTRACCION,
        options=OPCIONES_EXTRACCION,
        format=ESQUEMA_EXTRACCION,
    )

    contenido = respuesta["message"]["content"].strip()
    # strict=False: el modelo a veces deja un salto de línea literal dentro de
    # una descripción, y eso no justifica perder el movimiento.
    movimientos = json.loads(contenido, strict=False)

    if not isinstance(movimientos, list):
        raise ValueError("El modelo debe devolver una lista JSON de movimientos.")

    return movimientos


def consulta_llm(prompt1, prompt2, max_tokens=4000):
    """
    Revisión de categorías. gpt-oss razona antes de responder y ese
    razonamiento consume max_tokens: con 1000 el JSON de un lote de 8
    movimientos salía cortado. reasoning_effort="low" basta para elegir una
    categoría de una lista cerrada y abarata la llamada.
    """
    response = cliente_groq().chat.completions.create(
        model=MODELO_REVISION,
        max_tokens=max_tokens,
        temperature=0,
        reasoning_effort="low",
        messages=[
            {"role": "system", "content": prompt2},
            {"role": "user", "content": prompt1}
        ],
    )
    eleccion = response.choices[0]
    if eleccion.finish_reason == "length":
        raise ValueError("La respuesta del revisor se cortó por el límite de tokens.")
    contenido = (eleccion.message.content or "").strip()
    movimientos = json.loads(contenido, strict=False)

    if not isinstance(movimientos, list):
        raise ValueError("El revisor debe devolver una lista JSON de movimientos.")

    return movimientos


def consulta_llm_texto(prompt1, prompt2, max_tokens=1000):
    """
    Igual que consulta_llm pero devuelve el texto tal cual, sin parsear JSON.

    Se usa para la redacción del resumen, donde la salida esperada es prosa.
    La temperatura sigue en 0: el resumen debe ser estable entre ejecuciones.
    """
    response = cliente_groq().chat.completions.create(
        model=MODELO_REVISION,
        max_tokens=max_tokens,
        temperature=0,
        messages=[
            {"role": "system", "content": prompt2},
            {"role": "user", "content": prompt1}
        ],
    )
    texto = response.choices[0].message.content.strip()

    if not texto:
        raise ValueError("El modelo devolvió un resumen vacío.")

    return texto


def consulta_groq(prompt_usuario, prompt_sistema, modelo, max_tokens=600,
                  json_mode=False, esfuerzo="low", timeout=30):
    """
    Llamada corta a Groq para el asistente.

    reasoning_effort="low": los modelos gpt-oss razonan antes de responder, y
    para reescribir una pregunta o redactar tres frases sobre cifras ya
    calculadas no hace falta más; sube la latencia y el consumo sin mejorar
    la respuesta. El timeout evita que una petición colgada bloquee al usuario.
    """
    argumentos = {
        "model": modelo,
        "max_tokens": max_tokens,
        "temperature": 0,
        "reasoning_effort": esfuerzo,
        "timeout": timeout,
        "messages": [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": prompt_usuario},
        ],
    }
    if json_mode:
        argumentos["response_format"] = {"type": "json_object"}

    respuesta = cliente_groq().chat.completions.create(**argumentos)
    return (respuesta.choices[0].message.content or "").strip()


def puntaje_inyeccion(texto, modelo, timeout=10):
    """
    Probabilidad (0 a 1) de que el texto sea una inyección de prompt, según
    Llama Prompt Guard. El modelo responde solo con el número.
    """
    respuesta = cliente_groq().chat.completions.create(
        model=modelo,
        timeout=timeout,
        messages=[{"role": "user", "content": texto}],
    )
    return float((respuesta.choices[0].message.content or "0").strip())
