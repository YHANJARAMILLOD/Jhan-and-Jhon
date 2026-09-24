def CATEGORIAS_PERMITIDAS():
    return {
    "alimentacion",
    "transporte",
    "entretenimiento",
    "vivienda",
    "salud",
    "educacion",
    "compras",
    "servicios",
    "transferencia_persona",
    "ingreso_laboral",
    "otros",
}

def MONEDAS_PERMITIDAS():
    return {"COP", "USD", "EUR", "MXN", "ARS", "CLP", "PEN", "BRL"}

def CAMPOS_MOVIMIENTO():
    return {
    "nombre_remitente",
    "tipo",
    "categoria",
    "monto",
    "moneda",
    "nombre_destinatario",
    "entidad",
    "fecha",
    "descripcion",
    "requiere_revision_humana",
    "motivo_revision",
}

def MOTIVOS_REVISION_PERMITIDOS():
    return {
    "posible_intento_de_manipulacion",
    "posible_duplicado",
    "datos_insuficientes",
    "moneda_no_especificada",
    "formato_numerico_ambiguo",
}

def TIPOS_PERMITIDOS():
    return {"ingreso", "egreso"}

def CAMPOS_TEXTO_OPCIONAL():
    return ("nombre_remitente", "nombre_destinatario", "entidad")

def MODELO_EXTRACCION():
    return "qwen3:8b"

def MODELO_REVISION():
    return "openai/gpt-oss-120b"

def MODELO_EMBEDDINGS():
    # Modelo multilingüe de Ollama para los embeddings del RAG.
    return "bge-m3"

def RAG_TOP_K():
    # Máximo de ejemplos recuperados por movimiento.
    return 3

def RAG_UMBRAL_SIMILITUD():
    # Similitud coseno mínima para que un ejemplo se envíe al revisor.
    return 0.65

def COLUMNAS_RESULTADOS():
    return [
    "caso",
    "texto",
    "indice",
    "es_movimiento_financiero",
    "nombre_remitente",
    "tipo",
    "categoria_extraida",
    "categoria",
    "monto",
    "moneda",
    "nombre_destinatario",
    "entidad",
    "fecha",
    "descripcion",
    "requiere_revision_humana",
    "motivo_revision",
    "ejemplos_rag",
    "error",
]
