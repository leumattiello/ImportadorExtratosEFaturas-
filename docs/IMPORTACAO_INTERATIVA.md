# Importacao interativa — PR #9

Esta etapa usa a propria planilha como fonte de verdade dos IDs. Nao usa banco de dados.

## Preparacao OAuth (somente maquina local)

1. No Google Cloud habilite a Google Sheets API e crie credenciais OAuth de aplicativo Desktop.
2. Guarde o JSON em ~/Financeiro/google_client_secret.json, com chmod 600 no Ubuntu.
3. O token privado sera criado em ~/Financeiro/token_google.json na primeira autorizacao pelo navegador local.
4. Instale as dependencias opcionais no ambiente virtual: pip install -r requirements-google.txt.
5. A conta autorizada deve ter acesso de editor a COPIA DE HOMOLOGACAO, nunca use producao inicialmente.

## Simulacao obrigatoria antes da gravacao

```bash
PYTHONPATH=src python3 -m importador_extratos \
  --pasta "$HOME/Financeiro/ExtratosFaturas" \
  --arquivo "$HOME/Financeiro/ExtratosFaturas/2026/EXEMPLO.ofx" \
  --ano-competencia 2026 --mes-competencia 11 \
  --planilha-id ID_DA_COPIA_PRIVADA \
  --origem BB --conta CC1 --planejar-importacao
```

Um arquivo OFX/CSV por execucao; o mes e ano de competencia sao explicitos. A data real do documento permanece intacta.
Consulta automaticamente os IDs das doze abas mensais, bem como as contas e categorias na aba Dados.
IDs MAN: e registros antigos sem ID jamais sao alterados ou reclassificados automaticamente.
Ja existente: ignora; conflito de ID, ID ausente ou repetido no lote: bloqueia; coincidencia de data e valor: pergunta [S/n].
Enter responde S nas revisoes. --assumir-sim (ou -y) responde S apenas nas revisoes admissiveis e nunca libera conflitos.
CSV utiliza perfis privados por cabecalho; numeros de documento CSV sao tratados como nao confiaveis, salvo --id-confiavel explicito.

## Gravar apenas depois de homologar a simulacao

Substitua --planejar-importacao por --importar. Acrescente --conta-planilha com o nome exato da conta em Dados!A.
O parametro --categoria atribui a mesma categoria a todo o lote; use apenas em lotes homogeneos.
Sem --categoria, o terminal pergunta a categoria de cada transacao aprovada.
Com -y, --categoria e obrigatoria para evitar classificacoes silenciosas.
Uma despesa registra C=conta origem, D=contrapartida, E=valor positivo; entradas invertem C/D. A=data real, F=ID automatico.
O programa faz confirmacao final [s/N], Enter=N; -y permite o aceite final apenas se nao houver conflito bloqueante.
Antes de gravar, todas as abas sao relidas. Qualquer mudanca detectada cancela o lote.
A escrita ocorre em uma unica requisicao batchUpdate; depois os IDs sao conferidos novamente.
Google Sheets nao fornece CAS atomico entre a ultima leitura e a escrita: nao edite a planilha e nao execute instancias paralelas.
Em falha ou retorno incerto, confira manualmente o Google Sheets antes de repetir.

## Privacidade e testes

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Os testes sao sinteticos. Nao publique tokens, planilhas, extratos nem logs com dados financeiros no repositorio publico.