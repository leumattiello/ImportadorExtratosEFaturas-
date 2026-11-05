# Perfis CSV privados por formato de cabecalho

A leitura CSV pode selecionar automaticamente um mapeamento de colunas para cada arquivo. A identificacao usa **somente os nomes das colunas**, nao o nome do arquivo nem uma suposicao sobre a instituicao. Dois perfis que coincidam provocam erro controlado. Nenhum extrato e alterado, nenhuma operacao e enviada ao Google Sheets.

## Configuracao local privada

Crie manualmente um arquivo `perfis.ini` **fora do clone do Git**, ao lado da pasta `ExtratosFaturas`:

~~~text
Financeiro/
  perfis.ini
  ExtratosFaturas/
    2026/
      arquivo.csv
    2027/
      outro.csv
~~~

Exemplo **100% ficticio**, que deve ser adaptado aos cabecalhos do seu CSV:

~~~ini
[perfil:extrato_exemplo]
requer_colunas = Data | Lançamento | Histórico | Valor
descricao = Lançamento
valor = Valor
delimitador = ;

[perfil:outro_formato]
requer_colunas = Data | Texto livre | Entrada | Saída
descricao = Texto livre
credito = Entrada
debito = Saída
delimitador = ;
~~~

Em `requer_colunas`, separe os cabecalhos por `|`. Indique ao menos duas colunas distintas. A selecao considera **todas** as colunas exigidas; escolha combinacoes que distingam efetivamente cada layout. O nome da secao (como `perfil:extrato_exemplo`) e apenas um identificador local; nao comprova a instituicao.

Os campos opcionais de cada perfil sao `data`, `descricao`, `valor`, `credito`, `debito`, `identificador`, `delimitador` e `pular_linhas`. Quando necessario, `pular_linhas` determina quantas linhas introdutorias precedem o cabecalho. Nao combine `valor` com `credito` ou `debito`.

**Nao publique seu `perfis.ini` no GitHub.** Ele pode conter cabecalhos especificos de um banco; o exemplo acima e sintetico.

## Executar no Ubuntu

~~~bash
cd "$HOME/Projetos/ImportadorExtratosEFaturas-"
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m importador_extratos --pasta "$HOME/Financeiro/ExtratosFaturas" --analisar-csv
~~~

Se existir `$HOME/Financeiro/perfis.ini`, ele sera usado automaticamente. Para escolher um arquivo privado em outro local, use `--perfis "/caminho/privado/perfis.ini"`. Sem arquivo de perfis, continuam funcionando os parametros antigos, como `--csv-coluna-descricao 'Lançamento'`.

Para ignorar perfis temporariamente e usar parametros manuais, acrescente `--sem-perfis`. A configuracao de perfis e os parametros manuais nao podem ser combinados na mesma execucao sem `--sem-perfis`.

No Windows, use a mesma opcao `--analisar-csv` com Python e uma pasta raiz apropriada. O parser e compativel com Python 3.10 ou superior.

A saida padrao continua mostrando apenas contagens; nao exibe nomes, caminhos ou dados financeiros. Nao use `--mostrar-detalhes` ao copiar resultados para chats ou PRs.

## Limites

A configuracao foi concebida para identificar **layouts de CSV**. Dois bancos com cabecalhos identicos nao podem ser distinguidos somente por eles: nesses casos, a origem devera ser determinada de maneira explicita em etapa posterior. Se nenhum perfil servir, a leitura falha sem importacao parcial. Esta etapa nao faz classificacao, conciliacao, deduplicacao de movimentacoes, historico persistente ou gravacao na planilha.
