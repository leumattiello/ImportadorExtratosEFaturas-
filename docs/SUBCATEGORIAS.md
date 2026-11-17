# RF-065 / P8 — Cadastro de subcategorias

Etapa 1: **módulo isolado, sem alterações no fluxo de gravação**.

A especificação foi aprovada em 17/11/2026 e está documentada na aba
privada `Melhorias` (seção 16). Este documento público contém apenas
regras genéricas, sem extratos, transações ou identificadores reais.

## Fonte do cadastro

Ler `M2:T36` das 12 abas mensais. Dezembro é a referência de consistência.
As seis categorias vêm **da posição** da subcategoria:

| Faixa | Categoria |
|---|---|
| M3:M18 | Habitação |
| O3:O18 | Alimentação |
| Q3:Q18 | Transportes |
| S3:S18 | Financeiras e Impostos |
| M21:M36 | Transferências |
| O21:O36 | Despesas Gerais |

Ignorar nomes vazios e o curinga terminal `*` usado nas fórmulas
`SUMIF`. Não substituir essas fórmulas por `SUMIFS`; o prefixo é
suficiente para identificar a subcategoria.

## Classificação

Uma descrição já iniciada por `Subcategoria - ` mantém o prefixo.
Caso contrário, o usuário deve escolher uma subcategoria existente,
resultando em `Subcategoria - descrição original`. A categoria
contábil é inferida da posição, sem pergunta adicional.

Nomes duplicados, prefixos potencialmente conflitantes, cabeçalhos
incompatíveis ou cadastros divergentes entre meses impedem
classificação automática. Nunca escolher categorias genéricas por
omissão. Débitos, créditos, competência, estornos, receitas e
transferências patrimoniais mantêm suas regras próprias.

## Escopo desta PR

Esta PR introduz funções puras `carregar_catalogo` e
`classificar_descricao` em `subcategorias.py`, além de testes
sintéticos. **Ainda não lê automaticamente o cadastro pela API do
Google Sheets, não muda as perguntas do terminal e não modifica a
gravação.** A integração ao gateway e à revisão interativa deve ser
realizada em uma PR posterior, com testes de regressão e de natureza
contábil antes de qualquer importação de verdade.

Executar testes:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Nunca incluir dados financeiros reais no repositório público.
