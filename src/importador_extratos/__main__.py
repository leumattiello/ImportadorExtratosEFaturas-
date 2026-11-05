"""CLI local: somente leitura, sem acesso a rede ou planilhas."""

import argparse
from pathlib import Path
import sys

from .inventario import ErroInventario, inventariar
from .leitor_csv import ColunasCSV, ErroCSV, ler_csv
from .ofx import ErroOFX, ler_ofx
from .perfis_csv import ErroPerfis, ler_perfis, selecionar_perfil


def main(argv: list[str] | tuple[str, ...] = ()) -> int:
    parser = argparse.ArgumentParser(description="Inventario e leitura CSV/OFX (somente leitura).")
    parser.add_argument("--pasta", type=Path, help="Raiz privada com subpastas AAAA.")
    parser.add_argument("--analisar-ofx", action="store_true", help="Interpretar transacoes OFX.")
    parser.add_argument("--analisar-csv", action="store_true", help="Interpretar transacoes CSV.")
    parser.add_argument("--mostrar-detalhes", action="store_true",
                        help="Mostrar dados financeiros privados no terminal local.")
    parser.add_argument("--csv-delimitador", choices=(";", ",", "tab"),
                        help="Delimitador CSV se a deteccao automatica falhar.")
    parser.add_argument("--csv-pular-linhas", type=int, default=0,
                        help="Ignorar linhas introdutorias antes do cabecalho CSV.")
    parser.add_argument("--perfis", type=Path,
                        help="Arquivo INI privado de perfis CSV, fora do repositorio.")
    parser.add_argument("--sem-perfis", action="store_true",
                        help="Desabilitar descoberta de perfis locais nesta execucao.")
    for opcao in ("data", "descricao", "valor", "credito", "debito", "identificador"):
        parser.add_argument(f"--csv-coluna-{opcao}",
                            help=f"Nome literal do cabecalho CSV para {opcao}.")
    args = parser.parse_args(argv)
    if args.mostrar_detalhes and not (args.analisar_ofx or args.analisar_csv):
        parser.error("--mostrar-detalhes requer --analisar-ofx ou --analisar-csv")
    if (args.analisar_ofx or args.analisar_csv) and args.pasta is None:
        parser.error("--analisar-ofx/--analisar-csv requer --pasta")
    if args.csv_pular_linhas < 0:
        parser.error("--csv-pular-linhas nao pode ser negativo")
    if args.perfis is not None and not args.analisar_csv:
        parser.error("--perfis requer --analisar-csv")
    if args.sem_perfis and args.perfis is not None:
        parser.error("--sem-perfis nao pode ser combinado com --perfis")
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
                print(f"{mov.data.isoformat()} | {mov.valor} | {mov.descricao!r} | "
                      f"FITID: {mov.identificador!r}")
    if args.analisar_csv:
        arquivos = [a for a in dados.arquivos if a.formato == ".csv"]
        config = ColunasCSV(
            data=args.csv_coluna_data,
            descricao=args.csv_coluna_descricao,
            valor=args.csv_coluna_valor,
            credito=args.csv_coluna_credito,
            debito=args.csv_coluna_debito,
            identificador=args.csv_coluna_identificador,
        )
        config_manual = (
            args.csv_delimitador is not None or args.csv_pular_linhas != 0 or
            any(getattr(config, campo) is not None for campo in
                ("data", "descricao", "valor", "credito", "debito", "identificador"))
        )
        perfis = None
        caminho_perfis = args.perfis or Path(args.pasta).expanduser().parent / "perfis.ini"
        if not args.sem_perfis and (args.perfis is not None or caminho_perfis.exists() or caminho_perfis.is_symlink()):
            if config_manual:
                parser.error("Nao misture perfis CSV com mapeamento manual; use --sem-perfis.")
            try:
                perfis = ler_perfis(caminho_perfis)
            except ErroPerfis as exc:
                print(f"Falha na configuracao CSV: {exc}", file=sys.stderr)
                return 1
        movimentos = []
        for arquivo in arquivos:
            try:
                if perfis is None:
                    opcoes = dict(colunas=config, delimitador=args.csv_delimitador,
                                  pular_linhas=args.csv_pular_linhas)
                else:
                    perfil = selecionar_perfil(arquivo.caminho, perfis)
                    opcoes = dict(colunas=perfil.colunas, delimitador=perfil.delimitador,
                                  pular_linhas=perfil.pular_linhas)
                movimentos.extend(ler_csv(arquivo.caminho, **opcoes))
            except (ErroCSV, ErroPerfis) as exc:
                print(f"Falha ao interpretar um CSV: {exc}", file=sys.stderr)
                return 1
        print(f"Arquivos CSV analisados: {len(arquivos)}")
        print(f"Movimentacoes CSV identificadas: {len(movimentos)}")
        if perfis is not None:
            print(f"Arquivos selecionados por perfil: {len(arquivos)}")
        if args.mostrar_detalhes:
            print("ATENCAO: os detalhes a seguir sao privados e aparecem somente no terminal.")
            for mov in movimentos:
                print(f"{mov.data.isoformat()} | {mov.valor} | {mov.descricao!r} | "
                      f"ID: {mov.identificador!r}")
    print("Nenhum lancamento foi importado e nenhum arquivo foi alterado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
