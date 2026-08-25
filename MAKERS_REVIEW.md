# Makers Review

## Que encontramos

- El proyecto propone anonimizar y clasificar movimientos financieros personales.
- El avance nuevo mueve parte del flujo a `Makers/jhonyjhan.py`.
- El script combina Ollama local y Groq, pero todavia no separa configuracion, prompts y ejecucion.
- El riesgo central es financiero: montos inventados, categorias incorrectas, datos sensibles expuestos o movimientos no financieros clasificados como reales.
- La validacion actual se queda corta para comprobar schema, consistencia contable y manejo seguro de API keys.

## Mejora aplicada

Integre la rama `origin/Jhoneyker` y actualice el review para apuntar al nuevo script `Makers/jhonyjhan.py`.

La mejora docente anterior se mantiene: `evals/financial_email_eval_cases.csv` y `evals/README.md` con casos de happy path, input incompleto, duplicados, prompt injection y formato ambiguo.

## Por que importa

En un workflow financiero, el modelo puede interpretar lenguaje, pero el sistema debe verificar reglas deterministicas: schema, monto, moneda, fecha, categorias permitidas y datos faltantes. Un JSON valido con un monto mal extraido sigue siendo una falla de producto.

## Como probarlo

1. Instala dependencias desde `requirements.txt` o `Makers/requirements.txt`.
2. Revisa que las API keys no queden hardcodeadas.
3. Ejecuta `Makers/jhonyjhan.py` con un movimiento financiero sintetico.
4. Usa los inputs de `evals/financial_email_eval_cases.csv`.
5. Marca `PASS` o `FAIL` segun los guardrails del README de evals.

## Tu reto

1. Core: mover la API key de Groq a una variable de entorno y fallar con un mensaje claro si no existe.
2. Intermediate: crear `validate_financial_movement(output, input_text)` para schema, monto, moneda, fecha y categorias permitidas.
3. Advanced: separar `prompts.py`, `models.py` y `validators.py`, manteniendo un script simple de ejecucion.
