"""Revisión humana: cada decisión cambia los cálculos y se puede deshacer."""
import sqlite3

import pytest

from Agregacion.agregacion import resumen_por_periodo
from Almacenamiento.almacenamiento import borrar_cliente, guardar_linea, obtener_movimientos_cliente
from Consultas.consultas import version_datos
from Revision.revision import aplicar, elementos_revision


def _mov(monto, tipo="egreso", categoria="vivienda", motivo=None, moneda="COP", fecha="2026-10-16",
         descripcion="Pago de arriendo"):
    return {"es_movimiento_financiero": True, "movimiento": {
        "nombre_remitente": None, "tipo": tipo, "categoria": categoria, "monto": monto,
        "moneda": moneda, "nombre_destinatario": "Inmobiliaria", "entidad": None, "fecha": fecha,
        "descripcion": descripcion, "requiere_revision_humana": motivo is not None,
        "motivo_revision": motivo}}


@pytest.fixture
def base(tmp_path):
    ruta = tmp_path / "m.db"
    guardar_linea("yo", "ext", 1, "nomina", [_mov(2800000, "ingreso", "ingreso_laboral", fecha="2026-10-30")], ruta)
    guardar_linea("yo", "ext", 2, "arriendo x2", [_mov(950000, motivo="posible_duplicado"),
                                                   _mov(950000, motivo="posible_duplicado")], ruta)
    guardar_linea("yo", "ext", 3, "notificacion", [{
        "es_movimiento_financiero": True, "movimiento": {
            "nombre_remitente": None, "tipo": None, "categoria": None, "monto": None, "moneda": None,
            "nombre_destinatario": None, "entidad": None, "fecha": None, "descripcion": "Sin datos",
            "requiere_revision_humana": True, "motivo_revision": "datos_insuficientes"}}], ruta)
    guardar_linea("otro", "ext", 1, "ajeno", [_mov(5000, motivo="posible_duplicado")], ruta)
    return ruta


def _balance(ruta):
    return sum(p["ingresos"] - p["egresos"] for p in resumen_por_periodo("yo", db_path=ruta))


def _elemento(ruta, caso):
    return next(e for e in elementos_revision("yo", ruta)["pendientes"] if e["caso"] == caso)


def test_duplicados_se_agrupan_en_un_solo_elemento(base):
    pendientes = elementos_revision("yo", base)["pendientes"]
    assert sorted(e["caso"] for e in pendientes) == ["duplicado", "individual"]
    assert _elemento(base, "duplicado")["repeticiones"] == 2


def test_es_el_mismo_pago_baja_el_total_sin_calculo_manual(base):
    antes = _balance(base)  # cuenta ambos mientras está pendiente
    aplicar("yo", "duplicado_si", _elemento(base, "duplicado")["ids"], db_path=base)
    assert _balance(base) == antes + 950000
    # Ninguno se borra: el descartado sigue en el libro.
    decisiones = sorted(str(m["decision"]) for m in obtener_movimientos_cliente("yo", base)
                        if m["monto"] == 950000)
    assert decisiones == ["confirmado", "descartado"]
    assert not any(e["caso"] == "duplicado" for e in elementos_revision("yo", base)["pendientes"])


def test_son_pagos_distintos_conserva_ambos(base):
    antes = _balance(base)
    aplicar("yo", "duplicado_no", _elemento(base, "duplicado")["ids"], db_path=base)
    assert _balance(base) == antes
    assert len(elementos_revision("yo", base)["resueltos"]) == 1


def test_deshacer_restaura_el_calculo(base):
    ids = _elemento(base, "duplicado")["ids"]
    antes = _balance(base)
    aplicar("yo", "duplicado_si", ids, db_path=base)
    aplicar("yo", "deshacer", ids, db_path=base)
    assert _balance(base) == antes
    assert _elemento(base, "duplicado")["repeticiones"] == 2


def test_completar_datos_insuficientes_lo_suma(base):
    ids = _elemento(base, "individual")["ids"]
    antes = _balance(base)
    aplicar("yo", "corregir", ids, {"monto": 40000, "tipo": "egreso", "moneda": "COP",
                                    "categoria": "otros", "fecha": "2026-10-20"}, db_path=base)
    assert _balance(base) == antes - 40000
    assert all(e["caso"] != "individual" for e in elementos_revision("yo", base)["pendientes"])


def test_no_se_puede_confirmar_un_movimiento_incompleto(base):
    with pytest.raises(ValueError, match="completa"):
        aplicar("yo", "confirmar", _elemento(base, "individual")["ids"], db_path=base)
    with pytest.raises(ValueError, match="completa"):
        aplicar("yo", "corregir", _elemento(base, "individual")["ids"], {"monto": 40000}, db_path=base)


@pytest.mark.parametrize("valores,mensaje", [
    ({"monto": -5}, "mayor que cero"), ({"monto": True}, "número"), ({"monto": "40000"}, "número"),
    ({"monto": float("inf")}, "número"), ({"moneda": "BTC"}, "Moneda"), ({"fecha": "16/10/2026"}, "AAAA"),
    ({"categoria": "casino"}, "Categoría"), ({"tipo": "robo"}, "tipo"), ({"cliente_id": "x"}, "campos"),
    ({}, "ningún dato"), ({"categoria": "ingreso_laboral"}, "ingresos"),
])
def test_correcciones_invalidas(base, valores, mensaje):
    ids = [_elemento(base, "duplicado")["ids"][0]]
    with pytest.raises(ValueError, match=mensaje):
        aplicar("yo", "corregir", ids, valores, db_path=base)


def test_no_se_pueden_tocar_movimientos_de_otro_titular(base):
    ajeno = [m["movimiento_id"] for m in obtener_movimientos_cliente("otro", base)]
    with pytest.raises(ValueError, match="no existe"):
        aplicar("yo", "descartar", ajeno, db_path=base)


def test_no_se_pueden_revisar_movimientos_no_marcados(base):
    nomina = [m["movimiento_id"] for m in obtener_movimientos_cliente("yo", base) if m["tipo"] == "ingreso"]
    with pytest.raises(ValueError, match="no está marcado"):
        aplicar("yo", "descartar", nomina, db_path=base)


@pytest.mark.parametrize("accion,ids", [("borrar_todo", ["x"]), ("descartar", []), ("descartar", "x"),
                                        ("descartar", [1, 2]), ("descartar", ["a"] * 11)])
def test_peticiones_malformadas(base, accion, ids):
    with pytest.raises(ValueError):
        aplicar("yo", accion, ids, db_path=base)


def test_reprocesar_conserva_las_decisiones(base):
    aplicar("yo", "duplicado_si", _elemento(base, "duplicado")["ids"], db_path=base)
    balance = _balance(base)
    # El modelo vuelve a procesar la misma línea y redacta distinto.
    guardar_linea("yo", "ext", 2, "arriendo x2", [_mov(950000, motivo="posible_duplicado", descripcion="Arriendo"),
                                                   _mov(950000, motivo="posible_duplicado", descripcion="Arriendo")], base)
    assert _balance(base) == balance


def test_la_version_de_datos_cambia_con_cada_decision(base):
    antes = version_datos("yo", base)
    aplicar("yo", "descartar", _elemento(base, "duplicado")["ids"], db_path=base)
    assert version_datos("yo", base) != antes


def test_borrar_titular_borra_sus_decisiones(base):
    aplicar("yo", "descartar", _elemento(base, "duplicado")["ids"], db_path=base)
    borrar_cliente("yo", base)
    assert sqlite3.connect(base).execute("SELECT COUNT(*) FROM revisiones WHERE cliente_id='yo'").fetchone()[0] == 0


def test_corregir_categoria_aprende_y_deshacer_lo_olvida(base, tmp_path):
    rag = tmp_path / "rag.db"
    ids = [_elemento(base, "duplicado")["ids"][0]]
    aplicar("yo", "corregir", ids, {"categoria": "servicios"}, db_path=base, rag_db_path=rag)
    humanos = lambda: sqlite3.connect(rag).execute("SELECT COUNT(*) FROM ejemplos WHERE origen='humano'").fetchone()[0]
    assert humanos() == 1
    aplicar("yo", "deshacer", ids, db_path=base, rag_db_path=rag)
    assert humanos() == 0
    semillas = sqlite3.connect(rag).execute("SELECT COUNT(*) FROM ejemplos WHERE origen='semilla'").fetchone()[0]
    assert semillas > 0  # deshacer no toca las semillas


def test_el_asistente_no_avisa_de_revisiones_ya_resueltas(base):
    from Consultas.consultas import consultar
    ids = _elemento(base, "duplicado")["ids"]
    pendiente = lambda: [m["pendiente_de_revision"] for m in
                         consultar("yo", categoria="vivienda", db_path=base)["movimientos_principales"]]
    assert pendiente() == [True, True]
    aplicar("yo", "duplicado_no", ids, db_path=base)
    assert pendiente() == [False, False]
