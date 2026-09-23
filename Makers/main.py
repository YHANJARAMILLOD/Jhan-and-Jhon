import json
from Prompts import principales_prompts, prompts_secundarios
from Modelos.consultas_llm import extraer_movimiento, consulta_llm
from Validaciones.validaciones import validate_financial_movement, validar_revision
from Anonimizacion.anonimizacion import anonimizar_movimiento

egreso = """
Banco: compra supermercado -50.000 COP, nomina +2.500.000 COP, transporte -8.000 COP.
"""

if __name__ == "__main__":
    prompt_extraer_movimiento = principales_prompts.PROMPT_EXTRAER_MOVIMIENTO()
    analisis = extraer_movimiento(movimiento=egreso, prompt=prompt_extraer_movimiento)
    validate_financial_movement(analisis, egreso)
    anonimizado = anonimizar_movimiento(analisis)
    prompt = prompts_secundarios.PROMPT_CORREGIR_CATEGORIA(json.dumps(anonimizado, ensure_ascii=False, indent=2))
    prompt_revisor = principales_prompts.PROMPT_REVISAR_CATEGORIA()
    revisado = consulta_llm(prompt, prompt_revisor)
    validate_financial_movement(revisado, egreso)
    validar_revision(anonimizado, revisado)
    print(json.dumps(revisado, ensure_ascii=False, indent=2))
