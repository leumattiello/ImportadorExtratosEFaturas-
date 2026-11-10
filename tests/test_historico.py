"""Testes do historico privado com nomes e movimentacoes ficticios."""

import csv
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from hashlib import sha256
import sys
from unittest import TestCase

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from importador_extratos.__main__ import main
from importador_extratos.inventario import ArquivoFonte
from importador_extratos.historico import registrar_tentativa, ErroHistorico, NOME_HISTORICO, CABECALHO


class HistoricoTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.raiz = self.base / "ExtratosFaturas"
        (self.raiz / "2026").mkdir(parents=True)
        self.origem = self.raiz / "2026" / "FICTICIO.csv"
        self.origem.write_bytes(b"Data;Descricao;Valor\n01/11/2026;Item ficticio;-1,00\n")
        self.info = self.fonte()
        self.log = self.base / NOME_HISTORICO

    def fonte(self):
        b = self.origem.read_bytes()
        return ArquivoFonte(self.origem, 2026, ".csv", len(b), sha256(b).hexdigest(), False)

    def linhas(self):
        with self.log.open(encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f, delimiter=";"))

    def test_analise_somente_em_historico_e_original_preservado(self):
        estado = (self.origem.read_bytes(), self.origem.stat().st_mtime_ns)
        registrar_tentativa(self.raiz, self.info, "ANALISADO", 1)
        self.assertEqual(estado, (self.origem.read_bytes(), self.origem.stat().st_mtime_ns))
        self.assertEqual(len(self.linhas()), 1)
        self.assertEqual(self.linhas()[0]["resultado"], "ANALISADO")
        self.assertEqual(self.linhas()[0]["arquivo"], "2026/FICTICIO.csv")
        self.assertEqual(self.linhas()[0]["movimentacoes"], "1")
        self.assertEqual(self.linhas()[0]["sha256"], self.info.sha256)
        self.assertNotIn("Item ficticio", self.log.read_text())

    def test_repeticao_registra_outra_tentativa_sem_falso_importado(self):
        registrar_tentativa(self.raiz, self.info, "ANALISADO", 1)
        registrar_tentativa(self.raiz, self.info, "ANALISADO", 1)
        self.assertEqual([x["resultado"] for x in self.linhas()], ["ANALISADO", "ANALISADO"])
        self.assertNotIn("IMPORTADO", self.log.read_text())

    def test_falha_fica_identificada_com_quantidade_zero(self):
        registrar_tentativa(self.raiz, self.info, "ERRO", 0)
        self.assertEqual(self.linhas()[0]["movimentacoes"], "0")
        self.assertEqual(self.linhas()[0]["resultado"], "ERRO")

    def test_alteracao_entre_inventario_e_log_nega_sucesso(self):
        self.origem.write_bytes(b"dados alterados")
        with self.assertRaisesRegex(ErroHistorico, "alterado"):
            registrar_tentativa(self.raiz, self.info, "ANALISADO", 1)
        self.assertFalse(self.log.exists())

    def test_rejeita_symlink_para_historico(self):
        alvo = self.base / "alvo.csv"
        alvo.write_text("NAO ALTERAR")
        try:
            self.log.symlink_to(alvo)
        except OSError:
            self.skipTest("Sem symlink")
        with self.assertRaises(ErroHistorico):
            registrar_tentativa(self.raiz, self.info, "ANALISADO", 1)
        self.assertEqual(alvo.read_text(), "NAO ALTERAR")

    def test_header_invalido_nega_append(self):
        self.log.write_text("outro,cabecalho\n")
        if os.name == "posix":
            self.log.chmod(0o600)
        with self.assertRaisesRegex(ErroHistorico, "Formato"):
            registrar_tentativa(self.raiz, self.info, "ANALISADO", 1)
        self.assertEqual(self.log.read_text(), "outro,cabecalho\n")

    def test_permissoes_restritas_posix(self):
        if os.name != "posix":
            self.skipTest("POSIX")
        registrar_tentativa(self.raiz, self.info, "ANALISADO", 1)
        self.assertEqual(self.log.stat().st_mode & 0o777, 0o600)

    def test_rejeita_informacao_fora_raiz(self):
        with self.assertRaises(ErroHistorico):
            registrar_tentativa(self.raiz, self.info.__class__(
                self.base / "fora.csv", 2026, ".csv", 0, "a" * 64, False), "ERRO", 0)

    def test_rejeita_estado_importado(self):
        with self.assertRaises(ErroHistorico):
            registrar_tentativa(self.raiz, self.info, "IMPORTADO", 1)
        self.assertFalse(self.log.exists())

    def test_nome_csv_com_caracteres_especiais(self):
        self.origem = self.raiz / "2026" / "arquivo;teste.csv"
        self.origem.write_bytes(b"FICTICIO")
        registrar_tentativa(self.raiz, self.fonte(), "ERRO", 0)
        self.assertEqual(self.linhas()[0]["arquivo"], "2026/arquivo;teste.csv")

    def test_header_constante(self):
        registrar_tentativa(self.raiz, self.info, "ANALISADO", 1)
        with self.log.open(encoding="utf-8") as f:
            self.assertEqual(f.readline().strip(), ";".join(CABECALHO))

    def test_cli_sem_opcao_nao_cria_historico(self):
        self.assertEqual(main(["--pasta", str(self.raiz), "--analisar-csv"]), 0)
        self.assertFalse(self.log.exists())

    def test_cli_com_opcao_grava_tentativa_csv(self):
        self.assertEqual(main(["--pasta", str(self.raiz), "--analisar-csv",
                               "--registrar-historico"]), 0)
        self.assertEqual(len(self.linhas()), 1)
        self.assertEqual(self.linhas()[0]["resultado"], "ANALISADO")
        self.assertEqual(self.linhas()[0]["movimentacoes"], "1")

    def test_cli_com_opcao_registra_falha_sem_financas(self):
        self.origem.write_bytes(b"Data;Descricao;Valor\n01/11/2026;PRIVADO;INVALIDO\n")
        self.assertEqual(main(["--pasta", str(self.raiz), "--analisar-csv",
                               "--registrar-historico"]), 1)
        self.assertEqual(self.linhas()[0]["resultado"], "ERRO")
        self.assertNotIn("PRIVADO", self.log.read_text())

    def test_cli_repetir_nao_duplica_cabecalho(self):
        for i in range(2):
            self.assertEqual(main(["--pasta", str(self.raiz), "--analisar-csv",
                                   "--registrar-historico"]), 0)
        self.assertEqual(len(self.linhas()), 2)
        with self.log.open(encoding="utf-8") as f:
            self.assertEqual(sum(1 for row in f if row.startswith("processado_em;")), 1)
