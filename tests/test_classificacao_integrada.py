"""Testes exclusivamente sinteticos de classificacao contábil RF-065."""
from datetime import date
from decimal import Decimal
from unittest import TestCase
from unittest.mock import patch

from importador_extratos.fluxo_importacao import (
    ErroFluxo, _classificar, _natureza, _subcategoria,
)
from importador_extratos.identidade import Lancamento
from importador_extratos.subcategorias import Subcategoria


CATALOGO = (
    Subcategoria("Energia", "Habitação", "M3"),
    Subcategoria("IPTU", "Financeiras e Impostos", "S6"),
    Subcategoria("Recarga Celular", "Despesas Gerais", "O22"),
    Subcategoria("Pessoa Exemplo", "Transferências", "M21"),
)
CONTAS = {"Habitação", "Financeiras e Impostos", "Despesas Gerais",
          "Transferências", "Receitas", "Banco Próprio"}
def mov(descricao="Operação fictícia", valor="-12.50"):
    return Lancamento(date(2026, 11, 5), descricao, Decimal(valor), None)


class TestesClassificacaoIntegrada(TestCase):
    def test_despesa_inferida_sem_categoria_adicional(self):
        r = _classificar(mov(), CONTAS, CATALOGO, natureza="despesa",
                        subcategoria="Energia", assumir_sim=True)
        self.assertEqual(r, ("Habitação", "Energia - Operação fictícia"))

    def test_prefixo_ja_existe_sem_duplicar(self):
        r = _classificar(mov("IPTU - Taxa fictícia"), CONTAS, CATALOGO,
                        natureza="despesa")
        self.assertEqual(r, ("Financeiras e Impostos", "IPTU - Taxa fictícia"))

    def test_subcategoria_conflitante_bloqueia(self):
        with self.assertRaises(ErroFluxo):
            _classificar(mov("IPTU - Taxa fictícia"), CONTAS, CATALOGO,
                         natureza="despesa", subcategoria="Energia")

    def test_natureza_nao_inferida_do_sinal(self):
        for valor in ("12.50", "-12.50"):
            with self.assertRaises(ErroFluxo):
                _classificar(mov(valor=valor), CONTAS, CATALOGO,
                             assumir_sim=True)

    def test_receita_preserva_descricao_sem_prefixo(self):
        r = _classificar(mov(valor="12.50"), CONTAS, CATALOGO,
                        natureza="outra", categoria="Receitas", assumir_sim=True)
        self.assertEqual(r, ("Receitas", "Operação fictícia"))

    def test_transferencia_patrimonial_nao_vira_despesa(self):
        r = _classificar(mov("Transferência fictícia"), CONTAS, CATALOGO,
                        natureza="outra", categoria="Banco Próprio",
                        assumir_sim=True)
        self.assertEqual(r, ("Banco Próprio", "Transferência fictícia"))

    def test_subcategoria_proibida_em_outra_natureza(self):
        with self.assertRaises(ErroFluxo):
            _classificar(mov(), CONTAS, CATALOGO, natureza="outra",
                         subcategoria="Pessoa Exemplo")

    def test_categoria_principal_nao_substitui_subcategoria(self):
        with self.assertRaises(ErroFluxo):
            _classificar(mov(), CONTAS, CATALOGO, natureza="despesa",
                         categoria="Habitação")

    def test_categoria_inferida_ausente_bloqueia(self):
        with self.assertRaisesRegex(ErroFluxo, "Dados"):
            _classificar(mov(), {"Receitas"}, CATALOGO,
                         natureza="despesa", subcategoria="Energia")

    def test_sem_subcategoria_nao_autoclassifica_y(self):
        with self.assertRaises(ErroFluxo):
            _classificar(mov(), CONTAS, CATALOGO, natureza="despesa",
                         assumir_sim=True)

    def test_escolha_interativa_com_valor(self):
        perguntas = []
        def responder(pergunta):
            perguntas.append(pergunta)
            return "Recarga Celular"
        with patch("importador_extratos.fluxo_importacao.sys.stdin.isatty",
                   return_value=True):
            r = _subcategoria(mov(valor="-1234.50"), CATALOGO, entrada=responder)
        self.assertEqual(r.categoria, "Despesas Gerais")
        self.assertEqual(r.descricao, "Recarga Celular - Operação fictícia")
        self.assertIn("R$ -1.234,50", perguntas[0])

    def test_natureza_interativa_pergunta(self):
        with patch("importador_extratos.fluxo_importacao.sys.stdin.isatty",
                   return_value=True):
            self.assertEqual(_natureza(mov(), entrada=lambda _: "d"), "despesa")
            self.assertEqual(_natureza(mov(), entrada=lambda _: "o"), "outra")

    def test_nome_inexistente_bloqueia(self):
        with self.assertRaises(ErroFluxo):
            _classificar(mov(), CONTAS, CATALOGO, natureza="despesa",
                         subcategoria="Subcategoria inexistente")

    def test_estorno_exige_natureza_explicita(self):
        with self.assertRaises(ErroFluxo):
            _classificar(mov("Estorno de compra", valor="20.00"),
                         CONTAS, CATALOGO, assumir_sim=True)

    def test_prefixo_desconhecido_nao_e_reconhecido(self):
        with self.assertRaises(ErroFluxo):
            _classificar(mov("Outra - Operação fictícia"), CONTAS, CATALOGO,
                         natureza="despesa", assumir_sim=True)
