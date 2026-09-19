# Arquitectura

```mermaid
flowchart LR
    DocumentoOTexto --> Preprocesamiento
    Preprocesamiento --> Modelo
    Modelo --> MovimientoEstructurado
    MovimientoEstructurado --> ValidadorMovimiento
    ValidadorMovimiento --> SalidaAnonimizada
    Evals --> ValidadorMovimiento
```
