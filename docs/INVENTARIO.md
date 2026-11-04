# Inventario local de extratos e faturas

A funcao de **inventario** examina arquivos locais somente em modo de leitura, calcula assinaturas SHA-256 e informa quantos arquivos possuem conteudo identico.

O inventario isolado nao interpreta transacoes, nao cria historico, nao usa a rede e nao acessa o Google Sheets. Leituras OFX e CSV existem como **opcoes explicitas**, descritas em [OFX.md](OFX.md) e [CSV.md](CSV.md).

## Pasta privada (exemplo ficticio)

~~~text
C:\Financeiro\ExtratosFaturas\
  2026\
    exemplo.csv
    exemplo.ofx
  2027\
    exemplo.xlsx
~~~

A pasta real deve ficar fora do repositorio Git. Sao examinados arquivos diretamente nas pastas com nomes AAAA. Nao ha varredura de subpastas aninhadas nem de links simbolicos.

## Windows (PowerShell)

~~~powershell
$env:PYTHONPATH = "src"
py -3 -m importador_extratos --pasta "C:\Financeiro\ExtratosFaturas"
Remove-Item Env:PYTHONPATH
~~~

Formatos candidatos: CSV, OFX e XLSX, identificados pela extensao. PDF e demais tipos sao ignorados. O **inventario** nao interpreta nenhum desses formatos; use `--analisar-csv` ou `--analisar-ofx` para suas respectivas leituras, ainda sem gravacao.

A saida do inventario traz apenas contagens, nunca nomes, caminhos, hashes, valores ou detalhes de transacoes. Hashes iguais indicam arquivos com conteudo igual, nao comprovam duplicidade de movimentos bancarios e nao levam ao descarte automatico.

Persistencia e deduplicacao de transacoes ainda serao implementadas em etapas futuras.
