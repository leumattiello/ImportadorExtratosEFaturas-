# Identidade de lancamentos e deduplicacao conservadora (PR #8)

Esta etapa acrescenta a coluna **ID** em F, nas 12 abas mensais da planilha privada de homologacao. Os lancamentos financeiros continuam nas colunas A:E. O espaco de separacao passou para G; os demonstrativos iniciam em H.

O modulo Python `identidade.py` e **puramente funcional**: gera IDs a partir da origem, conta e referencia bancaria; compara uma lista de candidatos com lancamentos existentes passados pelo chamador; e **nao** se autentica no Google Sheets, nao importa, nao modifica o historico, nem imprime dados financeiros. A integracao de consulta das 12 abas sera implementada com a futura etapa de importacao.

## Formato

- Manual: `MAN:2026-0001` (exemplo ficticio). O usuario preenche identificadores manuais unicos. O prefixo `MAN:` identifica uma linha que nao deve ser alterada automaticamente.
- Automatico: `AUTO:BB:CC1:000123` ou `AUTO:NUBANK:CARTAO1:XYZ` (exemplos ficticios). Partes: `AUTO:<origem>:<conta_ou_cartao>:<id_externo>`.
- Os codigos de origem/conta devem ser informados explicitamente, com caracteres maiusculos `A-Z`, numeros, `_` ou `-`. Nao inferir instituicao do nome do arquivo.
- O ID externo e conservado, inclusive zeros a esquerda. Delimitadores presentes nele sao escapados para evitar colisao entre IDs.
- Sem ID externo, nenhum ID automatico e inventado.

## Estados da avaliacao

| Resultado | Condicao principal | Conduta futura |
| --- | --- | --- |
| `NOVO` | ID confiavel nao encontrado, sem coincidencia de data/valor | Candidato a importar |
| `JA_EXISTENTE` | Mesmo ID confiavel e mesmos dados; ocorrencia unica na planilha | Nao importar novamente |
| `CONFLITO` | Mesmo ID com dados diferentes ou duplicado na planilha | Revisao, nunca sobrescrever |
| `REVISAR` | ID ausente, repetido no lote, nao confiavel ou suspeita de sobreposicao | Confirmacao humana posterior |

A verificacao e conservadora: coincidencia de data e valor nao torna dois lancamentos automaticamente iguais. IDs de documento CSV, como `N° documento` no Banco do Brasil, **nao devem ser considerados globalmente unicos** sem comprovacao. Use `id_externo_confiavel=False` para essas origens ate confirmar a semantica do identificador. Mesmo IDs iguais nao confiaveis geram revisao.

Os lancamentos antigos sem ID permanecem intactos, em branco, ate revisao. Nao os marcar automaticamente com `MAN:` nem preencher IDs artificiais.

## Exemplo de uso em codigo (ficticio)

~~~python
from datetime import date
from decimal import Decimal
from importador_extratos.identidade import Lancamento, analisar_identificadores

novo = Lancamento(date(2026, 11, 1), "Compra ficticia", Decimal("-10.50"), "000123")
existentes = [
    Lancamento(date(2026, 11, 1), "Compra ficticia", Decimal("-10.50"),
               "AUTO:BB:CC1:000123")
]
resultado = analisar_identificadores([novo], existentes,
    origem="BB", conta="CC1", id_externo_confiavel=True)
assert resultado[0].situacao == "JA_EXISTENTE"
~~~

## Limitacoes e proximos passos

1. A PR #8 entrega a **estrutura de IDs e a logica de comparacao isolada**, testada com registros sinteticos. Ainda nao implementa consulta remota de IDs reais; ela sera feita antes de qualquer escrita na planilha.
2. A PR #9 adicionara a leitura autorizada das 12 abas, a previa dos lancamentos, perguntas `[S/n]` uma a uma com Enter como S, e a opcao `--assumir-sim`. As perguntas nao poderao autorizar sobrescrita de IDs existentes, especialmente os `MAN:`.
3. Antes de gravar, o importador devera verificar novamente os IDs para evitar duplicidades causadas por edicoes concorrentes. Apenas gravacao confirmada podera ser considerada importacao.
4. O historico local de **analises** da PR #6 nao substitui os IDs existentes na planilha.

Nao adicionar planilhas, extratos ou configuracoes privadas ao repositorio publico.
