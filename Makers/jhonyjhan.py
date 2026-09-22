import os
import json
import re
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
import ollama
from groq import Groq
from Prompts import principales_prompts, prompts_secundarios
from Constantes.Principales_constantes import CATEGORIAS_PERMITIDAS, MONEDAS_PERMITIDAS, CAMPOS_MOVIMIENTO

CATEGORIAS_PERMITIDAS = CATEGORIAS_PERMITIDAS()
MONEDAS_PERMITIDAS = MONEDAS_PERMITIDAS()
CAMPOS_MOVIMIENTO = CAMPOS_MOVIMIENTO()

ruta_env = Path(__file__).resolve().parent.parent / '.env'
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

egreso = """
Banco: compra supermercado -50.000 COP, nomina +2.500.000 COP, transporte -8.000 COP.
"""

def extraer_movimiento(movimiento, prompt):
    respuesta = ollama.chat(
        model="qwen3:8b",
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


def validate_financial_movement(output, input_text):
    """Valida y devuelve una lista de movimientos financieros estructurados."""
    if not isinstance(input_text, str) or not input_text.strip():
        raise ValueError("El texto de entrada no puede estar vacío.")

    if isinstance(output, str):
        try:
            output = json.loads(output)
        except json.JSONDecodeError as error:
            raise ValueError("La salida no contiene JSON válido.") from error

    if not isinstance(output, list) or not output:
        raise ValueError("La salida debe ser una lista JSON no vacía.")

    errores = []
    for indice, item in enumerate(output):
        ubicacion = f"movimiento[{indice+1}]"
        if not isinstance(item, dict):
            errores.append(f"{ubicacion} debe ser un objeto JSON.")
            continue

        if set(item) != {"es_movimiento_financiero", "movimiento"}:
            errores.append(f"{ubicacion} tiene un schema inválido.")
            continue

        if item["es_movimiento_financiero"] is False:
            if item["movimiento"] is not None:
                errores.append(f"{ubicacion}.movimiento debe ser null.")
            continue

        datos = item["movimiento"]
        if item["es_movimiento_financiero"] is not True or not isinstance(datos, dict):
            errores.append(f"{ubicacion} debe representar un movimiento financiero.")
            continue

        if set(datos) != CAMPOS_MOVIMIENTO:
            errores.append(f"{ubicacion} tiene campos incompletos o desconocidos.")
            continue

        monto = datos["monto"]
        if isinstance(monto, bool) or not isinstance(monto, (int, float)) or monto <= 0:
            errores.append(f"{ubicacion}.monto debe ser un número positivo.")

        moneda = datos["moneda"]
        if not isinstance(moneda, str) or moneda.upper() not in MONEDAS_PERMITIDAS:
            errores.append(f"{ubicacion}.moneda no es válida.")

        # fecha = datos["fecha"]
        # if (
        #     not isinstance(fecha, str)
        #     or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha)
        # ):
        #     errores.append(f"{ubicacion}.fecha debe usar el formato YYYY-MM-DD.")
        # else:
        #     try:
        #         datetime.strptime(fecha, "%Y-%m-%d")
        #     except ValueError:
        #         errores.append(f"{ubicacion}.fecha no es una fecha válida.")

        if datos["categoria"] not in CATEGORIAS_PERMITIDAS:
            errores.append(f"{ubicacion}.categoria no está permitida.")

        if not isinstance(datos["descripcion"], str) or not datos["descripcion"].strip():
            errores.append(f"{ubicacion}.descripcion no puede estar vacía.")

    if errores:
        raise ValueError("Salida financiera inválida: " + " ".join(errores))

    return output

def anonimizar_nombre(nombre):
    """Conserva las primeras 3 letras y reemplaza el resto por asteriscos."""
    if not nombre:
        return None

    nombre = str(nombre)

    if len(nombre) <= 3:
        return nombre

    return nombre[:3] + "*" * (len(nombre) - 3)


def anonimizar_movimiento(movimiento):
    """
    Anonimiza un movimiento financiero sin utilizar IA.

    - Anonimiza nombre_remitente y nombre_destinatario.
    - No financiero: devuelve el JSON sin modificaciones.
    """
    
    if isinstance(movimiento, str):
        movimiento = json.loads(movimiento)

    if isinstance(movimiento, list):
        return [anonimizar_movimiento(item) for item in movimiento]

    if not isinstance(movimiento, dict):
        raise TypeError(
            "El movimiento debe ser un objeto JSON o una lista de objetos JSON."
        )

    if not movimiento.get("es_movimiento_financiero", False):
        return movimiento

    datos = movimiento.get("movimiento")

    if not datos:
        return movimiento

    datos["nombre_remitente"] = anonimizar_nombre(
        datos.get("nombre_remitente")
    )
    datos["nombre_destinatario"] = anonimizar_nombre(
        datos.get("nombre_destinatario")
    )
    return movimiento

prompt_extraer_movimiento = principales_prompts.PROMPT_EXTRAER_MOVIMIENTO()
analisis = extraer_movimiento(movimiento=egreso, prompt=prompt_extraer_movimiento)
validate_financial_movement(analisis, egreso)
anonimizado = anonimizar_movimiento(analisis)

print(json.dumps(analisis, ensure_ascii=False, indent=2))
print(json.dumps(anonimizado, ensure_ascii=False, indent=2))

def consulta_llm(prompt1,prompt2, max_tokens=1000):
    response = usuario.chat.completions.create(
        model="openai/gpt-oss-120b",
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
prompt = prompts_secundarios.PROMPT_CORREGIR_CATEGORIA(json.dumps(anonimizado, ensure_ascii=False, indent=2))
prompt_revisor = principales_prompts.PROMPT_REVISAR_CATEGORIA()
revisado = consulta_llm(prompt, prompt_revisor)
validate_financial_movement(revisado, egreso)
print(json.dumps(revisado, ensure_ascii=False, indent=2))