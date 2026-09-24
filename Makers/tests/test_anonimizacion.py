from Anonimizacion.anonimizacion import anonimizar_movimiento


def item(tipo, remitente, destinatario, descripcion):
    return {
        "es_movimiento_financiero": True,
        "movimiento": {
            "tipo": tipo,
            "nombre_remitente": remitente,
            "nombre_destinatario": destinatario,
            "descripcion": descripcion,
        },
    }


def test_no_modifica_el_original():
    original = [item("egreso", "Juan Pérez", "Netflix", "Pago de Juan Pérez a Netflix")]
    anonimizar_movimiento(original)
    assert original[0]["movimiento"]["nombre_remitente"] == "Juan Pérez"
    assert original[0]["movimiento"]["descripcion"] == "Pago de Juan Pérez a Netflix"


def test_egreso_conserva_destinatario():
    (resultado,) = anonimizar_movimiento([item("egreso", "Juan Pérez", "Netflix", "Pago de Juan Pérez a Netflix")])
    datos = resultado["movimiento"]
    assert datos["nombre_remitente"] == "Jua*******"
    assert datos["nombre_destinatario"] == "Netflix"
    assert datos["descripcion"] == "Pago de Jua******* a Netflix"


def test_ingreso_conserva_remitente():
    (resultado,) = anonimizar_movimiento([item("ingreso", "Empresa XYZ", "María López", "Nómina de Empresa XYZ para maría")])
    datos = resultado["movimiento"]
    assert datos["nombre_remitente"] == "Empresa XYZ"
    assert datos["nombre_destinatario"] == "Mar********"
    assert datos["descripcion"] == "Nómina de Empresa XYZ para mar**"


def test_tipo_desconocido_anonimiza_ambos():
    (resultado,) = anonimizar_movimiento([item(None, "Juan Pérez", "Carlos Gómez", "Movimiento entre Juan y Carlos")])
    datos = resultado["movimiento"]
    assert datos["nombre_remitente"] == "Jua*******"
    assert datos["nombre_destinatario"] == "Car*********"
    assert datos["descripcion"] == "Movimiento entre Jua* y Car***"


def test_no_financiero_sin_cambios():
    original = [{"es_movimiento_financiero": False, "movimiento": None}]
    assert anonimizar_movimiento(original) == original
