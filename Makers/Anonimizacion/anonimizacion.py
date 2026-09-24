import copy
import json
import re


def anonimizar_nombre(nombre):
    """Conserva las primeras 3 letras y reemplaza el resto por asteriscos."""
    if not nombre:
        return None

    nombre = str(nombre)

    if len(nombre) <= 3:
        return nombre

    return nombre[:3] + "*" * (len(nombre) - 3)


def anonimizar_descripcion(descripcion, nombres):
    """
    Enmascara en la descripción los nombres de remitente y destinatario.

    Primero reemplaza el nombre completo y luego cada palabra del nombre de
    más de 3 letras, para cubrir menciones parciales ("Pago a Juan" cuando
    el remitente es "Juan Pérez"). No distingue mayúsculas de minúsculas.
    """
    if not descripcion:
        return descripcion

    fragmentos = set()
    for nombre in nombres:
        if not nombre:
            continue
        nombre = str(nombre).strip()
        fragmentos.add(nombre)
        fragmentos.update(palabra for palabra in nombre.split() if len(palabra) > 3)

    # Los fragmentos más largos primero para que el nombre completo no quede
    # partido por el reemplazo de una de sus palabras.
    for fragmento in sorted(fragmentos, key=len, reverse=True):
        if len(fragmento) <= 3:
            continue
        patron = re.compile(rf"(?<!\w){re.escape(fragmento)}(?!\w)", re.IGNORECASE)
        descripcion = patron.sub(lambda m: anonimizar_nombre(m.group(0)), descripcion)

    return descripcion


def nombres_a_anonimizar(datos):
    """
    Decide qué nombres pertenecen al cliente y, por tanto, se anonimizan.

    - Egreso: el cliente es quien envía el dinero (remitente). El
      destinatario es la contraparte (comercio, empresa o persona a la que
      se paga) y se conserva, porque es la mejor evidencia para la categoría.
    - Ingreso: el cliente es quien recibe (destinatario). El remitente es la
      contraparte (empleador, persona que transfiere) y se conserva.
    - Tipo desconocido: se anonimizan ambos por precaución.
    """
    tipo = datos.get("tipo")
    if tipo == "egreso":
        return ("nombre_remitente",)
    if tipo == "ingreso":
        return ("nombre_destinatario",)
    return ("nombre_remitente", "nombre_destinatario")


def anonimizar_movimiento(movimiento):
    """
    Anonimiza un movimiento financiero sin utilizar IA.

    - Anonimiza el nombre del cliente (ver nombres_a_anonimizar) y lo
      enmascara también dentro de la descripción.
    - La contraparte del movimiento se conserva sin anonimizar.
    - No financiero: devuelve el JSON sin modificaciones.

    Trabaja sobre una copia: el movimiento recibido no se modifica.
    """

    if isinstance(movimiento, str):
        movimiento = json.loads(movimiento)
    else:
        movimiento = copy.deepcopy(movimiento)

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

    campos = nombres_a_anonimizar(datos)

    datos["descripcion"] = anonimizar_descripcion(
        datos.get("descripcion"), [datos.get(campo) for campo in campos]
    )
    for campo in campos:
        datos[campo] = anonimizar_nombre(datos.get(campo))
    return movimiento
