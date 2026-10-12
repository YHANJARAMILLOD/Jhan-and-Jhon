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

def OPCIONES_EXTRACCION():
    """
    Opciones de la llamada a Ollama en la extracción.

    num_ctx: el modelo admite 40960 pero Ollama arranca en 4096. Con el
    system prompt completo, un texto largo y la respuesta, el contexto se
    desbordaba y Ollama descartaba tokens del propio prompt ("context
    shift"), dejando al modelo generando sin fin.

    num_predict: techo duro. Si la generación se desboca, la respuesta se
    corta, el JSON queda inválido y la línea falla rápido en vez de colgar.
    """
    return {"temperature": 0, "num_ctx": 8192, "num_predict": 2048}


def PENSAR_EN_EXTRACCION():
    # qwen3 razona en voz alta por defecto y eso multiplicaba por tres los
    # tokens generados sin mejorar la extracción. Se apaga.
    return False


def TIMEOUT_OLLAMA():
    # Segundos. Una petición colgada no debe bloquear el lote entero.
    return 300


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


# ───────────────────── Asistente de preguntas ─────────────────────

def MODELO_ASISTENTE():
    # El 20b basta para reescribir preguntas y redactar respuestas cortas a
    # partir de cifras ya calculadas, y responde bastante más rápido que el 120b.
    return "openai/gpt-oss-20b"


def MODELO_GUARDIA():
    # Clasificador dedicado a detectar inyección de prompt. Devuelve una
    # probabilidad, no texto libre.
    return "meta-llama/llama-prompt-guard-2-86m"


def UMBRAL_GUARDIA():
    # Probado: preguntas legítimas ~0.0004, ataques directos 0.90-0.9996.
    return 0.5


def MAX_LARGO_PREGUNTA():
    # Una pregunta financiera real es corta; los textos largos son el vehículo
    # habitual de las inyecciones.
    return 300


def MAX_TURNOS_HISTORIAL():
    return 3


def MAX_PREGUNTAS_POR_MINUTO():
    # Protege la cuota de Groq de un bucle o de un abuso desde el navegador.
    return 20


def PREGUNTAS_SUGERIDAS():
    """
    Preguntas genéricas, válidas para cualquier titular con movimientos.
    Su intención ya se conoce, así que se responden sin pasar por el enrutador.
    """
    return [
        "¿En qué categoría gasto más dinero?",
        "¿Cómo ha cambiado mi balance de un mes a otro?",
        "¿Hay algún movimiento fuera de lo normal que deba revisar?",
    ]


def TAMANO_LOTE():
    # Filas de un extracto (PDF o CSV) que se mandan juntas al extractor. Con
    # ~20 s por llamada, 100 filas pasan de ~33 min a unos 5. Más grande
    # alarga cada respuesta y sube el riesgo de que el modelo omita filas.
    return 8
