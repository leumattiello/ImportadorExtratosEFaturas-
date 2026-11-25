"""Testes sinteticos da leitura consultiva dos quadros M:T."""
from unittest import TestCase

from importador_extratos.catalogo_gateway import (
    ErroLeituraCatalogo, ler_catalogo_subcategorias,
)
from importador_extratos.subcategorias import MESES


class Requisicao:
    def __init__(self, resposta):
        self.resposta = resposta

    def execute(self):
        return self.resposta


class Valores:
    def __init__(self, resposta, operacoes):
        self.resposta = resposta
        self.operacoes = operacoes

    def batchGet(self, **kwargs):
        self.operacoes.append(("batchGet", kwargs))
        return Requisicao(self.resposta)


class Api:
    def __init__(self, resposta):
        self.operacoes = []
        self.valores = Valores(resposta, self.operacoes)

    def spreadsheets(self):
        return self

    def values(self):
        return self.valores


def tabela():
    linhas = [[""] * 8 for _ in range(35)]
    for linha, coluna, texto in (
        (2, 0, "Habitação"), (2, 2, "Alimentação"),
        (2, 4, "Transportes"), (2, 6, "Financeiras e Impostos"),
        (20, 0, "Transferências"), (20, 2, "Despesas Gerais"),
        (3, 0, "Energia*"), (3, 2, "Supermercado*"),
        (3, 4, "Combustível*"), (3, 6, "IPTU*"),
        (21, 0, "Pessoa Exemplo*"), (22, 2, "Recarga Celular*"),
    ):
        linhas[linha - 2][coluna] = texto
    return linhas


def resposta(*, divergente=None, recortar=True):
    blocos = []
    for mes in MESES:
        linhas = [linha[:] for linha in tabela()]
        if divergente == mes:
            linhas[1][0] = "Eletricidade*"
        if recortar:
            # Simula a omissao de linhas/celulas vazias pelo Google Sheets.
            linhas = [linha[:max((i + 1 for i, v in enumerate(linha) if v), default=0)]
                      for linha in linhas]
            while linhas and not linhas[-1]:
                linhas.pop()
        blocos.append({"range": f"{mes}!M2:T36", "values": linhas})
    return {"valueRanges": blocos}


class TestesLeituraCatalogo(TestCase):
    def test_le_e_valida_doze_meses_sem_escrever(self):
        api = Api(resposta())
        itens = ler_catalogo_subcategorias(api, "planilha-ficticia")
        self.assertEqual(len(itens), 6)
        self.assertEqual(
            {item.nome: item.categoria for item in itens}["IPTU"],
            "Financeiras e Impostos",
        )
        self.assertEqual(len(api.operacoes), 1)
        nome, kwargs = api.operacoes[0]
        self.assertEqual(nome, "batchGet")
        self.assertEqual(kwargs["valueRenderOption"], "FORMATTED_VALUE")
        self.assertEqual(len(kwargs["ranges"]), 12)

    def test_divergencia_entre_meses_interrompe(self):
        api = Api(resposta(divergente="Outubro"))
        with self.assertRaisesRegex(ErroLeituraCatalogo, "inconsistente"):
            ler_catalogo_subcategorias(api, "ficticia")
        self.assertEqual(len(api.operacoes), 1)

    def test_retorno_incompleto_interrompe(self):
        dados = resposta()
        dados["valueRanges"].pop()
        with self.assertRaisesRegex(ErroLeituraCatalogo, "incompleta"):
            ler_catalogo_subcategorias(Api(dados), "ficticia")

    def test_intervalo_trocado_interrompe(self):
        dados = resposta()
        dados["valueRanges"][0]["range"] = "Janeiro!M3:T36"
        with self.assertRaisesRegex(ErroLeituraCatalogo, "Faixas"):
            ler_catalogo_subcategorias(Api(dados), "ficticia")
