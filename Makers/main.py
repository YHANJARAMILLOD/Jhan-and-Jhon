"""
Punto de entrada: procesa transacciones nuevas y guarda el resultado en SQLite.

    python main.py "Pagué 45.900 COP a Netflix" --cliente cliente_001
    python main.py --archivo transacciones.txt --cliente cliente_001
    python main.py --listar --cliente cliente_001
    python main.py --resumen --cliente cliente_001
    python main.py --borrar --cliente cliente_001
"""
import argparse
import json
import sys
from pathlib import Path
from Pipeline.pipeline import procesar_movimiento
from Entrada.entrada import ArchivoIlegible, leer_lineas
from Almacenamiento.almacenamiento import borrar_cliente, guardar_linea, id_extracto, obtener_movimientos_cliente
from Exportacion.exportacion import VISTA_TODO, construir_vista, exportar_dashboard
from Resumen.resumen import lectura, metricas_para_lectura
from Revision.revision import elementos_revision


def leer_transacciones(args):
    """
    Lista de (extracto_id, número de línea, texto).

    Usa el mismo esquema de ids que el servidor, así que un archivo procesado
    por terminal y luego por la web no entra dos veces:
    - un --archivo es un extracto, con id sacado de su contenido;
    - cada texto suelto es su propio extracto, con id sacado de su texto;
    - --extracto fuerza un id común, y entonces la posición distingue líneas.
    """
    transacciones = [
        (args.extracto or id_extracto(texto), posicion if args.extracto else 1, texto)
        for posicion, texto in enumerate(args.textos, start=1)
    ]
    if args.archivo:
        ruta = Path(args.archivo)
        contenido = ruta.read_bytes()
        extracto = args.extracto or id_extracto(contenido)
        for numero, linea in leer_lineas(ruta.name, contenido):
            transacciones.append((extracto, numero, linea))
    return transacciones


def main():
    parser = argparse.ArgumentParser(description="Analiza transacciones bancarias y guarda el resultado en SQLite.")
    parser.add_argument("textos", nargs="*", help="Una o varias transacciones entre comillas.")
    parser.add_argument("--archivo", help="Archivo de texto con una transacción por línea (# para comentarios).")
    parser.add_argument("--cliente", help="Id del cliente al que pertenecen las transacciones.")
    parser.add_argument("--extracto", help="Id del extracto. Por defecto se genera uno por transacción.")
    parser.add_argument("--no-guardar", action="store_true", help="Solo muestra el resultado, sin guardar.")
    parser.add_argument("--sin-rag", action="store_true", help="Revisa la categoría sin ejemplos del RAG.")
    parser.add_argument("--listar", action="store_true", help="Muestra los movimientos guardados del cliente.")
    parser.add_argument("--resumen", action="store_true", help="Genera el resumen financiero del cliente y termina.")
    parser.add_argument("--periodo", choices=("mes", "anio"), default="mes", help="Granularidad del resumen (por defecto: mes).")
    parser.add_argument("--metricas", action="store_true", help="Con --resumen, muestra también las cifras usadas.")
    parser.add_argument("--vista", default="todo", help="Con --resumen: 'todo' (por defecto) o un mes, como 2026-10.")
    parser.add_argument("--exportar", action="store_true", help="Escribe el JSON que consume el dashboard y termina.")
    parser.add_argument("--salida", help="Ruta del JSON exportado (por defecto: dashboard/datos.json).")
    parser.add_argument("--sin-texto", action="store_true", help="Con --exportar, omite el resumen redactado por Groq.")
    parser.add_argument("--borrar", action="store_true", help="Borra todos los movimientos del --cliente. Pide confirmación.")
    args = parser.parse_args()

    if args.listar:
        if not args.cliente:
            parser.error("--listar necesita --cliente.")
        print(json.dumps(obtener_movimientos_cliente(args.cliente), ensure_ascii=False, indent=2))
        return 0

    if args.borrar:
        if not args.cliente:
            parser.error("--borrar necesita --cliente.")
        cantidad = len(obtener_movimientos_cliente(args.cliente))
        if not cantidad:
            print(f"'{args.cliente}' no tiene movimientos guardados. No hay nada que borrar.")
            return 0
        respuesta = input(f"Se borrarán {cantidad} movimientos de '{args.cliente}'. "
                          f"No se puede deshacer. ¿Continuar? [s/N] ")
        if respuesta.strip().lower() not in ("s", "si", "sí"):
            print("Cancelado. No se borró nada.")
            return 0
        borrados = borrar_cliente(args.cliente)
        print(f"Borrados {borrados} movimientos de '{args.cliente}'.")

        # Si el dashboard mostraba a este titular, su export ya no refleja la
        # base: se retira para no seguir mostrando cifras de datos borrados.
        export = Path(__file__).resolve().parent.parent / "dashboard" / "datos.json"
        try:
            if json.loads(export.read_text(encoding="utf-8")).get("cliente_id") == args.cliente:
                export.unlink()
                print("El estado de cuenta mostraba a este titular: se retiró dashboard/datos.json.")
        except (OSError, ValueError):
            pass
        return 0

    if args.exportar:
        if not args.cliente:
            parser.error("--exportar necesita --cliente.")
        try:
            ruta, datos = exportar_dashboard(
                args.cliente, args.salida, args.periodo, incluir_texto=not args.sin_texto
            )
        except Exception as error:
            print(f"ERROR {type(error).__name__}: {error}")
            return 1
        todo = datos["vistas"][VISTA_TODO]
        print(f"Exportado a {ruta}")
        print(f"  {todo['total_movimientos']} movimientos en {len(datos['periodos_disponibles'])} periodos, "
              f"{len(todo['categorias_egreso'])} categorías de egreso, "
              f"{len(todo['anomalias'])} anomalías, "
              f"{len(datos['revision']['pendientes'])} para revisión")
        guardada = datos["lecturas"].get(VISTA_TODO)
        if not guardada:
            print("  (sin lectura redactada)")
        elif not guardada["vigente"]:
            print("  (la lectura guardada no corresponde a las cifras actuales)")
        return 0

    if args.resumen:
        if not args.cliente:
            parser.error("--resumen necesita --cliente.")
        try:
            vista = construir_vista(args.cliente, args.vista, args.periodo)
            revision = elementos_revision(args.cliente)
            resultado = lectura(args.cliente, args.vista, vista, revision, forzar=True)
        except Exception as error:
            print(f"ERROR {type(error).__name__}: {error}")
            return 1
        if args.metricas:
            print(json.dumps(metricas_para_lectura(vista, revision), ensure_ascii=False, indent=2))
            print()
        print(resultado["texto"])
        return 0

    try:
        transacciones = leer_transacciones(args)
    except ArchivoIlegible as error:
        parser.error(str(error))
    if not transacciones:
        parser.error("Indica al menos una transacción o un --archivo.")
    if not args.no_guardar and not args.cliente:
        parser.error("Para guardar indica --cliente (o usa --no-guardar).")

    fallidas = 0
    guardados = 0
    for extracto_id, numero, texto in transacciones:
        print(f"\n=== {texto}")
        try:
            resultado = procesar_movimiento(texto, usar_rag=not args.sin_rag)
        except Exception as error:
            fallidas += 1
            print(f"ERROR {type(error).__name__}: {error}")
            continue

        print(json.dumps(resultado["revisado"], ensure_ascii=False, indent=2))
        if not args.no_guardar:
            # Cada línea reemplaza solo sus propias filas, así que guardar al
            # momento es seguro y no se pierde nada si el proceso se corta.
            guardados += guardar_linea(args.cliente, extracto_id, numero, texto, resultado["revisado"])

    if not args.no_guardar:
        print(f"\nGuardados {guardados} movimientos (cliente={args.cliente}).")

    print(f"\nProcesadas {len(transacciones) - fallidas} de {len(transacciones)} transacciones.")
    return 1 if fallidas else 0


if __name__ == "__main__":
    sys.exit(main())
