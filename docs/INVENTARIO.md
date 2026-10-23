# Inventario local de extratos e faturas

A primeira fatia funcional examina arquivos locais **somente em modo de leitura**. Identifica extensoes, conta arquivos e calcula hash SHA-256 para indicar documentos de conteudo identico.

Nao interpreta transacoes e nao cria historico, nao utiliza a rede e nao acessa o Google Sheets.

## Estrutura da pasta privada

Exemplo ficticio:

~~~text
C:\\Financeiro\\ExtratosFaturas\\
  2026\\
    exemplo.csv
    exemplo.ofx
  2027\\
    exemplo.xlsx
~~~

A pasta real **deve ficar fora do repositorio Git**. Apenas arquivos diretamente nas pastas numericas AAAA sao examinados. O programa nao percorre subpastas aninhadas, nem links simbolicos.

## Executar no Windows (PowerShell)

~~~powershell
$env:PYTHONPATH = "src"
py -3 -m importador_extratos --pasta "C:\\Financeiro\\ExtratosFaturas"
Remove-Item Env:PYTHONPATH
~~~

Formatos candidatos: CSV, OFX e XLSX, identificados pela extensao. PDFs e demais arquivos sao ignorados. **Nenhum desses formatos ainda e interpretado.**

A saida exibe apenas contagens: pastas anuais, arquivos candidatos, possiveis repeticoes e itens ignorados. Nao mostra nomes, caminhos, hashes, valores ou detalhes de transacoes.

Hashes iguais indicam **arquivos potencialmente repetidos**, nunca movimentos financeiros comprovadamente repetidos. Nada e descartado.

A analise se repete a cada execucao; persistencia, classificacao, previa de transacoes, autenticacao Google e gravacao na planilha ficam para etapas posteriores.
