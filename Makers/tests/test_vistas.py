"""Vistas por periodo del export y vigencia de las lecturas guardadas."""
import pytest

from Almacenamiento.almacenamiento import guardar_linea
from Exportacion.exportacion import VISTA_TODO, construir_datos_dashboard, construir_vista
from Resumen import resumen
from Revision.revision import aplicar, elementos_revision


def _mov(monto, fecha, tipo="egreso", categoria="otros", motivo=None):
    return {"es_movimiento_financiero": True, "movimiento": {
        "nombre_remitente": None, "tipo": tipo, "categoria": categoria, "monto": monto, "moneda": "COP",
        "nombre_destinatario": None, "entidad": None, "fecha": fecha, "descripcion": f"m {monto}",
        "requiere_revision_humana": motivo is not None, "motivo_revision": motivo}}


@pytest.fixture
def base(tmp_path):
    ruta = tmp_path / "m.db"
    guardar_linea("yo", "e", 1, "a", [_mov(1000000, "2026-09-30", "ingreso", "ingreso_laboral")], ruta)
    guardar_linea("yo", "e", 2, "b", [_mov(100000, "2026-10-05", categoria="transporte")], ruta)
    guardar_linea("yo", "e", 3, "c", [_mov(300000, "2026-10-16", categoria="vivienda", motivo="posible_duplicado"),
                                      _mov(300000, "2026-10-16", categoria="vivienda", motivo="posible_duplicado")], ruta)
    guardar_linea("yo", "e", 4, "d", [_mov(50000, None, categoria="otros")], ruta)
    return ruta


def test_una_vista_por_periodo_mas_el_total(base):
    d = construir_datos_dashboard("yo", incluir_texto=False, db_path=base)
    assert d["periodos_disponibles"] == ["2026-09", "2026-10"]
    assert list(d["vistas"]) == [VISTA_TODO, "2026-09", "2026-10"]


def test_las_vistas_suman_el_total(base):
    v = construir_datos_dashboard("yo", incluir_texto=False, db_path=base)["vistas"]
    meses = v["2026-09"]["total_movimientos"] + v["2026-10"]["total_movimientos"]
    # El movimiento sin fecha solo está en el total.
    assert v[VISTA_TODO]["total_movimientos"] == meses + 1
    assert v[VISTA_TODO]["movimientos_sin_fecha"] == 1 and v["2026-10"]["movimientos_sin_fecha"] == 0


def test_categorias_del_mes(base):
    oct_ = construir_vista("yo", "2026-10", db_path=base)
    assert {c["categoria"] for c in oct_["categorias_egreso"]} == {"transporte", "vivienda"}
    assert construir_vista("yo", "2026-09", db_path=base)["categorias_egreso"] == []


def test_periodo_inexistente(base):
    with pytest.raises(ValueError):
        construir_vista("yo", "1999-01", db_path=base)


def test_lectura_se_redacta_una_vez_y_luego_se_reutiliza(base, monkeypatch):
    llamadas = []
    monkeypatch.setattr(resumen, "redactar", lambda m, max_tokens=3000: llamadas.append(m["alcance"]) or "texto")
    vista = construir_vista("yo", "2026-10", db_path=base)
    revision = elementos_revision("yo", base)
    assert resumen.lectura("yo", "2026-10", vista, revision, db_path=base) == {"texto": "texto", "vigente": True}
    resumen.lectura("yo", "2026-10", vista, revision, db_path=base)
    assert llamadas == ["octubre de 2026"]  # la segunda vez no llama al modelo


def test_una_decision_vuelve_vieja_la_lectura_de_su_mes_sin_llamar_a_groq(base, monkeypatch):
    monkeypatch.setattr(resumen, "redactar", lambda m, max_tokens=3000: "texto")
    for periodo in ("2026-09", "2026-10"):
        resumen.lectura("yo", periodo, construir_vista("yo", periodo, db_path=base),
                        elementos_revision("yo", base), db_path=base)

    duplicado = next(e for e in elementos_revision("yo", base)["pendientes"] if e["caso"] == "duplicado")
    aplicar("yo", "duplicado_si", duplicado["ids"], db_path=base)

    monkeypatch.setattr(resumen, "redactar", lambda *a, **k: pytest.fail("no debía llamar a Groq"))
    lecturas = construir_datos_dashboard("yo", incluir_texto=False, db_path=base)["lecturas"]
    assert lecturas["2026-10"]["vigente"] is False   # cambió octubre
    assert lecturas["2026-09"]["vigente"] is True    # septiembre no se tocó
