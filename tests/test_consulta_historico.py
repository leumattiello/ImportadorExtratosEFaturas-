"""Testes sintéticos da classificação por hash do histórico local."""

import csv
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from importador_extratos.consulta_historico import consultar_historico
from importador_extratos.historico import CABECALHO, ErroHistorico, NOME_HISTORICO
from importador_extratos.inventario import ArquivoFonte
from importador_extratos.__main__ import main
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO


class ConsultaHistoricoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.raiz = self.base / "ExtratosFaturas"
        (self.raiz / "2026").mkdir(parents=True)
        self.log = self.base / NOME_HISTORICO
        self.a, self.b, self.c = "a"*64, "b"*64, "c"*64

    def fonte(self, nome="um.csv", digest=None, tipo=".csv"):
        return ArquivoFonte(self.raiz/"2026"/nome, 2026, tipo, 5,
                            digest or self.a, False)

    def gravar(self, eventos):
        with self.log.open("w", newline="", encoding="utf-8") as destino:
            w = csv.writer(destino, delimiter=";")
            w.writerow(CABECALHO)
            for digest, estado, nome, tipo in eventos:
                w.writerow(("2026-11-10T13:00:00-03:00", "2026/"+nome, tipo,
                            estado, 0 if estado == "ERRO" else 2, digest))
        if os.name == "posix":
            self.log.chmod(0o600)

    def test_ausencia_de_historico(self):
        a = consultar_historico(self.raiz, [self.fonte(), self.fonte("outro.ofx", self.b, ".ofx")])
        self.assertEqual((a.nunca_analisados, a.ja_analisados, a.com_erro_anterior), (2,0,0))
        self.assertFalse(self.log.exists())

    def test_mistura_sucesso_erro_novo(self):
        self.gravar([(self.a, "ANALISADO", "um.csv", ".csv"),
                     (self.b, "ERRO", "outro.ofx", ".ofx")])
        r = consultar_historico(self.raiz, [
            self.fonte(), self.fonte("outro.ofx", self.b, ".ofx"), self.fonte("tres.csv", self.c)])
        self.assertEqual((r.nunca_analisados, r.ja_analisados, r.com_erro_anterior), (1,1,1))

    def test_sucesso_prevalece_sobre_erro_posterior(self):
        self.gravar([(self.a,"ANALISADO","um.csv",".csv"), (self.a,"ERRO","um.csv",".csv")])
        self.assertEqual(consultar_historico(self.raiz, [self.fonte()]).ja_analisados, 1)

    def test_erro_seguido_de_sucesso(self):
        self.gravar([(self.a,"ERRO","um.csv",".csv"), (self.a,"ANALISADO","um.csv",".csv")])
        self.assertEqual(consultar_historico(self.raiz, [self.fonte()]).ja_analisados, 1)

    def test_renomear_preserva_identidade(self):
        self.gravar([(self.a,"ANALISADO","um.csv",".csv")])
        self.assertEqual(consultar_historico(self.raiz,[self.fonte("renomeado.csv")]).ja_analisados, 1)

    def test_mesmo_nome_mas_hash_novo(self):
        self.gravar([(self.a,"ANALISADO","um.csv",".csv")])
        self.assertEqual(consultar_historico(self.raiz,[self.fonte("um.csv",self.b)]).nunca_analisados, 1)

    def test_copias_do_mesmo_hash_contam_como_arquivos(self):
        self.gravar([(self.a,"ANALISADO","um.csv",".csv")])
        self.assertEqual(consultar_historico(self.raiz,[self.fonte(),self.fonte("renomeado.csv")]).ja_analisados, 2)

    def test_nao_conta_xlsx(self):
        self.assertEqual(consultar_historico(self.raiz,[self.fonte("amostra.xlsx",self.a,".xlsx")]).arquivos_csv_ofx, 0)

    def test_consulta_preserva_historico(self):
        self.gravar([(self.a,"ANALISADO","um.csv",".csv")])
        before=(self.log.read_bytes(), self.log.stat().st_mtime_ns)
        consultar_historico(self.raiz,[self.fonte()])
        self.assertEqual(before,(self.log.read_bytes(),self.log.stat().st_mtime_ns))

    def test_recusa_cabecalho_invalido(self):
        self.log.write_text("cabecalho errado\n")
        if os.name == "posix": self.log.chmod(0o600)
        with self.assertRaises(ErroHistorico):
            consultar_historico(self.raiz,[self.fonte()])

    def test_recusa_linha_incompleta(self):
        self.gravar([(self.a,"ANALISADO","um.csv",".csv")])
        with self.log.open("a") as f: f.write("incompleto;linha\n")
        with self.assertRaises(ErroHistorico):
            consultar_historico(self.raiz,[self.fonte()])

    def test_recusa_estado_invalido(self):
        self.gravar([(self.a,"IMPORTADO","um.csv",".csv")])
        with self.assertRaises(ErroHistorico):
            consultar_historico(self.raiz,[self.fonte()])

    def test_recusa_hash_invalido(self):
        self.gravar([("invalido","ANALISADO","um.csv",".csv")])
        with self.assertRaises(ErroHistorico):
            consultar_historico(self.raiz,[self.fonte()])

    def test_permissao_aberta_recusada(self):
        if os.name != "posix": self.skipTest("POSIX")
        self.gravar([(self.a,"ANALISADO","um.csv",".csv")])
        self.log.chmod(0o644)
        with self.assertRaises(ErroHistorico):
            consultar_historico(self.raiz,[self.fonte()])

    def test_symlink_recusado(self):
        other=self.base/"alvo"
        other.write_text("ficticio")
        try: self.log.symlink_to(other)
        except OSError: self.skipTest("symlink")
        with self.assertRaises(ErroHistorico):
            consultar_historico(self.raiz,[self.fonte()])
        self.assertEqual(other.read_text(),"ficticio")

    def test_historico_grande_recusado(self):
        from importador_extratos.consulta_historico import MAX_HISTORICO_BYTES
        with self.log.open("wb") as f: f.truncate(MAX_HISTORICO_BYTES+1)
        if os.name == "posix": self.log.chmod(0o600)
        with self.assertRaises(ErroHistorico):
            consultar_historico(self.raiz,[self.fonte()])

    def test_cli_contagem_antes_do_registro_na_propria_execucao(self):
        p=self.raiz/"2026"/"ficcao.csv"
        p.write_text("Data;Descricao;Valor\n01/11/2026;Item ficticio;10,00\n",encoding="utf-8")
        for esperado in ("Arquivos CSV/OFX nunca analisados: 1",
                         "Arquivos CSV/OFX ja analisados: 1"):
            out,err=StringIO(),StringIO()
            with redirect_stdout(out),redirect_stderr(err):
                status=main(["--pasta",str(self.raiz),"--analisar-csv","--registrar-historico"])
            self.assertEqual(status,0,err.getvalue())
            self.assertIn(esperado,out.getvalue())
            self.assertNotIn("Item ficticio",out.getvalue()+err.getvalue())

    def test_cli_contagem_sem_registro_mantem_somente_leitura(self):
        p=self.raiz/"2026"/"ficcao.csv"
        p.write_text("Data;Descricao;Valor\n01/11/2026;Item ficticio;10,00\n",encoding="utf-8")
        out=StringIO()
        with redirect_stdout(out):
            rc=main(["--pasta",str(self.raiz),"--analisar-csv"])
        self.assertEqual(rc,0)
        self.assertIn("Arquivos CSV/OFX nunca analisados: 1",out.getvalue())
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
