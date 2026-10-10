"""Seguridad del servidor local. Usa el cliente de prueba de Flask, sin red."""
import pytest

import servidor

BASE = f"http://127.0.0.1:{servidor.PUERTO}"
PROPIO = {"Origin": BASE}


@pytest.fixture
def cliente():
    servidor.app.config["TESTING"] = True
    return servidor.app.test_client()


@pytest.mark.parametrize("ruta", ["/", "/cargar", "/cargar.html", "/index.html", "/estilo.css"])
def test_sirve_las_paginas(cliente, ruta):
    assert cliente.get(ruta, base_url=BASE).status_code == 200


@pytest.mark.parametrize("ruta", [
    "/.env.local", "/.gitignore", "/vercel.json", "/../.env", "/..%2f.env",
    "/servidor.py", "/.vercel/project.json", "/datos/movimientos.db",
])
def test_no_sirve_nada_fuera_de_la_lista(cliente, ruta):
    assert cliente.get(ruta, base_url=BASE).status_code == 404


def test_host_ajeno_bloqueado(cliente):
    # DNS rebinding: un dominio que resuelve a 127.0.0.1 no puede leer los datos.
    assert cliente.get("/datos.json", base_url="http://atacante.example:5050").status_code == 403


def test_post_desde_otra_web_bloqueado(cliente):
    r = cliente.post("/api/preguntar", base_url=BASE, json={"pregunta": "hola"},
                     headers={"Origin": "https://atacante.example"})
    assert r.status_code == 403


def test_post_cross_site_bloqueado_aunque_falte_origin(cliente):
    r = cliente.post("/api/preguntar", base_url=BASE, json={"pregunta": "hola"},
                     headers={"Sec-Fetch-Site": "cross-site"})
    assert r.status_code == 403


def test_procesar_tambien_protegido(cliente):
    r = cliente.post("/api/procesar", base_url=BASE, data={"cliente": "x"},
                     headers={"Origin": "https://atacante.example"})
    assert r.status_code == 403


def test_preguntar_exige_json(cliente):
    r = cliente.post("/api/preguntar", base_url=BASE, data="pregunta=hola", headers=PROPIO)
    assert r.status_code == 400


def test_preguntar_rechaza_cuerpos_enormes(cliente):
    r = cliente.post("/api/preguntar", base_url=BASE, headers=PROPIO,
                     json={"pregunta": "x", "historial": [{"pregunta": "y" * 20000}]})
    assert r.status_code == 413


def test_saludo_responde_sin_modelo(cliente, monkeypatch):
    monkeypatch.setattr(servidor, "cliente_actual", lambda: "cualquiera")
    r = cliente.post("/api/preguntar", base_url=BASE, headers=PROPIO, json={"pregunta": "hola"})
    assert r.status_code == 200 and r.get_json()["tipo"] == "cortesia"


def test_el_titular_no_lo_decide_el_navegador(cliente, monkeypatch):
    vistos = []
    monkeypatch.setattr(servidor, "cliente_actual", lambda: "titular_del_dashboard")
    monkeypatch.setattr(servidor, "responder",
                        lambda cli, pregunta, historial, **_: vistos.append(cli) or {"tipo": "respuesta", "texto": "ok"})
    cliente.post("/api/preguntar", base_url=BASE, headers=PROPIO,
                 json={"pregunta": "¿cuánto gasté?", "cliente": "otro_titular", "cliente_id": "otro"})
    assert vistos == ["titular_del_dashboard"]


def test_sugerencias(cliente):
    r = cliente.get("/api/sugerencias", base_url=BASE)
    assert r.status_code == 200 and len(r.get_json()) == 3


def test_revision_valida_y_protegida(cliente, monkeypatch):
    monkeypatch.setattr(servidor, "cliente_actual", lambda: "titular")
    assert cliente.post("/api/revision", base_url=BASE, data="x", headers=PROPIO).status_code == 400
    r = cliente.post("/api/revision", base_url=BASE, headers=PROPIO, json={"accion": "borrar_todo", "ids": ["x"]})
    assert r.status_code == 400 and "Acción" in r.get_json()["error"]
    r = cliente.post("/api/revision", base_url=BASE, json={"accion": "descartar", "ids": ["x"]},
                     headers={"Origin": "https://atacante.example"})
    assert r.status_code == 403


def test_revision_usa_el_titular_del_servidor(cliente, monkeypatch):
    vistos = []
    monkeypatch.setattr(servidor, "cliente_actual", lambda: "titular_del_dashboard")
    monkeypatch.setattr(servidor, "aplicar_revision", lambda cli, *a: vistos.append(cli) or 1)
    monkeypatch.setattr(servidor, "exportar_dashboard", lambda *a, **k: (None, {"ok": True}))
    cliente.post("/api/revision", base_url=BASE, headers=PROPIO,
                 json={"accion": "descartar", "ids": ["x"], "cliente": "otro"})
    assert vistos == ["titular_del_dashboard"]


def test_lectura_rechaza_periodos_invalidos(cliente, monkeypatch):
    monkeypatch.setattr(servidor, "cliente_actual", lambda: "titular")
    monkeypatch.setattr(servidor, "construir_vista",
                        lambda c, p: (_ for _ in ()).throw(ValueError("Ese periodo no tiene movimientos.")))
    r = cliente.get("/api/lectura?periodo=1999-01", base_url=BASE)
    assert r.status_code == 400
    assert cliente.get("/api/lectura?periodo=" + "x" * 50, base_url=BASE).status_code == 400


def test_lectura_get_no_fuerza_y_post_si(cliente, monkeypatch):
    llamadas = []
    monkeypatch.setattr(servidor, "cliente_actual", lambda: "titular")
    monkeypatch.setattr(servidor, "construir_vista", lambda c, p: {"periodo": p})
    monkeypatch.setattr(servidor, "elementos_revision", lambda c: {"pendientes": []})
    monkeypatch.setattr(servidor, "lectura_periodo",
                        lambda c, p, v, r, forzar: llamadas.append(forzar) or {"texto": "t", "vigente": True})
    cliente.get("/api/lectura?periodo=2026-10", base_url=BASE)
    cliente.post("/api/lectura", base_url=BASE, headers=PROPIO, json={"periodo": "2026-10"})
    assert llamadas == [False, True]
