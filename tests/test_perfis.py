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


if __name__ == "__main__": unittest.main()
