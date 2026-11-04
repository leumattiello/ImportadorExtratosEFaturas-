# Leitura local de extratos CSV (somente leitura)

O importador interpreta transacoes em arquivos CSV estruturados, com cabecalho. As datas e os valores sao preservados como `date` e `Decimal`; **a interpretacao nao gera lancamentos na planilha**.

## Ubuntu

A pasta financeira deve estar **fora do clone Git**. Atualize e selecione a branch da PR antes de testar:

```bash
cd "$HOME/Projetos/ImportadorExtratosEFaturas-"
git fetch origin
git switch --track origin/feat/leitura-csv-somente-leitura
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m importador_extratos --pasta "$HOME/Financeiro/ExtratosFaturas" --analisar-csv
```

O ultimo comando **mostra somente contagens** (arquivos e movimentacoes). Nomes, caminhos, descricoes e valores nao aparecem na saida. O parametro `--mostrar-detalhes` e opcional e exibe dados privados **somente no terminal local**; nao compartilhe essa saida.

## Windows / PowerShell

```powershell
$env:PYTHONPATH = "src"
py -3 -m importador_extratos --pasta "C:\Financeiro\ExtratosFaturas" --analisar-csv
Remove-Item Env:PYTHONPATH
```

O caminho do Windows e ilustrativo. Os arquivos sao lidos sem alteracoes e sem serem enviados a nenhum servico.

## Formatos suportados nesta etapa

- Arquivos CSV com linha de cabecalho, delimitados por `;`, `,` ou tabulacao.
- Codificacoes UTF-8 (com ou sem BOM) e Windows-1252; as regras de deteccao sao conservadoras.
- Datas como `dd/mm/aaaa`, `dd-mm-aaaa` e `aaaa-mm-dd`.
- Valores com casas decimais brasileira (`-1.234,56`) ou internacional (`-1,234.56`), **com no maximo duas casas**.
- Colunas `Data`, `Descricao`/`Historico` e `Valor` assinado; ou colunas separadas `Credito` e `Debito` com valores positivos.
- Colunas opcionais de identificador (`ID`, `FITID`, `NSU` etc.).

Nenhuma linha e descartada por suposta duplicidade. Se houver ambiguidade no cabecalho, no valor, na data ou no sinal, o importador **rejeita a leitura**, em vez de inventar resultados.

### Cabecalhos e formatos diferentes

Se o CSV tiver colunas com outros nomes, pode-se informar os nomes exatos usando `--csv-coluna-data`, `--csv-coluna-descricao` e `--csv-coluna-valor`, por exemplo:

```bash
PYTHONPATH=src python3 -m importador_extratos \
  --pasta "$HOME/Financeiro/ExtratosFaturas" --analisar-csv \
  --csv-coluna-data 'Dt. Mov.' \
  --csv-coluna-descricao 'Texto' \
  --csv-coluna-valor 'Quantia'
```

Para arquivos com colunas separadas, use `--csv-coluna-credito` e/ou `--csv-coluna-debito` **no lugar de** `--csv-coluna-valor`. Outros parametros:

- `--csv-delimitador ';'` (ou `','` ou `tab`) para escolher o separador explicitamente;
- `--csv-pular-linhas 1` para pular uma linha introdutoria antes do cabecalho.

A mesma configuracao e aplicada a todos os CSV da pasta. Se houver arquivos de varias instituicoes, cada uma com um layout diferente, sera necessario criar perfis por instituicao em etapa posterior. Nao mova seus arquivos reais para dentro do repositorio Git.

## Limitacoes e seguranca

Esta entrega nao interpreta arquivos PDF/XLSX nem faturas complexas, nao consulta Google Sheets, nao identifica movimentacoes duplicadas entre arquivos, nao mantem historico e nao grava nada na contabilidade. O exercicio de competencia continua sendo definido pela subpasta anual; a data real da transacao e preservada.

Os testes do repositorio utilizam exclusivamente arquivos e transacoes ficticios. A saida padrao nao contem dados financeiros; erros tambem sao resumidos, sem repetir o conteudo de arquivos. Para pedir ajuda com um layout diferente, compartilhe **somente nomes genericos de colunas**, nunca o extrato.
