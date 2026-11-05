"""Dados inteiramente ficticios, sem leitura de arquivos reais."""

from contextlib import redirect_stderr, redirect_stdout
from decimal import Decimal
from io import StringIO
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from importador_extratos.leitor_csv import ColunasCSV, ErroCSV, ler_csv  # noqa: E402
from importador_extratos.__main__ import main  # noqa: E402


class CSVTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        (self.raiz / "2026").mkdir()

    def arquivo(self, content: bytes):
        p = self.raiz / "2026" / "amostra.csv"
        p.write_bytes(content)
        return p

    def test_csv_brasileiro_em_utf8_e_preservacao(self):
        p = self.arquivo("Data;Descrição;Valor;ID\n03/11/2026;Compra totalmente fictícia;-1.234,56;EX-1\n04/11/2026;Crédito inventado;R$ 2.000,00;EX-2\n".encode())
        estado = (p.read_bytes(), p.stat().st_mtime_ns)
        mov = ler_csv(p)
        self.assertEqual(len(mov), 2)
        self.assertEqual([x.valor for x in mov], [Decimal("-1234.56"), Decimal("2000.00")])
        self.assertEqual(mov[0].identificador, "EX-1")
        self.assertEqual(mov[0].data.isoformat(), "2026-11-03")
        self.assertEqual(estado, (p.read_bytes(), p.stat().st_mtime_ns))

    def test_csv_virgula_aspas_mais_valores_en(self):
        p = self.arquivo(b'Date,Description,Amount\n2026-11-03,"Store, fictitious","-1,234.56"\n2026-11-04,Imaginary,12.50\n')
        mov = ler_csv(p)
        self.assertEqual(len(mov), 2)
        self.assertEqual(mov[0].valor, Decimal("-1234.56"))
        self.assertEqual(mov[0].descricao, "Store, fictitious")

    def test_entrada_saida_separadas_e_cp1252(self):
        linhas = 'Data;Histórico;Entrada;Saída\n01/11/2026;Crédito fictício;50,00;\n02/11/2026;Débito fictício;;14,90\n'
        mov = ler_csv(self.arquivo(linhas.encode("cp1252")))
        self.assertEqual([x.valor for x in mov], [Decimal("50.00"), Decimal("-14.90")])

    def test_customizacao_de_cabecalhos(self):
        p = self.arquivo(b'Dt. Mov.;Texto da linha;Quantia\n01/11/2026;Teste ficticio;45,67\n')
        with self.assertRaises(ErroCSV):
            ler_csv(p)
        mov = ler_csv(p, colunas=ColunasCSV(data="Dt. Mov.", descricao="Texto da linha", valor="Quantia"))
        self.assertEqual(mov[0].valor, Decimal("45.67"))

    def test_ambiguidade_valores_e_mapeamento(self):
        p = self.arquivo(b'Data;Descricao;Valor;Credito\n01/11/2026;Ficticio;20,00;20,00\n')
        with self.assertRaisesRegex(ErroCSV, "coexistem"):
            ler_csv(p)
        self.assertEqual(ler_csv(p, colunas=ColunasCSV(valor="Valor"))[0].valor, Decimal("20.00"))

    def test_valor_com_3_casas_nao_aceito(self):
        for num in ("1.234", "1,234", "1,23,4", "999.999", "R$ 1.234"):
            with self.subTest(valor=num):
                with self.assertRaises(ErroCSV):
                    ler_csv(self.arquivo(("Data;Descricao;Valor\n01/11/2026;Ficticio;" + num + "\n").encode()))

    def test_erros_de_estrutura_sem_vazar_dados(self):
        for content in (
            b'Data;Descricao;Valor\n31/02/2026;NOME PRIVADO;12,00\n',
            b'Data;Descricao;Valor\n01/11/2026;NOME PRIVADO;INVAL\n',
            b'Data;Descricao;Valor\n01/11/2026;NOME PRIVADO;12;X\n',
        ):
            with self.subTest(content=content[:10]):
                with self.assertRaises(ErroCSV) as exc:
                    ler_csv(self.arquivo(content))
                self.assertNotIn("NOME PRIVADO", str(exc.exception))

    def test_recusa_link_simbolico(self):
        p = self.arquivo(b'Data;Descricao;Valor\n01/11/2026;Ficticio;3\n')
        link = self.raiz / "atalho.csv"
        try:
            link.symlink_to(p)
        except OSError:
            self.skipTest("Sem permissao para symlink")
        with self.assertRaises(ErroCSV):
            ler_csv(link)

    def test_pular_linhas_e_virgulas_embutidas(self):
        p = self.arquivo(b'Relatorio ficticio\nData;Descricao;Valor\n01/11/2026;"Loja; inventada";10,00\n')
        mov = ler_csv(p, pular_linhas=1)
        self.assertEqual(mov[0].descricao, "Loja; inventada")

    def test_bom_e_nova_linha_entre_aspas(self):
        p = self.arquivo(("Data;Descrição;Valor\n" +
                          '01/11/2026;"Compra\nem loja fictícia";3,00\n').encode("utf-8-sig"))
        mov = ler_csv(p)
        self.assertEqual(len(mov), 1)
        self.assertEqual(mov[0].valor, Decimal("3.00"))
        self.assertIn("\n", mov[0].descricao)

    def test_cp1252_invalido_retorna_erro_controlado(self):
        p = self.arquivo(b"Data;Descricao;Valor\n01/11/2026;Campo\x81;1,00\n")
        with self.assertRaisesRegex(ErroCSV, "Codificacao CSV"):
            ler_csv(p)

    def test_credito_e_debito_ambos_preenchidos_rejeitados(self):
        p = self.arquivo(b"Data;Descricao;Credito;Debito\n01/11/2026;Ficticio;10,00;10,00\n")
        with self.assertRaises(ErroCSV):
            ler_csv(p)

    def test_valores_negativos_com_parenteses(self):
        p = self.arquivo(b"Data;Descricao;Valor\n01/11/2026;Ficticio;(R$ 15,70)\n")
        self.assertEqual(ler_csv(p)[0].valor, Decimal("-15.70"))

    def test_cli_somente_contagens_por_padrao(self):
        self.arquivo(b'Data;Descricao;Valor\n01/11/2026;NOME PRIVADO;3,00\n')
        saida, erro = StringIO(), StringIO()
        with redirect_stdout(saida), redirect_stderr(erro):
            status = main(["--pasta", str(self.raiz), "--analisar-csv"])
        self.assertEqual(status, 0, erro.getvalue())
        self.assertIn("Movimentacoes CSV identificadas: 1", saida.getvalue())
        self.assertNotIn("NOME PRIVADO", saida.getvalue())
        self.assertNotIn(str(self.raiz), saida.getvalue())

    def test_cli_recusa_csv_invalido_sem_vazamento(self):
        self.arquivo(b'Data;Descricao;Valor\n01/11/2026;NOME PRIVADO;erro\n')
        saida, erro = StringIO(), StringIO()
        with redirect_stdout(saida), redirect_stderr(erro):
            status = main(["--pasta", str(self.raiz), "--analisar-csv"])
        self.assertEqual(status, 1)
        self.assertNotIn("NOME PRIVADO", saida.getvalue() + erro.getvalue())


if __name__ == "__main__":
    unittest.main()
