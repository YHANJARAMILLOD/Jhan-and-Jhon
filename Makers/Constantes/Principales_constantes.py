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
}