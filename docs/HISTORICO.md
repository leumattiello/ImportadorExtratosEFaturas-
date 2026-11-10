# Historico simples de leitura (RF-062 - etapa inicial)

O importador pode registrar **tentativas de analise**, opcionalmente, em um arquivo CSV local e privado, sem banco de dados. O historico nao e uma lista de lancamentos contabeis nem comprova importacao concluida.

## Onde fica

Ao executar sobre `~/Financeiro/ExtratosFaturas`, a opcao `--registrar-historico` cria ou acrescenta registros em:

`~/Financeiro/historico_importacoes.csv`

O arquivo fica **fora do repositorio Git**, no mesmo nivel de `perfis.ini` e `ExtratosFaturas`.

Exemplo de uso no Ubuntu:

~~~bash
cd "$HOME/Projetos/ImportadorExtratosEFaturas-"
PYTHONPATH=src python3 -m importador_extratos \
  --pasta "$HOME/Financeiro/ExtratosFaturas" \
  --analisar-ofx --analisar-csv --registrar-historico
~~~

No Windows, pode-se utilizar a mesma opcao com `py -3 -m importador_extratos` e o caminho local correspondente.

Sem `--registrar-historico`, o programa continua funcionando **sem criar ou alterar nenhum arquivo**. Com ela, somente o arquivo de historico sera criado ou modificado; os extratos originais continuarao intactos.

## Estrutura

O CSV utiliza delimitador ponto-e-virgula e as colunas:

- `processado_em`: horario local ISO 8601 com fuso;
- `arquivo`: nome e subpasta anual relativos a `ExtratosFaturas` (pode conter dados privados);
- `formato`: `.csv` ou `.ofx`;
- `resultado`: `ANALISADO` ou `ERRO`;
- `movimentacoes`: total lido quando a interpretacao teve sucesso; zero na falha;
- `sha256`: hash do arquivo original, calculado no inventario.

**ANALISADO nao significa APROVADO nem IMPORTADO.** Nenhuma linha deste historico significa que foi gravado um lancamento no Google Sheets. Um arquivo pode ser analisado novamente, gerando outra linha. Nenhuma transacao e deduplicada ou descartada automaticamente.

Se uma leitura falhar, registra-se `ERRO` (quando possivel), mantendo a mensagem de falha sem dados financeiros na tela. Em uma execucao com varios arquivos, o processamento atual e interrompido ao primeiro erro. Se o proprio historico estiver indisponivel, o comando falha explicitamente.

## Privacidade e seguranca

O registro fica fora do Git. No Linux, novos arquivos sao criados com permissao restrita `0600`; arquivos preexistentes com permissoes excessivas sao recusados. O programa nao segue um link simbolico como arquivo de historico. Antes de marcar `ANALISADO`, confere novamente o tamanho e hash do arquivo de origem.

O arquivo de historico **contem nomes reais de arquivos e hashes**, portanto e privado. Nao anexe, publique ou compartilhe esse CSV nem o resultado de `--mostrar-detalhes`.

Esta implementacao e destinada a uma unica instancia local do importador. Nao e um mecanismo de bloqueio de concorrencia nem uma transacao atomica com o Google Sheets. Para homologacao, execute em apenas um terminal de cada vez. Os testes usam exclusivamente exemplos ficticios.

## Proximas etapas

- Criar identificacao de movimentos e deteccao de sobreposicoes entre extratos;
- Comparar candidatos com registros existentes na planilha, inclusive manuais;
- Implementar previa e aprovacao humana;
- Somente entao registrar importacao efetivamente concluida, apos confirmacao remota.

**O historico nao autoriza ignorar automaticamente arquivos marcados ANALISADO**: eles ainda nao foram importados.
