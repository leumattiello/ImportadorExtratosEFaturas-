"""CLI local: somente leitura, sem acesso a rede ou planilhas."""

import argparse
from pathlib import Path
import sys

from .inventario import ErroInventario, inventariar


def main(argv: list[str] | tuple[str, ...] = ()) -> int:
    parser = argparse.ArgumentParser(description="Inventario local (somente leitura).")
    parser.add_argument("--pasta", type=Path, help="Raiz privada com subpastas AAAA.")
    args = parser.parse_args(argv)
    if args.pasta is None:
        print("Importador de Extratos e Faturas - estrutura inicial.")
        print("Nenhum arquivo financeiro e lido e nenhuma planilha e modificada.")
        return 0
    try:
        dados = inventariar(args.pasta)
    except ErroInventario as exc:
        print(f"Falha no inventario: {exc}", file=sys.stderr)
        return 1
    print("Inventario concluido em modo somente leitura.")
    print(f"Pastas anuais: {len(dados.anos)}")
    print(f"Arquivos candidatos: {len(dados.arquivos)}")
    print(f"Possiveis repeticoes (hash identico): {dados.possiveis_repetidos}")
    print(f"Itens ignorados: {dados.ignorados}")
    print("Nenhum lancamento foi importado e nenhum arquivo foi alterado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
