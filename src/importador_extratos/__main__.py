"""Entrada segura: nao le extratos, nao acessa rede e nao grava dados."""


def main() -> int:
    """Exibir apenas o estado do projeto."""
    print("Importador de Extratos e Faturas - estrutura inicial.")
    print("Nenhum arquivo financeiro e lido e nenhuma planilha e modificada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
