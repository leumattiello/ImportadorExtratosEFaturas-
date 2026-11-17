"""Testes sinteticos, sem credenciais Google e sem escritas reais."""
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from contextlib import redirect_stdout

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from importador_extratos.identidade import Lancamento
from importador_extratos.fluxo_importacao import confirmar, preparar_previa, _categoria, _valor_para_revisao
from importador_extratos.sheets_gateway import (
    ErroPlanilha, MESES, LinhaNova, _data, _valor, _linha,
    ler_instantaneo, gravar_lote,
)

class Requisicao:
    def __init__(self,retorno):self.retorno=retorno
    def execute(self):return self.retorno

class Valores:
    def __init__(self,servico):self.servico=servico
    def batchGet(self,**params):
        s=self.servico
        s.operacoes.append(("leitura",params))
        return Requisicao({"valueRanges":[{"values":s.dados.get(m,
            [["Data","Descrição","Debito","Credito","Valor","ID"]])} for m in MESES]+
            [{"values":[["CC Banco do Brasil"],["Alimentação"],["Habitação"]]}]})

class API:
    def __init__(self,servico):self.s=servico
    def get(self,**params):
        return Requisicao({"sheets":[{"properties":{"title":m,"sheetId":i,
          "gridProperties":{"rowCount":1001}}} for i,m in enumerate(MESES)]+
          [{"properties":{"title":"Dados","sheetId":999}}]})
    def values(self):return Valores(self.s)
    def batchUpdate(self,**params):
        self.s.operacoes.append(("gravacao",params))
        for req in params["body"]["requests"]:
            u=req["updateCells"];mes=MESES[u["range"]["sheetId"]]
            vals=[v["userEnteredValue"].get("stringValue",
                  v["userEnteredValue"].get("numberValue")) for v in u["rows"][0]["values"]]
            dia=(date(1899,12,30)+timedelta(days=int(vals[0]))).strftime("%d/%m/%Y")
            linhas=self.s.dados.setdefault(mes,[["Data","Descrição","Debito","Credito","Valor","ID"]])
            linhas.append([dia]+vals[1:])
        return Requisicao({})

class Servico:
    def __init__(self):self.dados={};self.operacoes=[]
    def spreadsheets(self):return API(self)

def movimento(id="100",valor="-10.50",descricao="Ficticio"):
    return Lancamento(date(2026,11,5),descricao,Decimal(valor),id)

class TestesFluxo(TestCase):
    def analisar(self, novos, antigos=(), **kwargs):
        return preparar_previa(novos,antigos,"BB","CC1",True,
                               exige_tty=False,**kwargs)

    def test_enter_interativo(self):
        self.assertTrue(confirmar("?",entrada=lambda p:""))
        self.assertFalse(confirmar("?",entrada=lambda p:"n"))
        self.assertTrue(confirmar("?",entrada=lambda p:"s"))
        self.assertFalse(confirmar("?",entrada=lambda p:"",padrao_sim=False))
        self.assertTrue(confirmar("?",assumir_sim=True,entrada=lambda p:1/0))

    def test_revisao_sim_ou_nao(self):
        anterior=movimento(id="MAN:1",valor="10.50")
        for resposta,esperado in (("",1),("n",0)):
            r=self.analisar([movimento()],[anterior],entrada=lambda p:resposta)
            self.assertEqual(len(r.aprovados),esperado)

    def test_id_ausente_gera_derivado_estavel(self):
        r=self.analisar([movimento(id=None)],assumir_sim=True)
        self.assertEqual((len(r.aprovados),r.bloqueados),(1,0))
        self.assertTrue(r.ids_aprovados[0].startswith("AUTO:BB:CC1:DERIVADO:"))

    def test_conflito_nao_autoriza_y(self):
        anterior=movimento(id="AUTO:BB:CC1:100",descricao="outro")
        r=self.analisar([movimento()],[anterior],assumir_sim=True)
        self.assertEqual((r.conflitos,r.bloqueados),(1,1))

    def test_ids_iguais_no_lote_bloqueados(self):
        r=self.analisar([movimento(),movimento()],assumir_sim=True)
        self.assertEqual((len(r.aprovados),r.bloqueados),(0,2))

    def test_ja_existente_ignorado(self):
        anterior=movimento(id="AUTO:BB:CC1:100",valor="10.50")
        r=self.analisar([movimento()],[anterior],assumir_sim=True)
        self.assertEqual((r.existentes,r.ignorados),(1,1))
        self.assertEqual(len(r.aprovados),0)

    def test_novo_elegivel(self):
        r=self.analisar([movimento()])
        self.assertEqual((r.novos,len(r.aprovados)),(1,1))

    def test_data_valores(self):
        self.assertEqual(_data("05/11/26"),date(2026,11,5))
        self.assertEqual(_valor("1.245,20"),Decimal("1245.20"))
        self.assertEqual(_valor(-4.5),Decimal("4.5"))

    def test_lancamento_incompleto_rejeitado(self):
        with self.assertRaises(ErroPlanilha):
            _linha(["01/01/2026","","","",11.2,""])

    def test_planilha_12_abas_leitura(self):
        s=Servico()
        s.dados["Janeiro"]=[["Data","Descrição","Debito","Credito","Valor","ID"],
            ["05/01/2026","Ficticio","CC Banco do Brasil","Alimentação",12.5,"MAN:1"]]
        r=ler_instantaneo(s,"id-ficticio")
        self.assertEqual(len(r.existentes),1)
        self.assertEqual(r.proximas["Janeiro"],3)
        self.assertEqual(r.proximas["Novembro"],2)
        self.assertEqual(len([o for o in s.operacoes if o[0]=="leitura"]),1)

    def test_gravacao_um_lote_uma_vez(self):
        s=Servico();snap=ler_instantaneo(s,"ficticio")
        item=LinhaNova(date(2026,11,5),"Exemplo",Decimal("-10.50"),
                       "AUTO:BB:CC1:100","CC Banco do Brasil","Alimentação")
        self.assertEqual(gravar_lote(s,"ficticio",snap,11,(item,)),1)
        self.assertEqual(sum(o[0]=="gravacao" for o in s.operacoes),1)
        d=s.dados["Novembro"][1]
        self.assertEqual((d[2],d[3],d[4],d[5]),
                         ("CC Banco do Brasil","Alimentação",10.5,"AUTO:BB:CC1:100"))

    def test_gravacao_suspensa_se_planilha_mudou(self):
        s=Servico();snap=ler_instantaneo(s,"ficticio")
        s.dados["Janeiro"]=[["Data","Descrição","Debito","Credito","Valor","ID"],
            ["05/01/2026","Novo","CC Banco do Brasil","Alimentação",5,"MAN:X"]]
        item=LinhaNova(date(2026,11,5),"Exemplo",Decimal("-10.50"),
                       "AUTO:BB:CC1:100","CC Banco do Brasil","Alimentação")
        with self.assertRaisesRegex(ErroPlanilha,"mudou"):
            gravar_lote(s,"ficticio",snap,11,(item,))
        self.assertFalse(any(k=="gravacao" for k,_ in s.operacoes))

    def test_id_manual_impedido_na_gravacao(self):
        s=Servico();snap=ler_instantaneo(s,"ficticio")
        item=LinhaNova(date(2026,11,5),"Exemplo",Decimal("-10.50"),
                       "MAN:100","CC Banco do Brasil","Alimentação")
        with self.assertRaises(ErroPlanilha):
            gravar_lote(s,"ficticio",snap,11,(item,))
        self.assertFalse(any(k=="gravacao" for k,_ in s.operacoes))

    def test_categoria_ausente_bloqueia(self):
        s=Servico();snap=ler_instantaneo(s,"ficticio")
        item=LinhaNova(date(2026,11,5),"Exemplo",Decimal("-10.50"),
                       "AUTO:BB:CC1:100","CC Banco do Brasil","INEXISTENTE")
        with self.assertRaises(ErroPlanilha):
            gravar_lote(s,"ficticio",snap,11,(item,))
        self.assertFalse(any(k=="gravacao" for k,_ in s.operacoes))

class TestesIDsDerivados(TestCase):
    def analisar(self,movimentos,existentes=(),**kwargs):
        return preparar_previa(movimentos,existentes,"BB","CC1",False,
                               exige_tty=False,**kwargs)

    def test_sem_id_estavel_em_leituras_repetidas(self):
        registro=movimento(id=None)
        a=self.analisar([registro],assumir_sim=True)
        b=self.analisar([registro],assumir_sim=True)
        self.assertEqual(a.ids_aprovados,b.ids_aprovados)
        self.assertEqual(len(a.aprovados),1)

    def test_mesmo_documento_repetido_em_operacoes_distintas(self):
        registros=[movimento(id="DOC9",descricao="Compra A"),
                   movimento(id="DOC9",descricao="Compra B"),
                   movimento(id="DOC9",descricao="Compra C")]
        r=self.analisar(registros,assumir_sim=True)
        self.assertEqual(len(r.aprovados),3)
        self.assertEqual(len(set(r.ids_aprovados)),3)

    def test_mesma_compra_em_arquivo_sobreposto_bloqueia_y(self):
        mov=movimento(id=None)
        primeiro=self.analisar([mov],assumir_sim=True)
        anterior=Lancamento(mov.data,mov.descricao,abs(mov.valor),primeiro.ids_aprovados[0])
        segundo=self.analisar([mov],[anterior],assumir_sim=True)
        self.assertEqual((len(segundo.aprovados),segundo.bloqueados),(0,1))
        self.assertEqual(segundo.revisao,1)

    def test_mesma_compra_em_arquivo_sobreposto_enter_nao(self):
        mov=movimento(id=None)
        anterior_id=self.analisar([mov],assumir_sim=True).ids_aprovados[0]
        anterior=Lancamento(mov.data,mov.descricao,abs(mov.valor),anterior_id)
        resposta=self.analisar([mov],[anterior],entrada=lambda _: "")
        self.assertEqual((resposta.ignorados,len(resposta.aprovados)),(1,0))

    def test_nova_ocorrencia_identica_exige_s_explicito(self):
        mov=movimento(id=None)
        anterior_id=self.analisar([mov],assumir_sim=True).ids_aprovados[0]
        anterior=Lancamento(mov.data,mov.descricao,abs(mov.valor),anterior_id)
        resposta=self.analisar([mov],[anterior],entrada=lambda _: "s")
        self.assertEqual(len(resposta.aprovados),1)
        self.assertNotEqual(resposta.ids_aprovados[0],anterior_id)
        self.assertTrue(resposta.ids_aprovados[0].endswith(":2"))

    def test_duas_operacoes_indistinguiveis_no_mesmo_arquivo_com_y(self):
        r=self.analisar([movimento(id=None),movimento(id=None)],assumir_sim=True)
        self.assertEqual((len(r.aprovados),r.bloqueados),(0,2))

    def test_duas_operacoes_indistinguiveis_exigem_confirmacao_individual(self):
        r=self.analisar([movimento(id=None),movimento(id=None)],entrada=lambda _: "s")
        self.assertEqual(len(r.aprovados),2)
        self.assertEqual(len(set(r.ids_aprovados)),2)
        self.assertTrue(r.ids_aprovados[0].endswith(":1"))
        self.assertTrue(r.ids_aprovados[1].endswith(":2"))

    def test_lancamento_historico_sem_id_mesmo_valor_bloqueia_y(self):
        mov=movimento(id=None)
        antigo=Lancamento(mov.data,"Outra descricao",abs(mov.valor),None)
        r=self.analisar([mov],[antigo],assumir_sim=True)
        self.assertEqual((len(r.aprovados),r.bloqueados),(0,1))

    def test_hash_distingue_entrada_de_saida(self):
        debito=movimento(id=None,valor="-10.50")
        credito=movimento(id=None,valor="10.50")
        r=self.analisar([debito,credito],assumir_sim=True)
        self.assertEqual(len(r.aprovados),2)
        self.assertNotEqual(r.ids_aprovados[0],r.ids_aprovados[1])

    def test_mesmo_conjunto_em_ordem_diferente_tem_mesmos_ids(self):
        a=movimento(id=None,descricao="Loja A")
        b=movimento(id=None,descricao="Loja B")
        x=self.analisar([a,b],assumir_sim=True)
        y=self.analisar([b,a],assumir_sim=True)
        self.assertEqual(set(x.ids_aprovados),set(y.ids_aprovados))

    def test_identificador_trustado_nao_vira_derivado(self):
        r=preparar_previa([movimento(id="ABC123")],(),"BB","CC1",True,
                          assumir_sim=True,exige_tty=False)
        self.assertEqual(r.ids_aprovados,("AUTO:BB:CC1:ABC123",))

    def test_35_movimentos_sinteticos_10_sem_id_9_doc_repetido_16_unicos(self):
        todos=[]
        for i in range(10):
            todos.append(Lancamento(date(2026,11,5),f"Sem ID {i}",Decimal("-10.50"),None))
        for i in range(9):
            todos.append(Lancamento(date(2026,11,5),f"Documento repetido {i}",
                                    Decimal("-10.50"),"DOC-REPETIDO"))
        for i in range(16):
            todos.append(Lancamento(date(2026,11,5),f"Documento unico {i}",
                                    Decimal("-10.50"),f"DOC-{i:03d}"))
        r=self.analisar(todos,assumir_sim=True)
        self.assertEqual(len(todos),35)
        self.assertEqual((len(r.aprovados),r.bloqueados),(35,0))
        self.assertEqual(len(set(r.ids_aprovados)),35)


class TestesDiagnosticoBloqueios(TestCase):
    def test_coincidencia_com_historico_contada_sem_dados(self):
        mov = movimento(id=None)
        antigo = Lancamento(mov.data, "Historico diferente", abs(mov.valor), None)
        resultado = preparar_previa([mov], [antigo], "BB", "CC1", False,
                                    assumir_sim=True, exige_tty=False)
        self.assertEqual(resultado.bloqueados, 1)
        self.assertEqual(dict(resultado.motivos_bloqueio),
                         {"coincidencia_data_valor_historico": 1})

    def test_repeticao_interna_de_fingerprint_contada(self):
        itens = [movimento(id=None), movimento(id=None)]
        resultado = preparar_previa(itens, (), "BB", "CC1", False,
                                    assumir_sim=True, exige_tty=False)
        self.assertEqual(dict(resultado.motivos_bloqueio),
                         {"movimentos_indistinguiveis_no_arquivo": 2})

    def test_fingerprint_presente_na_planilha_contado(self):
        mov = movimento(id=None)
        primeira = preparar_previa([mov], (), "BB", "CC1", False,
                                   assumir_sim=True, exige_tty=False)
        antigo = Lancamento(mov.data, mov.descricao, abs(mov.valor),
                            primeira.ids_aprovados[0])
        segunda = preparar_previa([mov], [antigo], "BB", "CC1", False,
                                  assumir_sim=True, exige_tty=False)
        self.assertEqual(dict(segunda.motivos_bloqueio),
                         {"fingerprint_ja_existente": 1})

    def test_conflito_id_contado_sem_divulgar_id(self):
        mov = movimento(id="XYZ")
        antigo = Lancamento(mov.data, "Outro lancamento", abs(mov.valor),
                            "AUTO:BB:CC1:XYZ")
        resultado = preparar_previa([mov], [antigo], "BB", "CC1", True,
                                    assumir_sim=True, exige_tty=False)
        self.assertEqual(dict(resultado.motivos_bloqueio), {"conflito_id": 1})

    def test_soma_dos_motivos_igual_a_total_bloqueado(self):
        mov = movimento(id=None)
        antigo = Lancamento(mov.data, "Historico", abs(mov.valor), "MAN:1")
        resultado = preparar_previa([mov, movimento(id=None), movimento(id="D")],
                                    [antigo], "BB", "CC1", False,
                                    assumir_sim=True, exige_tty=False)
        self.assertEqual(sum(v for _, v in resultado.motivos_bloqueio),
                         resultado.bloqueados)
        self.assertTrue(all(isinstance(nome, str) and isinstance(qtd, int)
                            for nome, qtd in resultado.motivos_bloqueio))


class TestesValoresNaoImportaveis(TestCase):
    """A previa deve continuar sem arredondar ou gravar valores invalidos."""

    def analisar(self, movimentos, confiavel=False):
        return preparar_previa(movimentos, (), "BB", "CC1", confiavel,
                               assumir_sim=True, exige_tty=False)

    def test_zero_csv_e_bloqueado_sem_interromper_outras_linhas(self):
        resultado = self.analisar([
            movimento(id=None, valor="0.00"),
            movimento(id=None, valor="-10.50", descricao="Compra A"),
        ])
        self.assertEqual(resultado.aprovados, (1,))
        self.assertEqual(resultado.bloqueados, 1)
        self.assertEqual(dict(resultado.motivos_bloqueio), {"valor_zero": 1})

    def test_zero_ofx_com_fitid_tambem_e_bloqueado(self):
        resultado = self.analisar([movimento(id="FIT-0", valor="0.00")],
                                  confiavel=True)
        self.assertEqual(resultado.aprovados, ())
        self.assertEqual(dict(resultado.motivos_bloqueio), {"valor_zero": 1})

    def test_precisao_maior_que_centavos_nao_e_arredondada(self):
        resultado = self.analisar([
            movimento(id=None, valor="-10.501"),
            movimento(id=None, valor="-10.502"),
            movimento(id=None, valor="-10.50"),
        ])
        self.assertEqual(resultado.aprovados, (2,))
        self.assertEqual(resultado.bloqueados, 2)
        self.assertEqual(dict(resultado.motivos_bloqueio),
                         {"valor_precisao_excessiva": 2})

    def test_35_movimentos_com_um_zero_mantem_resumo_consistente(self):
        movimentos = [
            movimento(id=f"REF-{i}", valor="0.00" if i == 17 else "-10.50",
                      descricao=f"Transacao ficticia {i}")
            for i in range(35)
        ]
        resultado = self.analisar(movimentos)
        self.assertEqual(len(resultado.aprovados) + resultado.ignorados +
                         resultado.bloqueados, len(movimentos))
        self.assertEqual((len(resultado.aprovados), resultado.bloqueados),
                         (34, 1))
        self.assertEqual(dict(resultado.motivos_bloqueio), {"valor_zero": 1})


class TestesExibicaoValorCategoria(TestCase):
    def test_valor_formatado_com_sinal_e_centavos(self):
        self.assertEqual(_valor_para_revisao(Decimal("-1234.50")), "R$ -1.234,50")
        self.assertEqual(_valor_para_revisao(Decimal("2500")), "R$ +2.500,00")

    def test_pergunta_categoria_contem_valor_e_descricao(self):
        perguntas=[]
        def responder(pergunta):
            perguntas.append(pergunta)
            return "Alimentação"
        mov=movimento(id="DOC-001",valor="-1234.50",descricao="Mercado ficticio")
        with patch("importador_extratos.fluxo_importacao.sys.stdin.isatty",return_value=True):
            with patch("builtins.input",side_effect=responder):
                selecionada=_categoria(mov,{"Alimentação","Habitação"},None,False)
        self.assertEqual(selecionada,"Alimentação")
        self.assertEqual(len(perguntas),1)
        self.assertIn("05/11/2026",perguntas[0])
        self.assertIn("Mercado ficticio",perguntas[0])
        self.assertIn("R$ -1.234,50",perguntas[0])
        self.assertIn("categoria?",perguntas[0])

    def test_categoria_padrao_preserva_comportamento(self):
        mov=movimento()
        with patch("builtins.input",side_effect=AssertionError("Nao perguntar")):
            self.assertEqual(_categoria(mov,{"Alimentação"},"Alimentação",False),"Alimentação")
