"""Guardado de movimientos: ids estables y sin pérdida de datos al reprocesar."""
import sqlite3

from Almacenamiento.almacenamiento import (
    guardar_linea, id_extracto, inicializar_db, obtener_movimientos_cliente,
)


def _mov(descripcion, monto=1000, financiero=True):
    if not financiero:
        return {"es_movimiento_financiero": False, "movimiento": None}
    return {"es_movimiento_financiero": True, "movimiento": {
        "nombre_remitente": None, "tipo": "egreso", "categoria": "otros", "monto": monto,
        "moneda": "COP", "nombre_destinatario": None, "entidad": None, "fecha": "2026-10-01",
        "descripcion": descripcion, "requiere_revision_humana": False, "motivo_revision": None}}


def _ids(ruta, cliente="c1"):
    return sorted(m["movimiento_id"] for m in obtener_movimientos_cliente(cliente, ruta))


def test_reprocesar_no_duplica_y_el_id_es_estable(tmp_path):
    ruta = tmp_path / "m.db"
    guardar_linea("c1", "ext", 1, "Pago Netflix 45.900 COP", [_mov("Pago a Netflix")], ruta)
    antes = _ids(ruta)
    # El modelo redacta distinto al reprocesar: el id no debe cambiar.
    guardar_linea("c1", "ext", 1, "Pago Netflix 45.900 COP", [_mov("Suscripción Netflix")], ruta)
    assert _ids(ruta) == antes and len(antes) == 1


def test_una_linea_que_falla_conserva_sus_filas(tmp_path):
    ruta = tmp_path / "m.db"
    guardar_linea("c1", "ext", 1, "línea uno", [_mov("uno")], ruta)
    guardar_linea("c1", "ext", 2, "línea dos", [_mov("dos")], ruta)
    # Al reprocesar, la línea 2 falla y nunca se guarda: la 1 se reemplaza y la
    # 2 debe seguir en la base. Antes se borraba el extracto entero.
    guardar_linea("c1", "ext", 1, "línea uno", [_mov("uno bis")], ruta)
    descripciones = sorted(m["descripcion"] for m in obtener_movimientos_cliente("c1", ruta))
    assert descripciones == ["dos", "uno bis"]


def test_lineas_identicas_en_distinta_posicion_no_se_pisan(tmp_path):
    ruta = tmp_path / "m.db"
    # Dos cafés iguales el mismo día son dos movimientos reales.
    guardar_linea("c1", "ext", 3, "Café 5.000 COP", [_mov("café")], ruta)
    guardar_linea("c1", "ext", 4, "Café 5.000 COP", [_mov("café")], ruta)
    assert len(_ids(ruta)) == 2


def test_varios_movimientos_por_linea_y_no_financieros(tmp_path):
    ruta = tmp_path / "m.db"
    n = guardar_linea("c1", "ext", 1, "x", [_mov("a"), _mov("", financiero=False), _mov("b")], ruta)
    assert n == 2 and len(_ids(ruta)) == 2


def test_id_extracto_depende_del_contenido_no_del_nombre():
    assert id_extracto(b"contenido A") == id_extracto(b"contenido A")
    assert id_extracto(b"contenido A") != id_extracto(b"contenido B")
    assert id_extracto("texto") == id_extracto("texto".encode("utf-8"))


def test_migra_bases_antiguas(tmp_path):
    ruta = tmp_path / "vieja.db"
    conexion = sqlite3.connect(ruta)
    conexion.execute("CREATE TABLE movimientos (movimiento_id TEXT PRIMARY KEY, cliente_id TEXT NOT NULL, "
                     "extracto_id TEXT NOT NULL, fecha_ingesta TEXT NOT NULL, nombre_remitente TEXT, tipo TEXT, "
                     "categoria TEXT, monto REAL, moneda TEXT, nombre_destinatario TEXT, entidad TEXT, "
                     "fecha TEXT, descripcion TEXT)")
    conexion.execute("INSERT INTO movimientos VALUES ('viejo','c1','e','t',NULL,'egreso','otros',1,'COP',NULL,NULL,NULL,'d')")
    conexion.commit()
    conexion.close()

    inicializar_db(ruta)
    columnas = {f[1] for f in sqlite3.connect(ruta).execute("PRAGMA table_info(movimientos)")}
    assert {"requiere_revision_humana", "motivo_revision", "linea_id", "numero_linea"} <= columnas
    assert _ids(ruta) == ["viejo"]
