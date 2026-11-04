# Leitura de movimentacoes OFX (somente leitura)

Esta etapa acrescenta um interpretador inicial para arquivos OFX de extratos bancarios.
Suporta transacoes STMTTRN nas representacoes OFX/SGML e OFX/XML, campos
DTPOSTED, TRNAMT, NAME/MEMO, FITID e TRNTYPE.

**Nao** interpreta faturas de cartao em CSV/XLSX, nao identifica categoria,
nao registra importacoes anteriores, nao compara transacoes com a planilha e
nao envia nada ao Google Sheets.

## Executar no Ubuntu

A pasta privada deve estar fora do clone Git.

~~~bash
cd "$HOME/Projetos/ImportadorExtratosEFaturas-"
git switch feat/leitura-ofx-somente-leitura
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m importador_extratos --pasta "$HOME/Financeiro/ExtratosFaturas" --analisar-ofx
~~~

O ultimo comando mostra apenas a quantidade de arquivos OFX e movimentacoes.
**Nenhum nome, valor, caminho, descricao ou identificador bancario aparece.**

Para inspecionar datas, valores e descricoes no **seu terminal privado**, adicione
`--mostrar-detalhes` ao comando. Nao copie essa saida para issues, PRs, logs
publicos ou conversas. Se precisar compartilhar resultados, informe so as contagens.

## Windows (PowerShell)

~~~powershell
$env:PYTHONPATH = "src"
py -3 -m importador_extratos --pasta "C:\\Financeiro\\ExtratosFaturas" --analisar-ofx
Remove-Item Env:PYTHONPATH
~~~

O diretorio acima e ilustrativo. Datas e valores sao preservados com
`datetime.date` e `Decimal`. O tamanho maximo de cada OFX e 20 MiB.
Erros de leitura exibem mensagens genericas sem copiar conteudo financeiro.

**Escopo intencionalmente limitado:** OFX fora dos casos suportados ou com
codificacao nao reconhecida pode exigir ajuste especifico posterior.
As transacoes lidas nao sao gravadas e nenhum historico persistente e criado.
