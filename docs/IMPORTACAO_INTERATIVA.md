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
ID bancario confiavel: ja existente e ignorado; conflito de identidade e bloqueado. Para CSV com ID ausente, repetido ou nao confiavel, gera-se um identificador AUTO:...:DERIVADO:<sha256>:<ocorrencia>, calculado por origem/conta, data real, sinal e valor, descricao normalizada e ID externo quando presente. Nao depende de nome, hash do arquivo ou ordem dos extratos.
O hash nao comprova unicidade: movimentacoes indistinguiveis em um mesmo arquivo e aquelas que ja possuem o mesmo fingerprint na planilha exigem resposta explicita [s/N], com Enter=N. Ao confirmar uma operacao realmente distinta, reserva-se um novo numero de ocorrencia sem sobrescrever o antigo. O argumento -y bloqueia essas duplicidades suspeitas e tambem candidatos com coincidencia de data/valor com qualquer lancamento historico, mesmo sem ID.
Para candidatos derivados unicos, sem sobreposicao suspeita, pede [S/n] (Enter=S). --assumir-sim (ou -y) confirma apenas esses candidatos admissiveis e nunca libera conflitos.
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

## Reimportacao e extratos sobrepostos

Um CSV sem numero de documento ou com numero repetido nao fica sem ID: o identificador derivado e gravado na mesma coluna F da transacao. Em uma reexecucao, quando houver o mesmo fingerprint, o programa **nao** importa de novo por padrao. Para lancar deliberadamente uma segunda compra indistinguivel, e necessario responder explicitamente S a pergunta [s/N]; um sufixo de ocorrencia novo preserva as duas compras. O parametro -y nunca confirma essas ocorrencias adicionais.

A opcao --id-confiavel so deve ser usada com comprovacao da unicidade dos IDs do banco e dentro da conta correta. Nenhum arquivo extra de estado e criado. Para faturas e lotes com categorias diversas, revisar a classificacao financeira uma a uma.

## Diagnostico de bloqueios sem expor dados financeiros

A previa exibe agora o detalhamento **somente por categoria e quantidade** quando ha bloqueios. Esses motivos nao contem datas, valores, descricoes, IDs bancarios nem nomes de arquivos:

- `movimentos_indistinguiveis_no_arquivo`: mais de uma linha gera o mesmo fingerprint dentro do CSV/OFX; com `-y`, exige revisao individual
- `coincidencia_data_valor_historico`: a data e o valor ja aparecem em algum lancamento das 12 abas, mesmo sem ID; isso **nao prova** que seja o mesmo lancamento
- `fingerprint_ja_existente`: ID derivado semelhante ja consta na planilha; pode ser reimportacao, nao adicionar automaticamente
- `fingerprint_ja_aprovado_no_lote`: candidato indistinguivel ja aprovado no lote atual
- `conflito_id`, `id_repetido_no_lote`, `id_ja_reservado` e outros: identidade externa conflitante ou reserva repetida; nao sobrescrever

Se a previa ainda mostrar bloqueios, **nao** execute `--importar` e nao utilize `--id-confiavel` apenas para forcar aprovacoes. Confirme primeiro se o codigo atualizado esta no HEAD local e depois interprete a lista de motivos. Os registros financeiros reais devem continuar privados.


## Linhas com valor zero ou precisao excessiva

Movimentacoes CSV/OFX com valor zero ou valor cuja precisao excede duas casas
decimais nao podem ser gravadas na planilha pelo importador. A previa
**nao deve abortar todo o arquivo** por isso: bloqueia apenas essas linhas,
mostrando suas quantidades como \`valor_zero\` ou
\`valor_precisao_excessiva\`, sem expor dados financeiros.
Esses valores nao sao arredondados automaticamente. Antes de qualquer importacao,
investigue os bloqueios e mantenha \`--planejar-importacao\` durante a homologacao.
