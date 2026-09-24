"""
Punto de entrada: procesa transacciones nuevas y guarda el resultado en SQLite.

    python main.py "Pagué 45.900 COP a Netflix" --cliente cliente_001
    python main.py --archivo transacciones.txt --cliente cliente_001
    python main.py --listar --cliente cliente_001
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from Pipeline.pipeline import procesar_movimiento
from Almacenamiento.almacenamiento import guardar_movimientos, obtener_movimientos_cliente


def leer_transacciones(args):
    """
    Devuelve una lista de (extracto_id, texto).

    Sin --extracto, el id sale del propio texto: reprocesar la misma
    transacción sobrescribe sus filas en lugar de duplicarlas.
    """
    textos = list(args.textos)
    if args.archivo:
        lineas = Path(args.archivo).read_text(encoding="utf-8").splitlines()
        textos += [linea.strip() for linea in lineas if linea.strip() and not linea.lstrip().startswith("#")]

    return [
        (args.extracto or "txt-" + hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16], texto)
        for texto in textos
    ]


def main():
    parser = argparse.ArgumentParser(description="Analiza transacciones bancarias y guarda el resultado en SQLite.")
    parser.add_argument("textos", nargs="*", help="Una o varias transacciones entre comillas.")
    parser.add_argument("--archivo", help="Archivo de texto con una transacción por línea (# para comentarios).")
    parser.add_argument("--cliente", help="Id del cliente al que pertenecen las transacciones.")
    parser.add_argument("--extracto", help="Id del extracto. Por defecto se genera uno por transacción.")
    parser.add_argument("--no-guardar", action="store_true", help="Solo muestra el resultado, sin guardar.")
    parser.add_argument("--sin-rag", action="store_true", help="Revisa la categoría sin ejemplos del RAG.")
    parser.add_argument("--listar", action="store_true", help="Muestra los movimientos guardados del cliente.")
    args = parser.parse_args()

    if args.listar:
        if not args.cliente:
            parser.error("--listar necesita --cliente.")
        print(json.dumps(obtener_movimientos_cliente(args.cliente), ensure_ascii=False, indent=2))
        return 0

    transacciones = leer_transacciones(args)
    if not transacciones:
        parser.error("Indica al menos una transacción o un --archivo.")
    if not args.no_guardar and not args.cliente:
        parser.error("Para guardar indica --cliente (o usa --no-guardar).")

    fallidas = 0
    # Los movimientos se agrupan por extracto y se guardan al final: guardar
    # un extracto reemplaza sus filas, así que guardar texto por texto con el
    # mismo --extracto dejaría solo el último.
    por_extracto = {}
    for extracto_id, texto in transacciones:
        print(f"\n=== {texto}")
        try:
            resultado = procesar_movimiento(texto, usar_rag=not args.sin_rag)
        except Exception as error:
            fallidas += 1
            print(f"ERROR {type(error).__name__}: {error}")
            continue

        print(json.dumps(resultado["revisado"], ensure_ascii=False, indent=2))
        # "revisado" ya está anonimizado y trae la categoría corregida.
        por_extracto.setdefault(extracto_id, []).extend(resultado["revisado"])

    if not args.no_guardar:
        for extracto_id, movimientos in por_extracto.items():
            guardados = guardar_movimientos(args.cliente, extracto_id, movimientos)
            print(f"Guardados {guardados} movimientos (cliente={args.cliente}, extracto={extracto_id}).")

    print(f"\nProcesadas {len(transacciones) - fallidas} de {len(transacciones)} transacciones.")
    return 1 if fallidas else 0


if __name__ == "__main__":
    sys.exit(main())
