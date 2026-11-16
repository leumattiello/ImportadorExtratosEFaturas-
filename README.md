# Importador de Extratos e Faturas

Projeto Python para futura importacao incremental de extratos e faturas na contabilidade privada do Google Sheets.

**Estado:** inventario e leitura local de transacoes **OFX e CSV**, somente leitura. **Ainda nao existe gravacao no Google Sheets, classificacao ou protecao de duplicidades entre movimentacoes. O historico CSV de analises pode ser ativado explicitamente, e arquivos previamente analisados sao reconhecidos pelo hash.** Os perfis de CSV por cabecalho estao implementados.

## Arquitetura aprovada

- Programa Python executado localmente no notebook Windows (tambem testavel no Ubuntu).
- Fonte: pasta local privada, **fora do clone Git**, com subpastas por competencia, como `2026/` e `2027/`.
- Os documentos originais permanecem intactos na pasta.
- Futuras importacoes precisarao identificar arquivos e movimentos ja processados, inclusive lancamentos manuais.
- So itens novos e aprovados poderao ser acrescentados na planilha; sem sobrescrita.
- A conciliacao financeira esta prevista para etapa posterior.

## Repositorio publico: privacidade obrigatoria

Nunca versionar extratos/faturas reais, planilhas financeiras, dados pessoais, senhas, tokens, credenciais Google, configuracoes privadas ou historicos de importacao.

O `.gitignore` e protecao complementar, nao garantia. Confira cada diff. Leia [docs/PRIVACIDADE.md](docs/PRIVACIDADE.md).

## Testar no Ubuntu

~~~bash
cd "$HOME/Projetos/ImportadorExtratosEFaturas-"
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m importador_extratos --pasta "$HOME/Financeiro/ExtratosFaturas" --analisar-ofx --analisar-csv
# Historico privado opcional: acrescente --registrar-historico ao comando anterior.
~~~

A saida padrao apresenta **somente contagens**, inclusive arquivos nunca analisados, ja analisados ou com erro anterior, sem revelar nomes, descricoes, identificadores ou valores privados. O programa **nao grava nada**, exceto quando a opcao explicita `--registrar-historico` for utilizada; nesse caso grava somente o historico de analises.

## Testar no Windows (PowerShell)

Requisitos: Python 3.10+ e Git; as leituras atuais usam somente bibliotecas padrao do Python.

~~~powershell
$env:PYTHONPATH = "src"
py -3 -m unittest discover -s tests -v
py -3 -m importador_extratos --pasta "C:\Financeiro\ExtratosFaturas" --analisar-ofx --analisar-csv
Remove-Item Env:PYTHONPATH
~~~

O caminho de exemplo no Windows deve ser ajustado para a pasta privada real.

**Identificadores:** a planilha de homologacao possui uma coluna F (ID) por aba mensal. A geracao e comparacao de IDs estao disponiveis como funcoes de leitura em `identidade.py`; ainda nao ha consulta autenticada nem importacao na planilha. Veja [docs/IDENTIFICADORES.md](docs/IDENTIFICADORES.md).

**Documentacao:** [inventario](docs/INVENTARIO.md), [leitura OFX](docs/OFX.md) [leitura CSV](docs/CSV.md) e [perfis CSV](docs/PERFIS_CSV.md), mais o [historico local](docs/HISTORICO.md). Se o CSV nao corresponder aos cabecalhos conhecidos, veja as opcoes de mapeamento manual em `docs/CSV.md`. Nao envie documentos financeiros para o repositorio.

## Revisao antes de publicar

~~~bash
git status --short
git diff --cached --name-only
git diff --cached
~~~

Criar uma branch por mudanca e solicitar revisao por pull request antes do merge.

O repositorio contem [LICENSE](LICENSE) com o texto da GPLv3; preservar a licenca existente.
