"""Testes com perfis privados e CSVs inteiramente ficticios."""

from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from importador_extratos.__main__ import main
from importador_extratos.perfis_csv import ErroPerfis, ler_perfis, selecionar_perfil
from importador_extratos.leitor_csv import ler_csv


class PerfisTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.base = Path(self.t.name)
        self.pasta = self.base / "ExtratosFaturas"
        (self.pasta / "2026").mkdir(parents=True)
        (self.pasta / "2027").mkdir()
        self.ini = self.base / "perfis.ini"

    def configurar(self, texto=None):
        self.ini.write_text(texto or """[perfil:layout_um]
requer_colunas = Data | Lançamento | Histórico
valor = Valor
descricao = Lançamento
delimitador = ;

[perfil:layout_dois]
requer_colunas = Data | Texto livre | Entrada | Saída
descricao = Texto livre
credito = Entrada
debito = Saída
delimitador = ;
""", encoding="utf-8")

    def csv(self, ano, nome, conteudo):
        caminho = self.pasta / ano / nome
        caminho.write_text(conteudo, encoding="utf-8")
        return caminho

    def executar(self, *args):
        saida, erro = StringIO(), StringIO()
        with redirect_stdout(saida), redirect_stderr(erro):
            codigo = main(["--pasta", str(self.pasta), "--analisar-csv", *args])
        return codigo, saida.getvalue(), erro.getvalue()

    def test_dois_perfis_com_layouts_diferentes(self):
        self.configurar()
        a = self.csv("2026", "a.csv", "Data;Lançamento;Histórico;Valor\n01/11/2026;VENDEDOR-FICTICIO;Compra;-13,90\n")
        b = self.csv("2027", "b.csv", "Data;Texto livre;Entrada;Saída\n02/01/2027;Credito fake;20,00;\n")
        p = ler_perfis(self.ini)
        self.assertEqual(len(p), 2)
        self.assertEqual(ler_csv(a, colunas=selecionar_perfil(a,p).colunas, delimitador=";")[0].descricao,"VENDEDOR-FICTICIO")
        self.assertEqual(str(ler_csv(b,colunas=selecionar_perfil(b,p).colunas,delimitador=";")[0].valor), "20.00")
        status, saida, erro = self.executar()
        self.assertEqual(status,0,erro)
        self.assertIn("Movimentacoes CSV identificadas: 2",saida)
        self.assertIn("Arquivos selecionados por perfil: 2",saida)
        self.assertNotIn("VENDEDOR-FICTICIO",saida+erro)
        self.assertNotIn(str(self.base),saida+erro)

    def test_sem_config_retorna_modo_antigo_manual(self):
        self.csv("2026", "a.csv", "Data;Lançamento;Histórico;Valor\n01/11/2026;Teste;OUTRA;5,00\n")
        rc, saida, erro = self.executar("--csv-coluna-descricao", "Lançamento")
        self.assertEqual(rc,0,erro)
        self.assertIn("Movimentacoes CSV identificadas: 1",saida)
        self.assertNotIn("Arquivos selecionados",saida)

    def test_com_config_incompativel_rejeita_sem_fallback(self):
        self.configurar()
        self.csv("2026", "desconhecido.csv", "Data;Descrição;Valor\n01/11/2026;Algo;10,00\n")
        rc, saida, erro = self.executar()
        self.assertEqual(rc,1)
        self.assertIn("Nenhum perfil",erro)
        self.assertNotIn(str(self.base),erro)

    def test_dupla_correspondencia_falha(self):
        self.configurar("""[perfil:um]
requer_colunas = Data | Descrição
descricao = Descrição
[perfil:dois]
requer_colunas = Data | Valor
descricao = Descrição
""")
        self.csv("2026", "amostra.csv", "Data;Descrição;Valor\n01/11/2026;Fictício;10,00\n")
        rc, _, erro = self.executar()
        self.assertEqual(rc,1)
        self.assertIn("Mais de um perfil",erro)

    def test_arquivo_privado_preservado(self):
        self.configurar()
        self.csv("2026", "a.csv", "Data;Lançamento;Histórico;Valor\n01/11/2026;Fictício;Algo;7,00\n")
        antes=(self.ini.read_bytes(),self.ini.stat().st_mtime_ns)
        rc,_,erro=self.executar()
        self.assertEqual(rc,0,erro)
        self.assertEqual(antes,(self.ini.read_bytes(),self.ini.stat().st_mtime_ns))

    def test_campo_invalido_e_dados_nao_expostos(self):
        self.configurar("""[perfil:xxx]
requer_colunas = Data | Histórico
conta_da_pessoa = DADOS-PRIVADOS
""")
        with self.assertRaises(ErroPerfis) as e:
            ler_perfis(self.ini)
        self.assertNotIn("DADOS-PRIVADOS",str(e.exception))

    def test_requer_duas_colunas_distintas(self):
        self.configurar("""[perfil:um]
requer_colunas = Lançamento | Lancamento
""")
        with self.assertRaises(ErroPerfis):ler_perfis(self.ini)

    def test_recusa_symlink_para_config(self):
        self.configurar()
        atalho=self.base/"atalho.ini"
        try: atalho.symlink_to(self.ini)
        except OSError: self.skipTest("symlink unsupported")
        with self.assertRaises(ErroPerfis):ler_perfis(atalho)

    def test_dados_de_config_com_conflito_nao_imprimem_cabecalho(self):
        self.configurar()
        self.csv("2026", "a.csv", "Data;Lançamento;Histórico;Valor\n01/11/2026;CONFIDENCIAL;Compra;5,00\n")
        with self.assertRaises(SystemExit):
            self.executar("--csv-coluna-descricao", "Lançamento")

    def test_pode_desabilitar_descoberta(self):
        self.configurar()
        self.csv("2026", "a.csv", "Data;Lançamento;Histórico;Valor\n01/11/2026;Item;Compra;5,00\n")
        rc,_,err=self.executar("--sem-perfis","--csv-coluna-descricao","Lançamento")
        self.assertEqual(rc,0,err)

    def test_opcao_explicita_arquivo_inexistente(self):
        self.csv("2026", "a.csv", "Data;Descrição;Valor\n01/11/2026;Item;10,00\n")
        rc,_,err=self.executar("--perfis",str(self.base/"inexistente.ini"))
        self.assertEqual(rc,1)
        self.assertIn("Arquivo de perfis inexistente",err)

    def test_arquivo_perfil_no_repositorio_e_recusado(self):
        repo=Path(__file__).resolve().parents[1]
        with self.assertRaises(ErroPerfis): ler_perfis(repo/"qualquer.ini")

    def test_concatenacao_multiplas_colunas_na_ordem(self):
        self.configurar("""[perfil:concatenado]
requer_colunas = Data | Lançamento | Histórico | Complemento | Valor
descricao = Lançamento | Histórico | Complemento
separador_descricao = " - "
valor = Valor
delimitador = ;
""")
        p = self.csv("2026", "a.csv",
                     "Data;Lançamento;Histórico;Complemento;Valor\n"
                     "01/11/2026;  PIX  ;  Serviço ; Pagamento ; -15,00\n"
                     "02/11/2026;  Tarifa ;;  ; -2,00\n"
                     "03/11/2026;;  Referência ;  ; 3,00\n")
        perfil = selecionar_perfil(p, ler_perfis(self.ini))
        mov = ler_csv(p, colunas=perfil.colunas, delimitador=perfil.delimitador)
        self.assertEqual([m.descricao for m in mov],
                         ["PIX - Serviço - Pagamento", "Tarifa", "Referência"])
        self.assertEqual(len(mov), 3)
        status, saida, erro = self.executar()
        self.assertEqual(status, 0, erro)
        self.assertIn("Movimentacoes CSV identificadas: 3", saida)
        self.assertNotIn("PIX", saida + erro)

    def test_separador_customizado_e_coluna_unica_compativel(self):
        self.configurar("""[perfil:custom]
requer_colunas = Data | Lançamento | Histórico | Valor
descricao = Lançamento | Histórico
separador_descricao = " / "
valor = Valor
delimitador = ;
""")
        p = self.csv("2026", "a.csv",
                     "Data;Lançamento;Histórico;Valor\n01/11/2026;PIX;Chave fictícia;5,00\n")
        perfil = selecionar_perfil(p, ler_perfis(self.ini))
        self.assertEqual(ler_csv(p, colunas=perfil.colunas, delimitador=";")[0].descricao,
                         "PIX / Chave fictícia")
        self.configurar()
        perfil = selecionar_perfil(p, ler_perfis(self.ini))
        self.assertEqual(ler_csv(p, colunas=perfil.colunas, delimitador=";")[0].descricao,
                         "PIX")

    def test_coluna_de_descricao_inexistente_recusada(self):
        self.configurar("""[perfil:invalido]
requer_colunas = Data | Lançamento | Valor
descricao = Lançamento | Complemento
valor = Valor
delimitador = ;
""")
        self.csv("2026", "a.csv",
                 "Data;Lançamento;Valor\n01/11/2026;DADO PRIVADO;5,00\n")
        status, saida, erro = self.executar()
        self.assertEqual(status, 1)
        self.assertIn("Coluna de descricao nao encontrada", erro)
        self.assertNotIn("DADO PRIVADO", saida + erro)

    def test_descricoes_todas_vazias_recusadas(self):
        self.configurar("""[perfil:vazio]
requer_colunas = Data | Lançamento | Histórico | Valor
descricao = Lançamento | Histórico
valor = Valor
delimitador = ;
""")
        self.csv("2026", "a.csv",
                 "Data;Lançamento;Histórico;Valor\n01/11/2026; ; ;5,00\n")
        status, _, erro = self.executar()
        self.assertEqual(status, 1)
        self.assertIn("Descricao CSV ausente", erro)

    def test_rejeita_colunas_repetidas_com_ou_sem_acentos(self):
        for duplicado in ("Lançamento | Lancamento", "Lançamento | Lançamento", "Lançamento | "):
            with self.subTest(duplicado=duplicado):
                self.configurar("""[perfil:duplo]
requer_colunas = Data | Lançamento | Valor
descricao = """ + duplicado + """
""")
                with self.assertRaises(ErroPerfis):
                    ler_perfis(self.ini)

    def test_separador_vazio_e_customizado(self):
        self.configurar("""[perfil:sem_separador]
requer_colunas = Data | Lançamento | Histórico | Valor
descricao = Lançamento | Histórico
separador_descricao = ""
valor = Valor
delimitador = ;
""")
        p = self.csv("2026", "a.csv",
                     "Data;Lançamento;Histórico;Valor\n01/11/2026;PIX; fictício ;5,00\n")
        perfil = selecionar_perfil(p, ler_perfis(self.ini))
        self.assertEqual(ler_csv(p, colunas=perfil.colunas, delimitador=";")[0].descricao,
                         "PIXfictício")
        self.configurar("""[perfil:separador_invalido]
requer_colunas = Data | Lançamento | Valor
descricao = Lançamento
separador_descricao = """ + "x" * 41 + """
""")
        with self.assertRaises(ErroPerfis):
            ler_perfis(self.ini)

    def test_coluna_ja_utilizada_como_valor_rejeitada(self):
        self.configurar("""[perfil:colisao]
requer_colunas = Data | Lançamento | Valor
descricao = Lançamento | Valor
valor = Valor
delimitador = ;
""")
        self.csv("2026", "a.csv",
                 "Data;Lançamento;Valor\n01/11/2026;Teste;5,00\n")
        status, _, erro = self.executar()
        self.assertEqual(status, 1)
        self.assertIn("mesma coluna", erro)

    def test_linha_com_quebra_interna_preservada(self):
        self.configurar("""[perfil:quebra]
requer_colunas = Data | Lançamento | Histórico | Valor
descricao = Lançamento | Histórico
valor = Valor
delimitador = ;
""")
        p = self.csv("2026", "a.csv",
                     'Data;Lançamento;Histórico;Valor\n01/11/2026;"  Compra\nem loja ";OK;3,00\n')
        perfil = selecionar_perfil(p, ler_perfis(self.ini))
        mov = ler_csv(p, colunas=perfil.colunas, delimitador=";")
        self.assertEqual(mov[0].descricao, "Compra\nem loja - OK")


    def test_bb_filtro_tipo_lancamento_ignora_saldos(self):
        self.configurar("""[perfil:bb_exemplo]
requer_colunas = Data | Lançamento | Detalhes | N° documento | Valor | Tipo Lançamento
descricao = Lançamento | Detalhes
separador_descricao = " - "
identificador = N° documento
valor = Valor
filtrar_coluna = Tipo Lançamento
filtrar_valores = Entrada | Saída
delimitador = ;
""")
        caminho = self.csv("2026", "bb.csv",
            "Data;Lançamento;Detalhes;N° documento;Valor;Tipo Lançamento\n"
            "01/11/2026;Saldo anterior;; ;0,00;Saldo\n"
            "02/11/2026;PIX fictício;Compra;100;-30,50;Saída\n"
            "03/11/2026;Crédito fictício;Depósito;101;99,90;Entrada\n"
            "04/11/2026;Saldo atual;; ;0,00;\n"
            "05/11/2026;Movimento desconhecido;Aviso;102;5,00;Outros\n")
        perfil=selecionar_perfil(caminho,ler_perfis(self.ini))
        mov=ler_csv(caminho,colunas=perfil.colunas,delimitador=perfil.delimitador)
        self.assertEqual(len(mov),2)
        self.assertEqual([str(m.valor) for m in mov],["-30.50","99.90"])
        self.assertEqual([m.identificador for m in mov],["100","101"])
        self.assertEqual(mov[0].descricao,"PIX fictício - Compra")
        status,saida,erro=self.executar()
        self.assertEqual(status,0,erro)
        self.assertIn("Movimentacoes CSV identificadas: 2",saida)

    def test_filtrar_antes_de_validar_campos_de_saldo(self):
        self.configurar("""[perfil:bb]
requer_colunas = Data | Lançamento | Valor | Tipo Lançamento
descricao = Lançamento
valor = Valor
filtrar_coluna = Tipo Lançamento
filtrar_valores = Entrada | Saída
delimitador = ;
""")
        caminho=self.csv("2026","bb.csv",
            "Data;Lançamento;Valor;Tipo Lançamento\n"
            "DATA INVALIDA;;VALOR INVALIDO;Saldo\n"
            "02/11/2026;Compra fictícia;-4,00; SaÍda \n")
        p=selecionar_perfil(caminho,ler_perfis(self.ini))
        mov=ler_csv(caminho,colunas=p.colunas,delimitador=p.delimitador)
        self.assertEqual(len(mov),1)
        self.assertEqual(str(mov[0].valor),"-4.00")

    def test_filtro_valor_desconhecido_nao_importa(self):
        self.configurar("""[perfil:bb]
requer_colunas = Data | Lançamento | Valor | Tipo Lançamento
descricao = Lançamento
valor = Valor
filtrar_coluna = Tipo Lançamento
filtrar_valores = Entrada | Saída
delimitador = ;
""")
        caminho=self.csv("2026","bb.csv",
            "Data;Lançamento;Valor;Tipo Lançamento\n"
            "02/11/2026;Outros fictício;25,00;Ajuste\n")
        p=selecionar_perfil(caminho,ler_perfis(self.ini))
        self.assertEqual(ler_csv(caminho,colunas=p.colunas,delimitador=p.delimitador),())
        status,saida,erro=self.executar()
        self.assertEqual(status,0,erro)
        self.assertIn("Movimentacoes CSV identificadas: 0",saida)

    def test_filtro_sem_coluna_requerida_falha_fechado(self):
        self.configurar("""[perfil:bb]
requer_colunas = Data | Lançamento | Valor
descricao = Lançamento
valor = Valor
filtrar_coluna = Tipo Lançamento
filtrar_valores = Entrada | Saída
delimitador = ;
""")
        caminho=self.csv("2026","bb.csv",
            "Data;Lançamento;Valor\n02/11/2026;Compra fictícia;-4,00\n")
        p=selecionar_perfil(caminho,ler_perfis(self.ini))
        with self.assertRaisesRegex(Exception,"Coluna de filtro"):
            ler_csv(caminho,colunas=p.colunas,delimitador=p.delimitador)

    def test_filtro_incompleto_e_duplicado_rejeitados(self):
        exemplos=[
            "filtrar_coluna = Tipo Lançamento\n",
            "filtrar_valores = Entrada | Saída\n",
            "filtrar_coluna = Tipo Lançamento\nfiltrar_valores = Entrada | entrada\n",
        ]
        for extra in exemplos:
            with self.subTest(extra=extra):
                self.configurar("[perfil:bb]\nrequer_colunas = Data | Lançamento | Valor\n"
                               "descricao = Lançamento\nvalor = Valor\n"+extra)
                with self.assertRaises(ErroPerfis):
                    ler_perfis(self.ini)

    def test_perfil_sem_filtro_nao_muda_comportamento(self):
        self.configurar("""[perfil:normal]
requer_colunas = Data | Lançamento | Valor
descricao = Lançamento
valor = Valor
delimitador = ;
""")
        caminho=self.csv("2026","normal.csv",
            "Data;Lançamento;Valor\n"
            "02/11/2026;Saldo descritivo;0,00\n"
            "03/11/2026;Compra;-1,00\n")
        p=selecionar_perfil(caminho,ler_perfis(self.ini))
        self.assertEqual(len(ler_csv(caminho,colunas=p.colunas,delimitador=p.delimitador)),2)


if __name__ == "__main__": unittest.main()
