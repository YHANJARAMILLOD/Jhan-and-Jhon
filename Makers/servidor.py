"""
Servidor local que conecta el frontend con el pipeline.

    python servidor.py              (puerto 5050)
    PUERTO=8080 python servidor.py  (otro puerto)

Sirve el dashboard en http://127.0.0.1:5050 y expone /api/procesar, que
recibe extractos, los pasa por el pipeline y regenera datos.json.

Está pensado para uso local: se ata a 127.0.0.1 a propósito. Exponerlo a la
red dejaría que cualquiera dispare llamadas a Ollama y a tu cuenta de Groq.
"""
import json
import os
import sys
import traceback
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

from Almacenamiento.almacenamiento import guardar_linea, id_extracto
from Entrada.entrada import ArchivoIlegible, leer_extracto
from Asistente.asistente import preguntas_sugeridas, responder
from Revision.revision import aplicar as aplicar_revision
from Exportacion.exportacion import VISTA_TODO, construir_vista, exportar_dashboard
from Resumen.resumen import lectura as lectura_periodo
from Revision.revision import elementos_revision
from Pipeline.pipeline import TAMANO_LOTE, procesar_en_lotes

RAIZ = Path(__file__).resolve().parent.parent
DASHBOARD = RAIZ / "dashboard"

# Un extracto bancario de un mes rara vez pasa de unos pocos KB. El límite
# corta subidas absurdas antes de leerlas en memoria.
# Un extracto en PDF de un mes ronda los cientos de KB; el límite deja margen
# para subir varios a la vez y corta subidas absurdas antes de leerlas.
MAX_BYTES = 15 * 1024 * 1024
MAX_LINEAS = 200

# 5000 no: en macOS lo ocupa el receptor de AirPlay (ControlCenter) y la
# petición se va a ese servicio en vez de a este servidor.
PUERTO = int(os.getenv("PUERTO", "5050"))

# Solo estos archivos salen del servidor. Servir la carpeta entera exponía
# todo lo que hubiera dentro (había un .env.local con un token de Vercel).
ESTATICOS = {
    "": "index.html",
    "index": "index.html",
    "index.html": "index.html",
    "cargar": "cargar.html",
    "cargar.html": "cargar.html",
    "estilo.css": "estilo.css",
    "datos.json": "datos.json",
}

# Host y Origin válidos. Validar el Host corta el DNS rebinding (un dominio
# ajeno que resuelve a 127.0.0.1 y lee datos.json); validar el Origin corta
# que otra web abierta en el navegador dispare el pipeline con un POST.
HOSTS_PERMITIDOS = {f"127.0.0.1:{PUERTO}", f"localhost:{PUERTO}"}
ORIGENES_PERMITIDOS = {f"http://{host}" for host in HOSTS_PERMITIDOS}

MAX_BYTES_PREGUNTA = 8 * 1024

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = MAX_BYTES


@app.before_request
def proteger():
    if request.host not in HOSTS_PERMITIDOS:
        return jsonify({"error": "Host no permitido."}), 403
    if request.method not in ("GET", "HEAD"):
        origen = request.headers.get("Origin")
        if origen is not None and origen not in ORIGENES_PERMITIDOS:
            return jsonify({"error": "Origen no permitido."}), 403
        if request.headers.get("Sec-Fetch-Site") == "cross-site":
            return jsonify({"error": "Origen no permitido."}), 403


@app.errorhandler(413)
def demasiado_grande(_error):
    # Sin esto Flask responde HTML y el frontend no puede mostrar el motivo.
    return jsonify({"error": f"El envío supera el límite de {MAX_BYTES // (1024 * 1024)} MB."}), 413


def cliente_actual():
    """
    Titular del estado de cuenta que muestra el dashboard.

    Se decide aquí y no se acepta del navegador: así el asistente solo puede
    consultar los datos del titular que se está viendo.
    """
    try:
        return json.loads((DASHBOARD / "datos.json").read_text(encoding="utf-8")).get("cliente_id")
    except (OSError, ValueError):
        return None


def evento(tipo, **datos):
    """Una línea de NDJSON. El frontend lee el flujo a medida que llega."""
    return json.dumps({"tipo": tipo, **datos}, ensure_ascii=False) + "\n"


@app.post("/api/procesar")
def procesar():
    cliente = (request.form.get("cliente") or "").strip()
    if not cliente:
        return jsonify({"error": "Falta el identificador del cliente."}), 400

    archivos = [a for a in request.files.getlist("archivos") if a.filename]
    if not archivos:
        return jsonify({"error": "No se recibió ningún archivo."}), 400

    usar_rag = request.form.get("sin_rag") != "1"

    # Una contraseña por archivo, en el mismo orden. Se usan solo para abrir
    # cada PDF en memoria: no se guardan ni se registran.
    contrasenas = request.form.getlist("contrasenas")

    # Los archivos se leen aquí, no dentro del generador: el contexto de la
    # petición ya no existe cuando Flask empieza a consumir el flujo.
    leidos = []
    vistos = set()
    try:
        for posicion, archivo in enumerate(archivos):
            contenido = archivo.read()
            # El id sale del contenido: el mismo archivo da el mismo id aunque se
            # llame distinto, y dos archivos distintos con igual nombre no se pisan.
            extracto_id = id_extracto(contenido)
            if extracto_id in vistos:
                continue
            vistos.add(extracto_id)
            contrasena = contrasenas[posicion] if posicion < len(contrasenas) else None
            filas, tipo = leer_extracto(archivo.filename, contenido, contrasena or None)
            if filas:
                leidos.append((archivo.filename, extracto_id, tipo, filas))
    except ArchivoIlegible as error:
        return jsonify({"error": str(error)}), 400

    total = sum(len(filas) for *_, filas in leidos)
    if not total:
        return jsonify({"error": "Los archivos no tienen ninguna línea con contenido."}), 400
    if total > MAX_LINEAS:
        return jsonify({
            "error": f"Son {total} filas y el límite es {MAX_LINEAS}. "
                     f"Súbelos por partes: cada fila tarda unos segundos en procesarse."
        }), 400

    def flujo():
        yield evento("inicio", total=total, archivos=sorted({nombre for nombre, *_ in leidos}))

        guardados = 0
        fallidas = 0
        indice = 0

        for nombre, extracto_id, tipo, filas in leidos:
            # Los extractos estructurados (PDF, CSV) traen un movimiento por fila
            # y se procesan en lotes. El texto libre va línea por línea: una
            # línea puede contener varios movimientos.
            tamano = TAMANO_LOTE if tipo in ("pdf", "csv") else 1
            for numero, texto, resultado, error in procesar_en_lotes(filas, usar_rag, tamano):
                indice += 1
                if error is None:
                    try:
                        # Cada fila se guarda en cuanto termina: si el proceso se
                        # corta, lo ya procesado no se pierde. Una fila que falla
                        # no llega aquí, así que sus filas previas se conservan.
                        guardados += guardar_linea(cliente, extracto_id, numero, texto, resultado["revisado"])
                    except Exception as fallo:
                        error = fallo
                if error is not None:
                    fallidas += 1
                    yield evento("linea", indice=indice, archivo=nombre, texto=texto,
                                 ok=False, mensaje=f"{type(error).__name__}: {error}")
                    continue

                financieros = [m for m in resultado["revisado"] if m.get("es_movimiento_financiero")]
                yield evento("linea", indice=indice, archivo=nombre, texto=texto,
                             ok=True, movimientos=financieros,
                             ejemplos_rag=sum(len(e) for e in resultado["ejemplos_rag"]))

        if not guardados:
            yield evento("fin", guardados=0, fallidas=fallidas, exportado=False,
                         mensaje="No se guardó ningún movimiento, así que el estado de cuenta no cambió.")
            return

        try:
            # Sin redactar: la lectura se genera sola la primera vez que se abre
            # una vista, o cuando el titular la pide. Procesar no gasta una llamada.
            exportar_dashboard(cliente, DASHBOARD / "datos.json", incluir_texto=False)
            yield evento("fin", guardados=guardados, fallidas=fallidas, exportado=True)
        except Exception as error:
            yield evento("fin", guardados=guardados, fallidas=fallidas, exportado=False,
                         mensaje=f"Se guardaron los movimientos pero falló el export: {error}")

    return Response(flujo(), mimetype="application/x-ndjson",
                    headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.post("/api/preguntar")
def preguntar():
    if (request.content_length or 0) > MAX_BYTES_PREGUNTA:
        return jsonify({"tipo": "rechazo", "texto": "La pregunta es demasiado larga."}), 413

    cuerpo = request.get_json(silent=True)
    if not isinstance(cuerpo, dict):
        return jsonify({"tipo": "rechazo", "texto": "Petición inválida."}), 400

    cliente = cliente_actual()
    if not cliente:
        return jsonify({"tipo": "sin_datos", "texto": "Todavía no hay un estado de cuenta generado."})

    vista = cuerpo.get("vista")
    return jsonify(responder(cliente, cuerpo.get("pregunta"), cuerpo.get("historial"),
                             vista=vista if isinstance(vista, str) else None))


@app.post("/api/revision")
def revision():
    """
    Aplica una decisión del titular y devuelve el estado de cuenta recalculado.

    No llama a Groq: regenera las cifras con SQL y conserva la lectura anterior
    marcada como desactualizada. Un clic, cero llamadas pagadas.
    """
    if (request.content_length or 0) > MAX_BYTES_PREGUNTA:
        return jsonify({"error": "Petición demasiado grande."}), 413
    cuerpo = request.get_json(silent=True)
    if not isinstance(cuerpo, dict):
        return jsonify({"error": "Petición inválida."}), 400

    cliente = cliente_actual()
    if not cliente:
        return jsonify({"error": "Todavía no hay un estado de cuenta generado."}), 409

    try:
        cambiados = aplicar_revision(cliente, cuerpo.get("accion"), cuerpo.get("ids"), cuerpo.get("valores"))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    _, datos = exportar_dashboard(cliente, DASHBOARD / "datos.json", incluir_texto=False)
    return jsonify({"cambiados": cambiados, "datos": datos})


@app.route("/api/lectura", methods=["GET", "POST"])
def lectura():
    """
    Lectura redactada de una vista.

    GET devuelve la guardada; solo si nunca se redactó, la redacta (una
    llamada, la primera vez). POST la vuelve a redactar a pedido del titular.
    """
    cliente = cliente_actual()
    if not cliente:
        return jsonify({"error": "Todavía no hay un estado de cuenta generado."}), 409

    cuerpo = request.get_json(silent=True) if request.method == "POST" else None
    periodo = (cuerpo or {}).get("periodo") if request.method == "POST" else request.args.get("periodo")
    periodo = periodo or VISTA_TODO
    if not isinstance(periodo, str) or len(periodo) > 10:
        return jsonify({"error": "Periodo inválido."}), 400

    try:
        vista = construir_vista(cliente, periodo)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    try:
        resultado = lectura_periodo(cliente, periodo, vista, elementos_revision(cliente),
                                    forzar=request.method == "POST")
    except Exception as error:
        app.logger.warning("Lectura no disponible: %s: %s", type(error).__name__, error)
        return jsonify({"error": "No se pudo redactar la lectura. Inténtalo de nuevo en unos segundos."}), 502
    return jsonify({"periodo": periodo, **resultado})


@app.get("/api/sugerencias")
def sugerencias():
    return jsonify(preguntas_sugeridas())


@app.get("/api/estado")
def estado():
    """Permite al frontend saber si hay servidor y si ya existe un export."""
    return jsonify({
        "servidor": True,
        "hay_datos": (DASHBOARD / "datos.json").exists(),
    })


@app.get("/")
@app.get("/<path:recurso>")
def estatico(recurso=""):
    archivo = ESTATICOS.get(recurso)
    if archivo is None:
        return jsonify({"error": "No encontrado"}), 404
    return send_from_directory(DASHBOARD, archivo)


if __name__ == "__main__":
    if not DASHBOARD.exists():
        print(f"No existe la carpeta del dashboard: {DASHBOARD}")
        sys.exit(1)

    print(f"Dashboard en  http://127.0.0.1:{PUERTO}")
    print(f"Sirviendo     {DASHBOARD}")
    print("Ctrl+C para detener.\n")
    app.run(host="127.0.0.1", port=PUERTO, debug=False, threaded=True)
