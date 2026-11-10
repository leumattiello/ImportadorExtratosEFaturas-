"""Testes exclusivamente ficticios da identidade e deduplicacao preliminar."""

from datetime import date
from decimal import Decimal
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from importador_extratos.identidade import (
    ErroIdentidade, Lancamento, analisar_identificadores,
    eh_manual, gerar_id_automatico,
)


def lanc(data="2026-11-01", desc="Mercado ficticio", valor="-10.50", id=None):
    return Lancamento(date.fromisoformat(data), desc, Decimal(valor), id)


class IdentidadeTests(unittest.TestCase):
    def analisar(self, novos, antigos=(), confiavel=True, origem="BB", conta="CC1"):
        return analisar_identificadores(
            novos, antigos, origem=origem, conta=conta,
            id_externo_confiavel=confiavel,
        )

    def test_prefixo_manual(self):
        self.assertTrue(eh_manual("MAN:2026-0001"))
        self.assertFalse(eh_manual("AUTO:BB:CC1:123"))
        self.assertFalse(eh_manual(None))

    def test_id_automatico_com_origem_e_conta(self):
        self.assertEqual(
            gerar_id_automatico("BB", "CC1", "000123"),
            "AUTO:BB:CC1:000123",
        )
        self.assertNotEqual(
            gerar_id_automatico("BB", "CC1", "000123"),
            gerar_id_automatico("BB", "CC2", "000123"),
        )
        self.assertNotEqual(
            gerar_id_automatico("BB", "CC1", "000123"),
            gerar_id_automatico("NUBANK", "CC1", "000123"),
        )

    def test_escape_dos_separadores_e_sem_colisoes(self):
        self.assertEqual(
            gerar_id_automatico("BB", "CC1", "A:B/C%"),
            "AUTO:BB:CC1:A%3AB%2FC%25",
        )
        self.assertNotEqual(
            gerar_id_automatico("BB", "CC1", "A:B"),
            gerar_id_automatico("BB", "CC1", "A%3AB"),
        )

    def test_identificador_ausente(self):
        self.assertIsNone(gerar_id_automatico("BB", "CC1", None))
        self.assertIsNone(gerar_id_automatico("BB", "CC1", ""))

    def test_codigo_invalido(self):
        for origem, conta in (("BB:", "CC1"), ("", "CC1"), ("BB", "CC 1")):
            with self.subTest(origem=origem, conta=conta):
                with self.assertRaises(ErroIdentidade):
                    gerar_id_automatico(origem, conta, "123")

    def test_id_novo_confiavel(self):
        self.assertEqual(self.analisar([lanc(id="100")])[0].situacao, "NOVO")

    def test_id_ja_existente_mesmos_dados(self):
        registrado = lanc(id="AUTO:BB:CC1:100")
        resultado = self.analisar([lanc(id="100")], [registrado])[0]
        self.assertEqual(resultado.situacao, "JA_EXISTENTE")

    def test_id_existente_dados_divergentes(self):
        registrado = lanc(desc="Mercado ficticio", id="AUTO:BB:CC1:100")
        resultado = self.analisar([lanc(desc="Compra diferente", id="100")],
                                 [registrado])[0]
        self.assertEqual(resultado.situacao, "CONFLITO")

    def test_id_duplicado_na_planilha(self):
        registrado = lanc(id="AUTO:BB:CC1:100")
        resultado = self.analisar([lanc(id="100")],
                                 [registrado, registrado])[0]
        self.assertEqual(resultado.situacao, "CONFLITO")

    def test_id_duplicado_no_mesmo_lote(self):
        situacoes = [r.situacao for r in self.analisar(
            [lanc(id="100"), lanc(id="100")]
        )]
        self.assertEqual(situacoes, ["REVISAR", "REVISAR"])

    def test_ausencia_de_id_exige_revisao(self):
        resultado = self.analisar([lanc(id=None)])[0]
        self.assertEqual((resultado.situacao, resultado.id_proposto),
                         ("REVISAR", None))

    def test_documento_nao_confiavel_exige_revisao(self):
        self.assertEqual(
            self.analisar([lanc(id="123")], confiavel=False)[0].situacao,
            "REVISAR",
        )

    def test_coincidencia_data_valor_nao_elimina_movimento(self):
        manual = lanc(desc="Despesa em dinheiro", id="MAN:2026-0001")
        resultado = self.analisar([lanc(desc="Compra no cartao", id="100")],
                                 [manual])[0]
        self.assertEqual(resultado.situacao, "REVISAR")
        self.assertEqual(manual.identificador, "MAN:2026-0001")

    def test_sem_coincidencia_mantem_novo(self):
        antigo = lanc(valor="-99.99", id="MAN:1")
        self.assertEqual(
            self.analisar([lanc(id="100")], [antigo])[0].situacao,
            "NOVO",
        )

    def test_sem_alteracao_de_entradas(self):
        novos = [lanc(id="100")]
        antigos = [lanc(id="MAN:1")]
        antes = (tuple(novos), tuple(antigos))
        self.analisar(novos, antigos)
        self.assertEqual(antes, (tuple(novos), tuple(antigos)))

    def test_descricoes_espacos_e_maiusculas_equivalentes(self):
        antigo = lanc(desc="Mercado   FICTICIO", id="AUTO:BB:CC1:100")
        self.assertEqual(
            self.analisar([lanc(id="100")], [antigo])[0].situacao,
            "JA_EXISTENTE",
        )

    def test_mesmo_id_contas_distintas_sem_colisao(self):
        antigo = lanc(id="AUTO:BB:CC2:100")
        self.assertEqual(
            self.analisar([lanc(id="100")], [antigo])[0].situacao,
            "NOVO",
        )

    def test_nao_aceita_valor_invalido(self):
        com_nan = lanc(valor="NaN", id="100")
        with self.assertRaises(ErroIdentidade):
            self.analisar([com_nan])

    def test_movimentacao_nao_confiavel_nao_importa_sozinha(self):
        novo = lanc(id="100")
        self.assertEqual(self.analisar([novo], confiavel=False)[0].situacao,
                         "REVISAR")

    def test_id_nao_confiavel_ja_existente_exige_revisao(self):
        antigo = lanc(id="AUTO:BB:CC1:100")
        self.assertEqual(
            self.analisar([lanc(id="100")], [antigo], confiavel=False)[0].situacao,
            "REVISAR",
        )

    def test_tipo_de_id_invalido_com_erro_controlado(self):
        with self.assertRaises(ErroIdentidade):
            gerar_id_automatico("BB", "CC1", 123)



if __name__ == "__main__":
    unittest.main()
