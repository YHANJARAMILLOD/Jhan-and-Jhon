"""Construye PDFs mínimos para pruebas, sin depender de ninguna librería."""


def _escapar(texto):
    return texto.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def crear_pdf(lineas, margen_vertical=None):
    """
    PDF de una página con las líneas dadas, en Helvetica. Sin cifrar.

    margen_vertical: texto girado 90° en el margen izquierdo, a la altura de
    las líneas, como la razón social de los extractos de NuBank.
    """
    contenido = "BT /F1 10 Tf 40 780 Td 14 TL " + " ".join(
        "({}) '".format(_escapar(l)) for l in lineas
    ) + " ET"
    if margen_vertical:
        contenido += f" q 0 1 -1 0 25 690 cm BT /F1 6 Tf 0 0 Td ({_escapar(margen_vertical)}) Tj ET Q"
    flujo = contenido.encode("latin-1")
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(flujo) + flujo + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    salida = bytearray(b"%PDF-1.4\n")
    posiciones = []
    for i, cuerpo in enumerate(objetos, start=1):
        posiciones.append(len(salida))
        salida += b"%d 0 obj\n" % i + cuerpo + b"\nendobj\n"
    inicio_xref = len(salida)
    salida += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objetos) + 1)
    for posicion in posiciones:
        salida += b"%010d 00000 n \n" % posicion
    salida += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objetos) + 1, inicio_xref)
    return bytes(salida)
