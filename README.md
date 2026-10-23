# Importador de Extratos e Faturas

Projeto Python para futura importacao incremental de extratos e faturas na contabilidade privada do Google Sheets.

**Estado:** apenas estrutura segura. Ainda NAO existem leitura de extratos, conexao ao Google Sheets ou escrita financeira.

## Arquitetura aprovada

- Programa Python executado localmente no notebook Windows.
- Fonte: pasta local privada com subpastas por competencia, como 2026 e 2027.
- Os documentos originais permanecerao intactos na pasta.
- Importacoes futuras identificarao arquivos e movimentos ja processados, inclusive lancamentos manuais.
- Itens novos serao revisados e aprovados antes de serem acrescentados a planilha, sem sobrescrita.
- Conciliacao bancaria ficara para uma etapa posterior.

## Repositorio publico: privacidade obrigatoria

Nunca versionar extratos ou faturas reais, planilhas financeiras, nomes e identificadores pessoais, senhas, tokens, credenciais Google, configuracoes locais ou historicos de importacao.

O .gitignore e uma protecao complementar e nao impede que dados sejam publicados se forem adicionados a arquivos permitidos, forcados com git add -f ou enviados em commits anteriores.

Leia docs/PRIVACIDADE.md antes de contribuir. Use exclusivamente exemplos totalmente ficticios.

## Teste no Windows (PowerShell)

Requisitos: Python 3.10+ e Git, sem bibliotecas de terceiros para esta etapa.

~~~powershell
$env:PYTHONPATH = "src"
py -3 -m importador_extratos
py -3 -m unittest discover -s tests -v
Remove-Item Env:PYTHONPATH
~~~

A execucao inicial apenas imprime uma mensagem; nao abre arquivos financeiros e nao modifica planilhas.

## Revisao antes de publicar

~~~powershell
git status --short
git diff --cached --name-only
git diff --cached
~~~

Criar uma branch por mudanca e solicitar revisao por pull request antes do merge.

O repositorio contem LICENSE com o texto da GPLv3; preservar a licenca existente.
