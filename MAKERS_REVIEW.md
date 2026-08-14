# Makers Review

## Que encontramos

- El proyecto propone resumir correos financieros y extractos en ingresos/egresos categorizados.
- Usa Groq con `openai/gpt-oss-120b`.
- El notebook tiene salida JSON y algunos casos adversariales.
- El riesgo central es financiero: montos inventados, duplicados, fuentes vacias o totales inconsistentes.
- La validacion actual se queda corta para comprobar consistencia contable.

## Mejora aplicada

Agregue `evals/financial_email_eval_cases.csv` y `evals/README.md` con 5 casos: happy path, input incompleto, duplicados, prompt injection y formato ambiguo.

## Por que importa

En un workflow financiero, el modelo puede clasificar lenguaje, pero el sistema debe verificar aritmetica, duplicados y trazabilidad. Un JSON valido con un total incorrecto sigue siendo una falla de producto.

## Como probarlo

1. Abre `Sesión_8_Use_case-2.ipynb`.
2. Ejecuta hasta `run_prototype`.
3. Usa los inputs de `evals/financial_email_eval_cases.csv`.
4. Marca `PASS` o `FAIL` segun los guardrails del README.

## Tu reto

1. Core: ejecutar los 5 casos y completar `pass_fail`.
2. Intermediate: crear `validate_financial_summary(output, input_text)` para totales y duplicados.
3. Advanced: guardar cada resultado en `evals/results.csv` y comparar mejora antes/despues de cambiar el prompt o schema.
