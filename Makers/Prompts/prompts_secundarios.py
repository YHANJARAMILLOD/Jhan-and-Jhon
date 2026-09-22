def PROMPT_CORREGIR_CATEGORIA(json_movimiento):
    return f"""Revisa el siguiente movimiento financiero.

Determina si la categoría asignada es correcta teniendo en cuenta toda la información disponible. Si es un egreso, presta especial atención al nombre_remitente.

Si la categoría es incorrecta y existe evidencia suficiente, corrígela. Si es correcta o no existe suficiente información para cambiarla, mantenla.

No modifiques ningún otro campo.

Movimientos: {json_movimiento}"""