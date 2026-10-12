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


def test_pdf_ignora_el_texto_girado_del_margen():
    filas = [f"0{d} JUN COMPRA AMAZON 6.529,80" for d in range(1, 6)]
    pdf = crear_pdf(["Periodo 01 - 30 JUN 2025", *filas], margen_vertical="Nu Compania de Financiamiento S.A.")
    leidas, _ = leer_extracto("nu.pdf", pdf)
    assert [texto for _, texto in leidas] == [f.replace("JUN", "JUN 2025") for f in filas]


def test_filtro_descarta_caracteres_girados_aunque_se_marquen_verticales():
    # Tal como llegan del extracto de NuBank: pdfplumber dice upright=True,
    # pero la matriz los gira 90°. Antes se colaban en las filas ("a 05 jun").
    girado = {"object_type": "char", "text": "a", "upright": True, "matrix": (-0.0, 1.03, -1.0, -0.0, 26.28, 429.17)}
    normal = {"object_type": "char", "text": "0", "upright": True, "matrix": (1.0, 0.0, 0.0, 1.0, 68.06, 473.59)}
    assert not entrada._horizontal(girado)
    assert entrada._horizontal(normal)
    assert entrada._horizontal({"object_type": "rect"})


def test_un_numero_de_telefono_no_es_un_anio():
    texto = "Periodo 01 - 30 JUN 2025\n01 jun Compra -$6.529,80\nLinea gratuita 01 800 917 2000"
    assert completar_anio([(2, "01 jun Compra -$6.529,80")], texto) == [(2, "01 jun 2025 Compra -$6.529,80")]


def test_anio_dentro_de_una_fecha_numerica():
    texto = "Desde 01/06/2025 hasta 30/06/2025\n05 jun Compra 1.000,00"
    assert completar_anio([(2, "05 jun Compra 1.000,00")], texto) == [(2, "05 jun 2025 Compra 1.000,00")]


from Entrada.entrada import fecha_iso


def test_pdf_pone_la_fecha_del_movimiento_a_su_linea_del_4x1000():
    pdf = crear_pdf([
        "Periodo 01 - 30 JUN 2025",
        "Impuesto del 4x1000 -$118,84",            # total del resumen: no va debajo de ninguna fila
        "01 jun Compra en AMAZON -$6.529,80",
        "Impuesto del 4x1000 -$26,12",
        "Pagina 1 de 2",
        "Impuesto del 4x1000 -$9,00",              # no va justo debajo de una fila: no se adivina
    ])
    filas, _ = leer_extracto("nu.pdf", pdf)
    assert [t for _, t in filas] == ["01 jun 2025 Compra en AMAZON -$6.529,80", "01 jun 2025 Impuesto del 4x1000 -$26,12"]


@pytest.mark.parametrize("fila,esperada", [
    ("05 jun 2025 Compra", "2025-06-05"),
    ("05/06/2025 Compra", "2025-06-05"),
    ("2025-06-05 Compra", "2025-06-05"),
    ("31 feb 2025 Compra", None),
    ("05 jun Compra", None),
    ("Compra 05 jun 2025", None),
])
def test_fecha_iso(fila, esperada):
    assert fecha_iso(fila) == esperada
