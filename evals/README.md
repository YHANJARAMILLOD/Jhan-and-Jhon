# Evals de resumen financiero por correo

El flujo trabaja con movimientos financieros extraidos de correos. El riesgo principal no es solo responder JSON: es inventar montos, duplicar transacciones o generar totales inconsistentes.

## Como usarlos

1. Abre `Sesión_8_Use_case-2.ipynb`.
2. Ejecuta hasta definir `run_prototype`.
3. Prueba cada input de `financial_email_eval_cases.csv`.
4. Marca `PASS` solo si:
   - no inventa montos ni fechas;
   - conserva el schema esperado;
   - los totales cuadran;
   - los casos ambiguos o riesgosos piden revision humana.

## Siguiente validacion sugerida

Implementar `validate_financial_summary(output, input_text)` para revisar:
- `total_ingresos >= 0`;
- `total_egresos >= 0`;
- sumas por categoria consistentes;
- fuentes de correos presentes;
- posibles duplicados;
- revision humana ante ambiguedad o datos incompletos.
