import json
import re
import warnings
from datetime import datetime
from Constantes.Principales_constantes import CATEGORIAS_PERMITIDAS, MONEDAS_PERMITIDAS, CAMPOS_MOVIMIENTO, MOTIVOS_REVISION_PERMITIDOS, TIPOS_PERMITIDOS, CAMPOS_TEXTO_OPCIONAL

CATEGORIAS_PERMITIDAS = CATEGORIAS_PERMITIDAS()
MONEDAS_PERMITIDAS = MONEDAS_PERMITIDAS()
CAMPOS_MOVIMIENTO = CAMPOS_MOVIMIENTO()
MOTIVOS_REVISION_PERMITIDOS = MOTIVOS_REVISION_PERMITIDOS()
TIPOS_PERMITIDOS = TIPOS_PERMITIDOS()
CAMPOS_TEXTO_OPCIONAL = CAMPOS_TEXTO_OPCIONAL()


def normalizar_motivos(output, motivo_por_defecto="datos_insuficientes"):
    """
    Reemplaza los motivos de revisión inventados por uno permitido.

    El extractor ocasionalmente devuelve motivos fuera del conjunto permitido
    (se ha visto "fecha_en_el_futuro"), lo que invalidaba el extracto completo
    aunque el resto del movimiento fuera correcto. Se conserva la marca de
    revisión y se sustituye el motivo: marcar de más es preferible a descartar
    el movimiento.

    Modifica y devuelve `output`. Debe llamarse antes de validar.
    """
    if not isinstance(output, list):
        return output

    for item in output:
        if not isinstance(item, dict) or not item.get("es_movimiento_financiero"):
            continue

        datos = item.get("movimiento")
        if not isinstance(datos, dict):
            continue

        motivo = datos.get("motivo_revision")
        if not isinstance(motivo, str) or not motivo.strip():
            continue

        motivos = [m.strip() for m in motivo.split(",") if m.strip()]
        desconocidos = [m for m in motivos if m not in MOTIVOS_REVISION_PERMITIDOS]
        if not desconocidos:
            continue

        conservados = [m for m in motivos if m in MOTIVOS_REVISION_PERMITIDOS]
        if motivo_por_defecto not in conservados:
            conservados.append(motivo_por_defecto)

        datos["motivo_revision"] = ",".join(conservados)
        datos["requiere_revision_humana"] = True
        warnings.warn(
            f"Motivos de revisión no permitidos {desconocidos}: "
            f"se marca para revisión con '{motivo_por_defecto}'."
        )

    return output


def _validar_motivos(ubicacion, datos, errores):
    """Valida requiere_revision_humana / motivo_revision (reglas 5 y 26-32 del prompt)."""
    requiere = datos["requiere_revision_humana"]
    motivo = datos["motivo_revision"]

    if not isinstance(requiere, bool):
        errores.append(f"{ubicacion}.requiere_revision_humana debe ser booleano.")
        return set()

    if not requiere:
        if motivo is not None:
            errores.append(f"{ubicacion}.motivo_revision debe ser null si no requiere revisión.")
        return set()

    if not isinstance(motivo, str) or not motivo.strip():
        errores.append(f"{ubicacion}.motivo_revision es obligatorio si requiere revisión.")
        return set()

    motivos = [m.strip() for m in motivo.split(",")]
    desconocidos = [m for m in motivos if m not in MOTIVOS_REVISION_PERMITIDOS]
    if desconocidos:
        errores.append(f"{ubicacion}.motivo_revision tiene motivos no permitidos: {', '.join(desconocidos)}.")
    return set(motivos)


def validate_financial_movement(output, input_text):
    """
    Valida la lista de movimientos según el esquema definido en los prompts.

    Admite null en los campos que el prompt permite dejar vacíos, pero exige
    que esos casos vengan marcados para revisión humana con el motivo
    correspondiente (datos_insuficientes / moneda_no_especificada).
    """
    if not isinstance(input_text, str) or not input_text.strip():
        raise ValueError("El texto de entrada no puede estar vacío.")

    if isinstance(output, str):
        try:
            output = json.loads(output)
        except json.JSONDecodeError as error:
            raise ValueError("La salida no contiene JSON válido.") from error

    if not isinstance(output, list) or not output:
        raise ValueError("La salida debe ser una lista JSON no vacía.")

    errores = []
    for indice, item in enumerate(output):
        ubicacion = f"movimiento[{indice+1}]"
        if not isinstance(item, dict):
            errores.append(f"{ubicacion} debe ser un objeto JSON.")
            continue

        if set(item) != {"es_movimiento_financiero", "movimiento"}:
            errores.append(f"{ubicacion} tiene un schema inválido.")
            continue

        if item["es_movimiento_financiero"] is False:
            if item["movimiento"] is not None:
                errores.append(f"{ubicacion}.movimiento debe ser null.")
            continue

        datos = item["movimiento"]
        if item["es_movimiento_financiero"] is not True or not isinstance(datos, dict):
            errores.append(f"{ubicacion} debe representar un movimiento financiero.")
            continue

        if set(datos) != CAMPOS_MOVIMIENTO:
            faltantes = CAMPOS_MOVIMIENTO - set(datos)
            sobrantes = set(datos) - CAMPOS_MOVIMIENTO
            errores.append(
                f"{ubicacion} tiene campos inválidos "
                f"(faltantes: {sorted(faltantes)}, desconocidos: {sorted(sobrantes)})."
            )
            continue

        motivos = _validar_motivos(ubicacion, datos, errores)

        tipo = datos["tipo"]
        if tipo is not None and tipo not in TIPOS_PERMITIDOS:
            errores.append(f"{ubicacion}.tipo debe ser 'ingreso', 'egreso' o null.")

        categoria = datos["categoria"]
        if categoria is not None and categoria not in CATEGORIAS_PERMITIDAS:
            errores.append(f"{ubicacion}.categoria no está permitida.")
        if categoria == "ingreso_laboral" and tipo != "ingreso":
            errores.append(f"{ubicacion}.categoria 'ingreso_laboral' solo aplica a ingresos.")

        monto = datos["monto"]
        if monto is not None and (
            isinstance(monto, bool) or not isinstance(monto, (int, float)) or monto <= 0
        ):
            errores.append(f"{ubicacion}.monto debe ser un número positivo o null.")

        moneda = datos["moneda"]
        if moneda is not None and (
            not isinstance(moneda, str) or moneda.upper() not in MONEDAS_PERMITIDAS
        ):
            errores.append(f"{ubicacion}.moneda no es válida.")

        fecha = datos["fecha"]
        if fecha is not None:
            if not isinstance(fecha, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha):
                errores.append(f"{ubicacion}.fecha debe usar el formato YYYY-MM-DD o ser null.")
            else:
                try:
                    datetime.strptime(fecha, "%Y-%m-%d")
                except ValueError:
                    errores.append(f"{ubicacion}.fecha no es una fecha válida.")

        for campo in CAMPOS_TEXTO_OPCIONAL:
            if datos[campo] is not None and not isinstance(datos[campo], str):
                errores.append(f"{ubicacion}.{campo} debe ser texto o null.")

        if not isinstance(datos["descripcion"], str) or not datos["descripcion"].strip():
            errores.append(f"{ubicacion}.descripcion no puede estar vacía.")

        # Regla 28: si faltan datos esenciales debe marcarse datos_insuficientes.
        if (monto is None or tipo is None or categoria is None) and "datos_insuficientes" not in motivos:
            errores.append(
                f"{ubicacion} tiene tipo, categoría o monto en null sin motivo 'datos_insuficientes'."
            )

        # Regla 29: moneda null requiere moneda_no_especificada (o datos_insuficientes).
        if moneda is None and not motivos & {"moneda_no_especificada", "datos_insuficientes"}:
            errores.append(
                f"{ubicacion}.moneda es null sin motivo 'moneda_no_especificada'."
            )

    if errores:
        raise ValueError("Salida financiera inválida: " + " ".join(errores))

    return output


def validar_revision(original, revisado):
    """
    Comprueba que el revisor solo haya modificado "categoria" (reglas 14-16
    de PROMPT_REVISAR_CATEGORIA): mismos elementos, mismo orden y resto de
    campos idénticos.
    """
    if len(original) != len(revisado):
        raise ValueError(
            f"El revisor devolvió {len(revisado)} elementos y se esperaban {len(original)}."
        )

    errores = []
    for indice, (antes, despues) in enumerate(zip(original, revisado)):
        ubicacion = f"movimiento[{indice+1}]"
        if antes["es_movimiento_financiero"] != despues["es_movimiento_financiero"]:
            errores.append(f"{ubicacion}.es_movimiento_financiero fue modificado.")
            continue

        datos_antes = antes["movimiento"] or {}
        datos_despues = despues["movimiento"] or {}
        for campo in CAMPOS_MOVIMIENTO - {"categoria"}:
            if datos_antes.get(campo) != datos_despues.get(campo):
                errores.append(f"{ubicacion}.{campo} fue modificado por el revisor.")

    if errores:
        raise ValueError("Revisión inválida: " + " ".join(errores))

    return revisado
