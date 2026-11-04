"""CLI local: somente leitura, sem acesso a rede ou planilhas."""

import argparse
from pathlib import Path
import sys

from .inventario import ErroInventario, inventariar
from .ofx import ErroOFX, ler_ofx


def main(argv: list[str] | tuple[str, ...] = ()) -> int:
    parser = argparse.ArgumentParser(description="Inventario e leitura OFX (somente leitura).")
    parser.add_argument("--pasta", type=Path, help="Raiz privada com subpastas AAAA.")
    parser.add_argument("--analisar-ofx", action="store_true",
                        help="Interpretar transacoes OFX, sem gravar dados.")
    parser.add_argument("--mostrar-detalhes", action="store_true",
                        help="Mostrar dados financeiros privados no terminal local.")
    args = parser.parse_args(argv)
    if args.mostrar_detalhes and not args.analisar_ofx:
        parser.error("--mostrar-detalhes requer --analisar-ofx")
    if args.analisar_ofx and args.pasta is None:
        parser.error("--analisar-ofx requer --pasta")
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
    if args.analisar_ofx:
        arquivos = [a for a in dados.arquivos if a.formato == ".ofx"]
        movimentos = []
        for arquivo in arquivos:
            try:
                movimentos.extend(ler_ofx(arquivo.caminho))
            except ErroOFX as exc:
                print(f"Falha ao interpretar um OFX: {exc}", file=sys.stderr)
                return 1
        print(f"Arquivos OFX analisados: {len(arquivos)}")
        print(f"Movimentacoes OFX identificadas: {len(movimentos)}")
        if args.mostrar_detalhes:
            print("ATENCAO: os detalhes a seguir sao privados e aparecem somente no terminal.")
            for mov in movimentos:
                print(f"{mov.data.isoformat()} | {mov.valor} | {mov.descricao} | "
                      f"FITID: {mov.identificador or '(ausente)'}")
    print("Nenhum lancamento foi importado e nenhum arquivo foi alterado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
