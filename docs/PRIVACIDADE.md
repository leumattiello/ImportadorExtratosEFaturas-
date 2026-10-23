# Politica de privacidade do projeto

Este repositorio e PUBLICO e nunca deve armazenar dados financeiros verdadeiros.

## Nao publicar

- Extratos, faturas, PDFs, planilhas financeiras, contracheques, dados pessoais ou bancarios.
- Numeros de contas e cartoes, CPF, chaves Pix, referencias reais de transacoes.
- Senhas, tokens, arquivos OAuth, chaves privadas, .env e configuracoes privadas.
- Historicos de importacao, estado de deduplicacao, dumps, caches e logs reais.

## Praticas obrigatorias

1. Manter pasta de documentos e historico de processamento fora do clone do repositorio.
2. Abrir documentos locais apenas em modo leitura quando o importador for desenvolvido.
3. Criar testes com dados integralmente inventados: nao copiar, anonimizar ou recortar extratos reais.
4. Nao incluir conteudo de extratos, valores, tokens ou identificadores pessoais nos logs do CI ou da PR.
5. Guardar configuracao e autenticacao Google em local privado e nao versionado.
6. Conferir os arquivos de cada commit com git status --short, git diff --cached --name-only e git diff --cached.
7. Abrir branch e PR para revisao antes de alterar main.

## Limites do .gitignore

.gitignore ajuda a evitar inclusao acidental. NAO protege dados escritos dentro de codigo ou documentacao, arquivos adicionados com git add -f nem dados publicados anteriormente no historico Git.

Em caso de vazamento: interromper novas publicacoes, revogar credenciais comprometidas e tratar o historico. Apagar um arquivo num commit posterior nao apaga seu historico.

Esta primeira versao nao le extratos, nao acessa a planilha e nao faz nenhuma importacao.
