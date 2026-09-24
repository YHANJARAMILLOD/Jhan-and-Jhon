"""
Herramienta de línea de comandos para el RAG del revisor de categoría.

    python rag.py indexar
    python rag.py buscar "Suscripción mensual" --tipo egreso --contraparte Netflix
    python rag.py agregar "Pedido de mercado" --tipo egreso --contraparte Merqueo --categoria compras
"""
import argparse
import json
from Recuperacion.recuperacion import agregar_ejemplo, cargar_indice, recuperar_ejemplos


def _movimiento(args):
    """Arma un movimiento con la contraparte en el campo que le corresponde según el tipo."""
    return {
        "tipo": args.tipo,
        "nombre_remitente": args.contraparte if args.tipo == "ingreso" else None,
        "nombre_destinatario": args.contraparte if args.tipo == "egreso" else None,
        "entidad": args.entidad,
        "descripcion": args.descripcion,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG del revisor de categoría.")
    subparsers = parser.add_subparsers(dest="comando", required=True)

    subparsers.add_parser("indexar", help="Carga los ejemplos semilla y calcula los embeddings que falten.")

    for nombre, ayuda in (("buscar", "Muestra los ejemplos que recibiría el revisor."),
                          ("agregar", "Agrega un ejemplo confirmado por una persona.")):
        sub = subparsers.add_parser(nombre, help=ayuda)
        sub.add_argument("descripcion")
        sub.add_argument("--tipo", choices=["ingreso", "egreso"])
        sub.add_argument("--contraparte")
        sub.add_argument("--entidad")
        if nombre == "buscar":
            sub.add_argument("--k", type=int, default=5)
            sub.add_argument("--umbral", type=float, default=0.0,
                             help="Similitud mínima (0 muestra todo; el pipeline usa RAG_UMBRAL_SIMILITUD).")
        else:
            sub.add_argument("--categoria", required=True)

    args = parser.parse_args()

    if args.comando == "indexar":
        ejemplos, _ = cargar_indice()
        print(f"Índice listo con {len(ejemplos)} ejemplos.")
    elif args.comando == "buscar":
        item = {"es_movimiento_financiero": True, "movimiento": _movimiento(args)}
        (ejemplos,) = recuperar_ejemplos([item], k=args.k, umbral=args.umbral)
        print(json.dumps(ejemplos, ensure_ascii=False, indent=2))
    elif args.comando == "agregar":
        ejemplo_id = agregar_ejemplo(_movimiento(args), args.categoria)
        print(f"Ejemplo guardado: {ejemplo_id}")
