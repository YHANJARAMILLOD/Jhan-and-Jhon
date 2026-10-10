"""Lectura de archivos: codificaciones habituales y archivos que no son texto."""
import codecs

import pytest

from Entrada.entrada import ArchivoIlegible, decodificar, leer_lineas

MUESTRA = "Compra en Éxito Poblado por 120.000 COP, cafetería Ñandú 8.500 COP"


@pytest.mark.parametrize("codificacion", ["utf-8", "utf-8-sig", "cp1252", "latin-1", "utf-16", "utf-16-be"])
def test_decodifica_las_codificaciones_habituales(codificacion):
    contenido = MUESTRA.encode(codificacion)
    if codificacion == "utf-16-be":
        contenido = codecs.BOM_UTF16_BE + contenido
    assert decodificar(contenido) == MUESTRA


def test_las_cifras_nunca_se_estropean():
    # Aunque se adivine mal la codificación, los montos quedan intactos.
    texto = decodificar("Nómina 2.800.000 COP".encode("cp1252"))
    assert "2.800.000" in texto


def test_txt_conserva_numeros_de_linea_y_salta_comentarios():
    contenido = "# encabezado\n\nPagué 45.900 a Netflix\nLínea sin monto\n".encode("utf-8")
    assert leer_lineas("extracto.txt", contenido) == [(3, "Pagué 45.900 a Netflix"), (4, "Línea sin monto")]


def test_csv_salta_filas_sin_monto():
    contenido = "Fecha;Descripción;Valor\n03/10/2026;Compra Éxito;-120.000\n".encode("cp1252")
    assert leer_lineas("mov.csv", contenido) == [(2, "03/10/2026;Compra Éxito;-120.000")]


@pytest.mark.parametrize("contenido,mensaje", [
    (b"", "vacío"),
    (bytes(range(32)) * 50, "texto"),
])
def test_archivos_ilegibles(contenido, mensaje):
    with pytest.raises(ArchivoIlegible, match=mensaje):
        leer_lineas("raro.bin", contenido)


# ───────────────────────── PDF ─────────────────────────

from pdf_minimo import crear_pdf  # noqa: E402

from Entrada import entrada  # noqa: E402
from Entrada.entrada import es_fila_de_movimiento, leer_extracto  # noqa: E402


@pytest.mark.parametrize("linea", [
    "05 OCT COMPRA EXITO POBLADO 120.000,00",
    "07/10/2026 PAGO CLARO 58.900",
    "2026-10-12 Netflix 45.900",
    "oct 15 Uber 18.400",
    "15-10-26 Transferencia 250.000",
])
def test_filas_de_movimiento(linea):
    assert es_fila_de_movimiento(linea)


@pytest.mark.parametrize("linea", [
    "EXTRACTO BANCARIO - OCTUBRE 2026",      # sin fecha completa ni monto
    "Fecha Descripción Valor",
    "Página 1 de 2",
    "Total del periodo 178.900",             # monto sin fecha
    "Fecha de corte: 05/10/2026",            # fecha sin monto
])
def test_lineas_que_no_son_movimientos(linea):
    assert not es_fila_de_movimiento(linea)


def test_pdf_solo_entrega_las_filas_de_movimiento():
    pdf = crear_pdf(["EXTRACTO OCTUBRE 2026", "Fecha Descripcion Valor",
                     "05 OCT COMPRA EXITO 120.000,00", "Pagina 1 de 2", "07/10/2026 PAGO CLARO 58.900"])
    filas, tipo = leer_extracto("nu.pdf", pdf)
    assert tipo == "pdf"
    assert [texto for _, texto in filas] == ["05 OCT 2026 COMPRA EXITO 120.000,00", "07/10/2026 PAGO CLARO 58.900"]


def test_pdf_escaneado():
    with pytest.raises(ArchivoIlegible, match="escaneado"):
        leer_extracto("escaneado.pdf", crear_pdf([]))


def test_pdf_sin_filas_reconocibles():
    with pytest.raises(ArchivoIlegible, match="formato"):
        leer_extracto("otro.pdf", crear_pdf(["Resumen anual", "Gracias por ser cliente"]))


def test_pdf_danado():
    with pytest.raises(ArchivoIlegible, match="dañado"):
        leer_extracto("roto.pdf", b"%PDF-1.4\nesto no es un pdf")


@pytest.mark.parametrize("contrasena,mensaje", [(None, "protegido con contraseña"), ("1234", "no es correcta")])
def test_pdf_con_contrasena(monkeypatch, contrasena, mensaje):
    import pdfplumber
    from pdfminer.pdfdocument import PDFPasswordIncorrect

    def cifrado(*_, **__):
        raise PDFPasswordIncorrect()

    monkeypatch.setattr(pdfplumber, "open", cifrado)
    with pytest.raises(ArchivoIlegible, match=mensaje) as error:
        leer_extracto("nu.pdf", b"%PDF-1.7 cifrado", contrasena)
    # La contraseña nunca aparece en el mensaje.
    assert "1234" not in str(error.value)


def test_texto_y_csv_siguen_funcionando():
    assert leer_extracto("a.txt", b"Pago Netflix 45.900")[1] == "texto"
    assert leer_extracto("a.csv", b"x;45.900")[1] == "csv"


from Entrada.entrada import completar_anio


def test_pdf_completa_el_anio_del_encabezado():
    pdf = crear_pdf(["Periodo: noviembre 2026", "02 NOV COMPRA EXITO 145.300,00", "Pagina 1 de 1"])
    filas, _ = leer_extracto("extracto.pdf", pdf)
    assert filas == [(2, "02 NOV 2026 COMPRA EXITO 145.300,00")]


def test_periodo_que_cruza_el_fin_de_anio():
    texto = "Periodo 15 dic 2025 - 14 ene 2026\n28 DIC NETFLIX 45.900,00\n03 ENE UBER 21.500,00"
    filas = [(2, "28 DIC NETFLIX 45.900,00"), (3, "03 ENE UBER 21.500,00")]
    assert completar_anio(filas, texto) == [
        (2, "28 DIC 2025 NETFLIX 45.900,00"), (3, "03 ENE 2026 UBER 21.500,00"),
    ]


@pytest.mark.parametrize("texto,fila", [
    ("Extracto sin año\n02 NOV X 1.000,00", "02 NOV X 1.000,00"),             # no hay año que usar
    ("Años 2024 y 2026\n02 NOV X 1.000,00", "02 NOV X 1.000,00"),              # ambiguo: no se adivina
    ("Periodo 2026\n05 oct 2025 X 1.000,00", "05 oct 2025 X 1.000,00"),         # ya trae año
])
def test_no_toca_las_filas_sin_un_anio_claro(texto, fila):
    assert completar_anio([(2, fila)], texto) == [(2, fila)]
