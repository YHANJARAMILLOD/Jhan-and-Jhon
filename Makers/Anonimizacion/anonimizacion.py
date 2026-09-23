import json


def anonimizar_nombre(nombre):
    """Conserva las primeras 3 letras y reemplaza el resto por asteriscos."""
    if not nombre:
        return None

    nombre = str(nombre)

    if len(nombre) <= 3:
        return nombre

    return nombre[:3] + "*" * (len(nombre) - 3)


def anonimizar_movimiento(movimiento):
    """
    Anonimiza un movimiento financiero sin utilizar IA.

    - Anonimiza nombre_remitente y nombre_destinatario.
    - No financiero: devuelve el JSON sin modificaciones.
    """
    
    if isinstance(movimiento, str):
        movimiento = json.loads(movimiento)

    if isinstance(movimiento, list):
        return [anonimizar_movimiento(item) for item in movimiento]

    if not isinstance(movimiento, dict):
        raise TypeError(
            "El movimiento debe ser un objeto JSON o una lista de objetos JSON."
        )

    if not movimiento.get("es_movimiento_financiero", False):
        return movimiento

    datos = movimiento.get("movimiento")

    if not datos:
        return movimiento

    datos["nombre_remitente"] = anonimizar_nombre(
        datos.get("nombre_remitente")
    )
    datos["nombre_destinatario"] = anonimizar_nombre(
        datos.get("nombre_destinatario")
    )
    return movimiento
