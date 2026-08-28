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

<!-- MAKERS_REVIEW_2026_08_27_START -->
## Revision docente - 2026-08-27

### Lo que vimos

- Hay avance moviendo parte del flujo a script y agregando requirements/setup.
- El proyecto parece orientado a clasificacion/anonimizacion financiera.
- Todavia falta ordenar configuracion, prompts, validacion y evidencia.
- Las API keys y configuracion deben vivir fuera del codigo.
- El aporte individual debe quedar mas claro por commits y ramas.

### Reto de hoy

Hagan una validacion minima de movimiento financiero:

1. Definir campos esperados: monto, moneda, fecha, categoria, descripcion.
2. Rechazar monto vacio, moneda invalida, fecha ambigua o categoria no permitida.
3. Registrar 5 casos en vals/results.md.

### Tarea obligatoria: diagrama de arquitectura

Crear docs/arquitectura.md con un diagrama Mermaid que muestre:

`mermaid
flowchart LR
  DocumentoOTexto --> Preprocesamiento
  Preprocesamiento --> Modelo
  Modelo --> MovimientoEstructurado
  MovimientoEstructurado --> ValidadorMovimiento
  ValidadorMovimiento --> SalidaAnonimizada
  Evals --> ValidadorMovimiento
`

El diagrama debe mostrar donde se anonimiza, donde se llama al modelo y donde se valida.

### Criterio de aceptacion

No queremos mas codigo sin contrato. Queremos una salida financiera minima que se pueda revisar.
<!-- MAKERS_REVIEW_2026_08_27_END -->

