# RF-065 — Etapa 2: integração em revisão

A PR #10 entregou o módulo puro `subcategorias.py`. A PR #11
acrescenta leitura consultiva de M2:T36 das doze abas e conecta a
classificação ao fluxo existente de revisão antes da gravação.

## Comportamento implementado

- `catalogo_gateway.ler_catalogo_subcategorias` consulta as 12 faixas
  via `values.batchGet`, sem gravar nenhuma célula.
- `carregar_catalogo` valida identidade entre meses, cabeçalhos,
  duplicidades e prefixos. Qualquer inconsistência impede o lote.
- No modo `--importar`, cada movimento elegível recebe natureza
  explicitamente informada: **despesa** ou **outra**.
- Para despesa, reconhece prefixo já cadastrado ou pergunta uma
  subcategoria existente, e infere a categoria principal da posição.
  Preserva integralmente a descrição original depois do prefixo.
- Para natureza `outra` (por exemplo, receita ou transferência
  patrimonial), mantém a seleção explícita da contrapartida da aba Dados.
  Não acrescenta prefixo de despesa.
- `--assumir-sim` só funciona com natureza e classificação explicitamente
  informadas: `--natureza despesa --subcategoria ...` ou
  `--natureza outra --categoria ...`.
- Um catálogo modificado durante a revisão cancela a escrita.
  A checagem original de alteração de A:F antes do batch continua ativa.
- `--planejar-importacao` permanece somente leitura e mantém sua
  análise de identidade/duplicidade; ainda não faz classificação
  financeira, que é feita na fase de revisão anterior à escrita.

## Exemplo para lote homogêneo de despesas

```bash
PYTHONPATH=src python3 -m importador_extratos \
  --pasta "$HOME/Financeiro/ExtratosFaturas" \
  --arquivo "$HOME/Financeiro/ExtratosFaturas/2026/EXEMPLO.ofx" \
  --ano-competencia 2026 --mes-competencia 11 \
  --planilha-id ID_DA_COPIA_PRIVADA \
  --origem BB --conta CC1 --conta-planilha "CONTA_EXATA" \
  --natureza despesa --subcategoria Energia --planejar-importacao
```

A opção `--planejar-importacao` **não grava**. Na homologação,
substituir `--planejar-importacao` por `--importar` somente em uma
planilha fictícia e com documentos sintéticos. Na revisão interativa de
lotes heterogêneos, omitir `--natureza` e `--subcategoria`: cada
movimento terá perguntas específicas. Não usar `-y` para esses lotes.

## Limitações e segurança

O sinal bancário não é suficiente para inferir natureza contábil:
estornos, pagamentos de cartão, receitas e transferências patrimoniais
exigem decisão explícita da contrapartida. O fluxo existente ainda
representa movimentos com os campos de débito/crédito usados na PR #9;
precisa de homologação contábil antes de importar cartões e transações
complexas. Os testes novos são sintéticos; ainda é necessário executar
a suíte e homologar TA-20/TA-21 com uma planilha isolada antes de
autorizar importações reais.

Nunca enviar à PR extratos, histórico privado, planilha nem tokens.
