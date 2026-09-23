# Gates Makers — revisión 2026-09-23

Referencia revisada: `origin/Jhoneyker`, integrada localmente en `makers/review`.

| Gate | Estado | Evidencia | Para cerrar |
|---|---|---|---|
| Arquitectura atribuible | PARCIAL | `docs/arquitectura.md`, principalmente atribuible a Jhoneyker. | Yhan debe aportar una decisión y ambos explicar límites local/cloud. |
| Uso de IA + evals | PARCIAL | Pipeline local + Groq y tests. No hay resultados versionados reproducibles. | Proveedor fake y reporte offline. |
| Jailbreak y privacidad | NO PASA | Hay validaciones, pero descripción y entidad pueden filtrar PII al cloud. | Threat model y casos de PII en todos los campos libres. |
| Mantenibilidad | PARCIAL | Módulos separados; `principales_prompts.py` supera 300 líneas. | Prompts versionados por función y sin código mezclado. |
| Producto ejecutable | PARCIAL | Pipeline/CLI, sin journey de usuario definido. | Elegir API B2B o app consumidor y demostrar un flujo. |
| Git profesional | PARCIAL | Ambos tienen commits. | Usar `dev/nombre`, limpiar artefactos y PR. |

No debe salir ningún texto libre al proveedor cloud antes de una política explícita de redacción y allowlist.
