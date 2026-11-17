"""Testes exclusivamente sinteticos para o catalogo RF-065/P8."""
from unittest import TestCase

from importador_extratos.subcategorias import (
    ErroSubcategoria, carregar_catalogo, classificar_descricao, MESES,
)


def catalogo_exemplo():
    tabela = [[""] * 8 for _ in range(35)]
    for row, col, value in (
        (2, 0, "Habitação"), (2, 2, "Alimentação"),
        (2, 4, "Transportes"), (2, 6, "Financeiras e Impostos"),
        (20, 0, "Transferências"), (20, 2, "Despesas Gerais"),
        (3, 0, "Energia*"), (8, 0, "Aluguel*"),
        (3, 2, "Supermercado*"), (4, 4, "Combustível*"),
        (6, 6, "IPTU*"), (21, 0, "Pessoa Exemplo*"),
        (22, 2, "Recarga Celular*"), (36, 2, "Desconhecido*"),
    ):
        tabela[row - 2][col] = value
    return {mes: [linha[:] for linha in tabela] for mes in MESES}


class TestesCadastro(TestCase):
    def test_seis_categorias_e_posicoes(self):
        itens = carregar_catalogo(catalogo_exemplo())
        self.assertEqual(
            {x.nome: (x.categoria, x.celula) for x in itens},
            {
                "Energia": ("Habitação", "M3"),
                "Aluguel": ("Habitação", "M8"),
                "Supermercado": ("Alimentação", "O3"),
                "Combustível": ("Transportes", "Q4"),
                "IPTU": ("Financeiras e Impostos", "S6"),
                "Pessoa Exemplo": ("Transferências", "M21"),
                "Recarga Celular": ("Despesas Gerais", "O22"),
                "Desconhecido": ("Despesas Gerais", "O36"),
            },
        )

    def test_posicoes_vazias_sao_ignoradas(self):
        self.assertEqual(len(carregar_catalogo(catalogo_exemplo())), 8)

    def test_mes_divergente_e_recusado(self):
        dados = catalogo_exemplo()
        dados["Outubro"][1][0] = "Eletricidade*"
        with self.assertRaisesRegex(ErroSubcategoria, "divergentes"):
            carregar_catalogo(dados)

    def test_ausencia_de_mes_e_recusada(self):
        dados = catalogo_exemplo()
        del dados["Janeiro"]
        with self.assertRaises(ErroSubcategoria):
            carregar_catalogo(dados)

    def test_cabecalho_diferente_e_recusado(self):
        dados = catalogo_exemplo()
        dados["Dezembro"][18][2] = "Outros"
        with self.assertRaisesRegex(ErroSubcategoria, "Cabecalho"):
            carregar_catalogo(dados)

    def test_nome_duplicado_bloqueia(self):
        dados = catalogo_exemplo()
        for mes in MESES:
            dados[mes][2][0] = "Energia*"
        with self.assertRaises(ErroSubcategoria):
            carregar_catalogo(dados)

    def test_prefixo_conflitante_bloqueia(self):
        dados = catalogo_exemplo()
        for mes in MESES:
            dados[mes][3][0] = "Energia Solar*"
        with self.assertRaises(ErroSubcategoria):
            carregar_catalogo(dados)

    def test_curinga_invalido_bloqueia(self):
        dados = catalogo_exemplo()
        for mes in MESES:
            dados[mes][1][0] = "Ener*gia*"
        with self.assertRaises(ErroSubcategoria):
            carregar_catalogo(dados)


class TestesClassificacao(TestCase):
    def setUp(self):
        self.itens = carregar_catalogo(catalogo_exemplo())

    def test_escolha_constroi_prefixo_e_categoria(self):
        r = classificar_descricao(self.itens, "Compra fictícia", "Supermercado")
        self.assertEqual(
            (r.subcategoria, r.categoria, r.descricao),
            ("Supermercado", "Alimentação", "Supermercado - Compra fictícia"),
        )

    def test_descricao_ja_prefixada_nao_duplica(self):
        r = classificar_descricao(self.itens, "IPTU - Taxa fictícia")
        self.assertEqual(
            (r.categoria, r.descricao),
            ("Financeiras e Impostos", "IPTU - Taxa fictícia"),
        )

    def test_prefixo_e_escolha_conflitantes_bloqueiam(self):
        with self.assertRaisesRegex(ErroSubcategoria, "diverge"):
            classificar_descricao(
                self.itens, "Energia - Exemplo", "Aluguel"
            )

    def test_descricao_nao_classificada_exige_escolha(self):
        with self.assertRaisesRegex(ErroSubcategoria, "requer escolha"):
            classificar_descricao(self.itens, "Compra sem prefixo")

    def test_escolha_inexistente_nao_cria_categoria(self):
        with self.assertRaises(ErroSubcategoria):
            classificar_descricao(self.itens, "Compra fictícia", "Outra")

    def test_nome_com_acentos_preservado(self):
        r = classificar_descricao(self.itens, "Serviço fictício", "Recarga Celular")
        self.assertEqual(r.descricao, "Recarga Celular - Serviço fictício")

    def test_nao_reconhece_palavra_solamente(self):
        with self.assertRaises(ErroSubcategoria):
            classificar_descricao(self.itens, "IPTU pendente sem separador")
