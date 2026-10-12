"""
Lectura de los archivos que sube el titular: texto en cualquier codificación
habitual y, más adelante, PDF de extractos bancarios.

Devuelve siempre pares (número de línea, texto). El número forma parte del id
estable de cada movimiento, así que leer el mismo archivo da los mismos ids.
"""
import codecs
import io
import re
from datetime import date


class ArchivoIlegible(ValueError):
    """El archivo no se puede convertir en líneas de transacciones."""


# Orden de prueba. UTF-8 primero porque es estricto: si un archivo decodifica
# como UTF-8, casi seguro lo es. Windows-1252 cubre lo que exporta Excel en
# Windows. Latin-1 nunca falla y queda de último recurso.
_CODIFICACIONES = ("utf-8", "cp1252", "latin-1")


def decodificar(contenido):
    """
    Texto de un archivo sin importar su codificación.

    Una codificación mal adivinada estropearía una tilde, nunca un monto: los
    dígitos y los separadores son iguales en todas. Por eso la cadena simple es
    suficiente y no hace falta una librería de detección.
    """
    if contenido.startswith(codecs.BOM_UTF8):
        return contenido[len(codecs.BOM_UTF8):].decode("utf-8", errors="replace")
    if contenido.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return contenido.decode("utf-16", errors="replace")
    for codificacion in _CODIFICACIONES:
        try:
            return contenido.decode(codificacion)
        except UnicodeDecodeError:
            continue
    return contenido.decode("latin-1")


# Un número con aspecto de monto: 45.900, 1,500, 2500000, 120.000,00
_MONTO = re.compile(r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?|\d{4,}|\d+[.,]\d{1,2}")


def _lineas_de_texto(texto, exigir_monto):
    lineas = []
    for numero, linea in enumerate(texto.splitlines(), start=1):
        limpia = linea.strip()
        if not limpia or limpia.startswith("#"):
            continue
        # En un CSV, una fila sin ningún número con aspecto de monto es el
        # encabezado o una línea de relleno: mandarla al modelo solo costaría
        # una llamada para descubrir que no es un movimiento.
        if exigir_monto and not _MONTO.search(limpia):
            continue
        lineas.append((numero, limpia))
    return lineas


def leer_lineas(nombre, contenido):
    """
    Pares (número de línea, texto) de un archivo subido.

    Lanza ArchivoIlegible con un mensaje que se le puede mostrar al titular.
    """
    if not contenido:
        raise ArchivoIlegible(f"'{nombre}' está vacío.")
    if contenido.startswith(b"%PDF-"):
        raise ArchivoIlegible(f"'{nombre}' es un PDF: usa leer_extracto, que acepta la contraseña.")

    texto = decodificar(contenido)
    # Un binario que no es texto deja muchos caracteres de control.
    controles = sum(1 for c in texto[:2000] if ord(c) < 32 and c not in "\r\n\t")
    if controles > 20:
        raise ArchivoIlegible(f"'{nombre}' no parece un archivo de texto. Se esperan .txt, .csv o .pdf.")

    return _lineas_de_texto(texto, exigir_monto=nombre.lower().endswith(".csv"))


# ───────────────────────── PDF ─────────────────────────

_MESES_CORTOS = r"(?:ene|feb|mar|abr|may|jun|jul|ago|sep|set|oct|nov|dic)[a-z]*\.?"
# Fechas como aparecen en los extractos: 05/10/2026, 05-10-26, 2026-10-05,
# "05 oct", "05 OCT 2026", "oct 05".
_FECHA = re.compile(
    rf"\b\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}}\b"
    rf"|\b\d{{4}}-\d{{2}}-\d{{2}}\b"
    rf"|\b\d{{1,2}}\s+{_MESES_CORTOS}(?:\s+\d{{2,4}})?\b"
    rf"|\b{_MESES_CORTOS}\s+\d{{1,2}}\b",
    re.IGNORECASE,
)


def es_fila_de_movimiento(linea):
    """
    Una fila de un extracto trae fecha y monto. Encabezados, pies de página,
    totales y números de página casi nunca tienen las dos cosas, y así no
    llegan al modelo: cada línea que se le manda cuesta segundos.
    """
    return bool(_FECHA.search(linea)) and bool(_MONTO.search(_FECHA.sub(" ", linea)))


_NUMERO_MES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8,
               "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12}
# "02 NOV" o "NOV 02" sin año detrás. Una cifra que sigue con punto o coma es
# un monto ("02 NOV 145.300,00"), no un año.
_FECHA_SIN_ANIO = re.compile(
    rf"\b(?:\d{{1,2}}\s+(?P<mes1>{_MESES_CORTOS})|(?P<mes2>{_MESES_CORTOS})\s+\d{{1,2}})"
    rf"(?!\s*\d{{2,4}}(?![\d.,]))",
    re.IGNORECASE,
)
# Solo cuenta un año que acompaña a un mes ("JUN 2025", "noviembre de 2026") o
# que forma parte de una fecha (30/06/2025). Un "2000" suelto era el final del
# teléfono de atención de NuBank y anulaba el año real.
_ANIO = re.compile(
    rf"\b{_MESES_CORTOS}\s+(?:de\s+|del\s+)?(20\d{{2}})\b|\b\d{{1,2}}[/-]\d{{1,2}}[/-](20\d{{2}})\b",
    re.IGNORECASE,
)


# El gravamen a los movimientos financieros (4x1000) que los extractos
# colombianos cobran, y a veces devuelven, en una línea aparte debajo de cada
# movimiento, sin fecha propia.
ES_GMF = re.compile(r"4\s?x\s?1\.?000|\bGMF\b|gravamen (?:a los |de )?movimientos financieros", re.IGNORECASE)
_DINERO_CON_SIGNO = re.compile(r"[+-]\s?\$\s?\d")
_FECHA_AL_INICIO = re.compile(
    rf"^(?:\d{{1,2}}\s+{_MESES_CORTOS}(?:\s+20\d{{2}}\b)?|\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}}\b|\d{{4}}-\d{{2}}-\d{{2}}\b)",
    re.IGNORECASE,
)
_FECHA_COMPLETA = re.compile(
    rf"^(?:(?P<d1>\d{{1,2}})\s+(?P<mes>{_MESES_CORTOS})\s+(?P<a1>20\d{{2}})"
    rf"|(?P<d2>\d{{1,2}})/(?P<m2>\d{{1,2}})/(?P<a2>20\d{{2}})"
    rf"|(?P<a3>20\d{{2}})-(?P<m3>\d{{2}})-(?P<d3>\d{{2}}))\b",
    re.IGNORECASE,
)


def fecha_iso(fila):
    """
    La fecha con que empieza una fila, como YYYY-MM-DD, o None si no empieza
    con una fecha completa e inequívoca ("05 jun 2025", "05/06/2025",
    "2025-06-05"). Las fechas con año de dos dígitos o en orden mes/día no se
    adivinan.
    """
    m = _FECHA_COMPLETA.match(fila.strip())
    if not m:
        return None
    if m.group("d1"):
        anio, mes, dia = int(m.group("a1")), _NUMERO_MES[m.group("mes")[:3].lower()], int(m.group("d1"))
    elif m.group("d2"):
        anio, mes, dia = int(m.group("a2")), int(m.group("m2")), int(m.group("d2"))
    else:
        anio, mes, dia = int(m.group("a3")), int(m.group("m3")), int(m.group("d3"))
    try:
        return date(anio, mes, dia).isoformat()
    except ValueError:
        return None


def completar_anio(filas, texto):
    """
    Agrega el año a las fechas de fila que no lo traen ("02 NOV").

    Los extractos ponen el año una sola vez, en el encabezado ("Periodo:
    noviembre 2026"). Sin él, el modelo lo inventaba y el movimiento caía en
    otro mes. El año se toma de las líneas que no son filas, y solo si va
    junto a un mes o dentro de una fecha; si el periodo
    cruza el fin de año (dic 2025 - ene 2026), los meses de julio en adelante
    van con el primer año y el resto con el segundo. Si no hay un año claro,
    las filas quedan como están.
    """
    filas_texto = {texto_fila for _, texto_fila in filas}
    anios = sorted({
        int(a or b) for linea in texto.splitlines() if linea.strip() not in filas_texto
        for a, b in _ANIO.findall(linea)
    })
    if len(anios) == 1:
        def anio_de(mes):
            return anios[0]
    elif len(anios) == 2 and anios[1] == anios[0] + 1:
        def anio_de(mes):
            return anios[0] if mes >= 7 else anios[1]
    else:
        return filas

    def con_anio(coincidencia):
        mes = (coincidencia.group("mes1") or coincidencia.group("mes2"))[:3].lower()
        return f"{coincidencia.group(0)} {anio_de(_NUMERO_MES[mes])}"

    return [(numero, _FECHA_SIN_ANIO.sub(con_anio, texto_fila, count=1)) for numero, texto_fila in filas]


def _horizontal(objeto):
    """
    Descarta el texto girado. Los extractos de NuBank llevan la razón social en
    vertical en el margen, y sus letras sueltas se colaban entre las filas
    ("a 05 jun ...") o las partían. pdfplumber marca esos caracteres como
    verticales; la matriz de transformación es la que dice que están girados.
    """
    if objeto.get("object_type") != "char":
        return True
    _, b, c, *_ = objeto["matrix"]
    return abs(b) < 0.01 and abs(c) < 0.01


def _filas_del_pdf(texto):
    """
    Las filas con fecha y monto, más las del 4x1000.

    La línea del 4x1000 no trae fecha: es la del movimiento que va justo
    encima, así que se le antepone. Solo si va justo debajo de una fila con
    fecha: el total del 4x1000 del resumen (primera página) no va debajo de
    ninguna, y así no se suma dos veces.
    """
    filas, fecha_anterior = [], None
    for numero, linea in enumerate(texto.splitlines(), start=1):
        linea = linea.strip()
        if es_fila_de_movimiento(linea):
            filas.append((numero, linea))
            inicio = _FECHA_AL_INICIO.match(linea)
            fecha_anterior = inicio.group(0) if inicio else None
            continue
        if fecha_anterior and ES_GMF.search(linea) and _DINERO_CON_SIGNO.search(linea):
            filas.append((numero, f"{fecha_anterior} {linea}"))
        fecha_anterior = None
    return filas


def leer_pdf(nombre, contenido, contrasena=None):
    """
    Filas de movimiento de un PDF, como pares (número de línea, texto).

    La contraseña se usa solo para abrir el archivo en memoria: no se guarda ni
    se registra en ninguna parte.
    """
    import pdfplumber
    from pdfminer.pdfdocument import PDFPasswordIncorrect

    try:
        with pdfplumber.open(io.BytesIO(contenido), password=contrasena or "") as pdf:
            texto = "\n".join((pagina.filter(_horizontal).extract_text() or "") for pagina in pdf.pages)
    except PDFPasswordIncorrect:
        if contrasena:
            raise ArchivoIlegible(f"La contraseña de '{nombre}' no es correcta.") from None
        raise ArchivoIlegible(
            f"'{nombre}' está protegido con contraseña. Escríbela junto al archivo "
            f"(en los extractos colombianos suele ser el número de documento)."
        ) from None
    except Exception:
        raise ArchivoIlegible(f"No se pudo leer '{nombre}' como PDF. Puede estar dañado.") from None

    if not texto.strip():
        raise ArchivoIlegible(
            f"'{nombre}' parece un documento escaneado: no tiene texto que leer. "
            f"Descarga el extracto digital desde la aplicación o la web de tu banco."
        )

    filas = _filas_del_pdf(texto)
    if not filas:
        raise ArchivoIlegible(
            f"En '{nombre}' no se encontró ninguna fila con fecha y monto. "
            f"Puede que el formato de este banco todavía no esté soportado."
        )
    return completar_anio(filas, texto)


def leer_extracto(nombre, contenido, contrasena=None):
    """Lee un archivo subido, sea texto, CSV o PDF. Devuelve (filas, tipo)."""
    if contenido.startswith(b"%PDF-"):
        return leer_pdf(nombre, contenido, contrasena), "pdf"
    tipo = "csv" if nombre.lower().endswith(".csv") else "texto"
    return leer_lineas(nombre, contenido), tipo
