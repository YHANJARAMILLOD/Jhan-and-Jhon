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