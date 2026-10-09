"""
Servidor local que conecta el frontend con el pipeline.

    python servidor.py              (puerto 5050)
    PUERTO=8080 python servidor.py  (otro puerto)

Sirve el dashboard en http://127.0.0.1:5050 y expone /api/procesar, que
recibe extractos, los pasa por el pipeline y regenera datos.json.

Está pensado para uso local: se ata a 127.0.0.1 a propósito. Exponerlo a la
red dejaría que cualquiera dispare llamadas a Ollama y a tu cuenta de Groq.
"""
import hashlib
import json
import os
import sys
import traceback
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

from Almacenamiento.almacenamiento import guardar_movimientos
from Exportacion.exportacion import exportar_dashboard
from Pipeline.pipeline import procesar_movimiento

RAIZ = Path(__file__).resolve().parent.parent
DASHBOARD = RAIZ / "dashboard"

# Un extracto bancario de un mes rara vez pasa de unos pocos KB. El límite
# corta subidas absurdas antes de leerlas en memoria.
MAX_BYTES = 2 * 1024 * 1024
MAX_LINEAS = 200

# 5000 no: en macOS lo ocupa el receptor de AirPlay (ControlCenter) y la
# petición se va a ese servicio en vez de a este servidor.
PUERTO = int(os.getenv("PUERTO", "5050"))

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = MAX_BYTES


def leer_lineas(archivo):
    """
    Texto de un archivo subido, una transacción por línea.

    Se ignoran líneas vacías y comentarios, igual que en main.py --archivo.
    """
    try:
        contenido = archivo.read().decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError(f"'{archivo.filename}' no es texto UTF-8. Se esperan archivos .txt o .csv.")

    return [
        linea.strip()
        for linea in contenido.splitlines()
        if linea.strip() and not linea.lstrip().startswith("#")
    ]


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

    # Los archivos se leen aquí, no dentro del generador: el contexto de la
    # petición ya no existe cuando Flask empieza a consumir el flujo.
    tareas = []
    try:
        for archivo in archivos:
            lineas = leer_lineas(archivo)
            if not lineas:
                continue
            # El id del extracto sale del nombre: reprocesar el mismo archivo
            # reemplaza sus filas en vez de duplicarlas.
            extracto_id = "arch-" + hashlib.sha256(archivo.filename.encode("utf-8")).hexdigest()[:16]
            for linea in lineas:
                tareas.append((archivo.filename, extracto_id, linea))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    if not tareas:
        return jsonify({"error": "Los archivos no tienen ninguna línea con contenido."}), 400

    if len(tareas) > MAX_LINEAS:
        return jsonify({
            "error": f"Son {len(tareas)} líneas y el límite es {MAX_LINEAS}. "
                     f"Cada línea tarda unos segundos en procesarse."
        }), 400

    def flujo():
        yield evento("inicio", total=len(tareas),
                     archivos=sorted({t[0] for t in tareas}))

        por_extracto = {}
        fallidas = 0

        for indice, (nombre, extracto_id, texto) in enumerate(tareas, start=1):
            try:
                resultado = procesar_movimiento(texto, usar_rag=usar_rag)
            except Exception as error:
                fallidas += 1
                yield evento("linea", indice=indice, archivo=nombre, texto=texto,
                             ok=False, mensaje=f"{type(error).__name__}: {error}")
                continue

            revisado = resultado["revisado"]
            por_extracto.setdefault(extracto_id, []).extend(revisado)

            financieros = [m for m in revisado if m.get("es_movimiento_financiero")]
            yield evento("linea", indice=indice, archivo=nombre, texto=texto,
                         ok=True, movimientos=financieros,
                         ejemplos_rag=sum(len(e) for e in resultado["ejemplos_rag"]))

        guardados = 0
        for extracto_id, movimientos in por_extracto.items():
            guardados += guardar_movimientos(cliente, extracto_id, movimientos)

        if not guardados:
            yield evento("fin", guardados=0, fallidas=fallidas, exportado=False,
                         mensaje="No se guardó ningún movimiento, así que el estado de cuenta no cambió.")
            return

        try:
            exportar_dashboard(cliente, DASHBOARD / "datos.json")
            yield evento("fin", guardados=guardados, fallidas=fallidas, exportado=True)
        except Exception as error:
            yield evento("fin", guardados=guardados, fallidas=fallidas, exportado=False,
                         mensaje=f"Se guardaron los movimientos pero falló el export: {error}")

    return Response(flujo(), mimetype="application/x-ndjson",
                    headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.get("/api/estado")
def estado():
    """Permite al frontend saber si hay servidor y si ya existe un export."""
    return jsonify({
        "servidor": True,
        "hay_datos": (DASHBOARD / "datos.json").exists(),
    })


@app.get("/")
def inicio():
    return send_from_directory(DASHBOARD, "index.html")


@app.get("/<path:recurso>")
def estatico(recurso):
    # send_from_directory rechaza rutas que se salgan de la carpeta.
    destino = DASHBOARD / recurso
    if destino.is_dir():
        return jsonify({"error": "No encontrado"}), 404
    if not destino.exists() and not (DASHBOARD / f"{recurso}.html").exists():
        return jsonify({"error": "No encontrado"}), 404
    if not destino.exists():
        recurso = f"{recurso}.html"
    return send_from_directory(DASHBOARD, recurso)


if __name__ == "__main__":
    if not DASHBOARD.exists():
        print(f"No existe la carpeta del dashboard: {DASHBOARD}")
        sys.exit(1)

    print(f"Dashboard en  http://127.0.0.1:{PUERTO}")
    print(f"Sirviendo     {DASHBOARD}")
    print("Ctrl+C para detener.\n")
    app.run(host="127.0.0.1", port=PUERTO, debug=False, threaded=True)
