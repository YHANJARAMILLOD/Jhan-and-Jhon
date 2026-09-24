import os
import json
from dotenv import load_dotenv
from pathlib import Path
import ollama
from groq import Groq
from Constantes.Principales_constantes import MODELO_EXTRACCION, MODELO_REVISION

MODELO_EXTRACCION = MODELO_EXTRACCION()
MODELO_REVISION = MODELO_REVISION()

ruta_env = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(dotenv_path=ruta_env)
api_key = os.getenv("GROQ_API_KEY")

# 3. Verifica que la clave realmente se haya cargado
if not api_key:
    raise ValueError(
        "❌ Error: La variable de entorno no está configurada. "
        "Asegúrate de agregarla a tu archivo .env."
    )

# 4. Inicializa tu cliente de Groq (tu "usuario") usando la variable en lugar del texto fijo
usuario = Groq(api_key=api_key)

def extraer_movimiento(movimiento, prompt):
    respuesta = ollama.chat(
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
        options={
            "temperature": 0
        }
    )

    contenido = respuesta["message"]["content"].strip()
    movimientos = json.loads(contenido)

    if not isinstance(movimientos, list):
        raise ValueError("El modelo debe devolver una lista JSON de movimientos.")

    return movimientos


def consulta_llm(prompt1,prompt2, max_tokens=1000):
    response = usuario.chat.completions.create(
        model=MODELO_REVISION,
        max_tokens=max_tokens,
        temperature=0,
        messages=[
            {"role": "system", "content": prompt2},
            {"role": "user", "content": prompt1}
        ],
    )
    contenido = response.choices[0].message.content.strip()
    movimientos = json.loads(contenido)

    if not isinstance(movimientos, list):
        raise ValueError("El revisor debe devolver una lista JSON de movimientos.")

    return movimientos


def consulta_llm_texto(prompt1, prompt2, max_tokens=1000):
    """
    Igual que consulta_llm pero devuelve el texto tal cual, sin parsear JSON.

    Se usa para la redacción del resumen, donde la salida esperada es prosa.
    La temperatura sigue en 0: el resumen debe ser estable entre ejecuciones.
    """
    response = usuario.chat.completions.create(
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
