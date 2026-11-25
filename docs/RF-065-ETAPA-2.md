# RF-065 — Etapa 2 (integração incremental)

A PR #10 entregou o módulo puro `subcategorias.py`. Esta entrega inicia
a integração com uma **leitura consultiva** dos cadastros M2:T36 nas doze
abas mensais, sem acesso a extratos nem mudança na gravação.

## Implementado neste incremento

- `catalogo_gateway.ler_catalogo_subcategorias(servico, planilha_id)`
  consulta as doze faixas em um único `values.batchGet`, apenas leitura.
- Normaliza linhas e colunas vazias omitidas pela API, preservando posições.
- Reutiliza `carregar_catalogo` da PR #10: dezembro como referência,
  cabeçalhos e posições, nomes duplicados e prefixos conflitantes.
- Recusa retornos incompletos, intervalos incorretos e divergências.
- Testes exclusivamente sintéticos, sem chamadas de rede.

## Ainda não integrado

**Não há alteração na CLI ou no fluxo de revisão e gravação.** A próxima
alteração da PR precisa carregar este catálogo no fluxo, reconhecer
prefixos e perguntar a *subcategoria* só para despesas aplicáveis.
É indispensável distinguir receitas, transferências patrimoniais,
pagamentos de faturas e estornos antes da classificação; a simples
presença de valor positivo ou negativo não basta para essa distinção.
Não escolher `Desconhecido` por omissão e não deixar `-y` escolher
subcategorias silenciosamente.

Testes locais:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Até a homologação de TA-20/TA-21 e regressões, manter o uso de dados
sintéticos e não executar importação real com esta funcionalidade.
