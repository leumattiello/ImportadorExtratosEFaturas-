"""Leitura exclusivamente consultiva do cadastro RF-065 nas doze abas.

A matriz M2:T36 e obtida da propria planilha; nao replica nomes no codigo.
Falhas de API ou divergencias de cadastro interrompem a classificacao.
"""
from .subcategorias import MESES, ErroSubcategoria, carregar_catalogo


class ErroLeituraCatalogo(Exception):
    """Falha controlada sem expor valores privados do cadastro."""


def ler_catalogo_subcategorias(servico, planilha_id):
    """Retorna as subcategorias validadas, sem alterar a planilha.

    O endpoint values.batchGet pode omitir linhas/celulas finais vazias.
    Normalizamos para uma matriz de 35 linhas por 8 colunas, preservando
    a posicao original para a validacao feita por carregar_catalogo.
    """
    ranges = [f"'{mes}'!M2:T36" for mes in MESES]
    try:
        api = servico.spreadsheets()
        resposta = api.values().batchGet(
            spreadsheetId=planilha_id,
            ranges=ranges,
            valueRenderOption="FORMATTED_VALUE",
        ).execute()
        blocos = resposta.get("valueRanges", [])
        if len(blocos) != len(MESES):
            raise ErroLeituraCatalogo("Leitura incompleta dos quadros M:T.")
        por_mes = {}
        for mes, faixa, bloco in zip(MESES, ranges, blocos):
            # Confirmar que cada bloco corresponde a faixa esperada.
            retornada = bloco.get("range", "")
            if retornada.replace("$", "") != faixa:
                raise ErroLeituraCatalogo("Faixas de cadastro divergentes na API.")
            linhas = bloco.get("values", [])
            if len(linhas) > 35 or any(not isinstance(l, list) or len(l) > 8
                                      for l in linhas):
                raise ErroLeituraCatalogo("Dimensoes invalidas no cadastro.")
            matriz = [(linha + [""] * (8 - len(linha)))
                      for linha in linhas]
            matriz.extend([[""] * 8 for _ in range(35 - len(matriz))])
            por_mes[mes] = matriz
        return carregar_catalogo(por_mes)
    except ErroLeituraCatalogo:
        raise
    except ErroSubcategoria as exc:
        raise ErroLeituraCatalogo("Cadastro inconsistente; revise M2:T36 nas 12 abas.") from exc
    except Exception as exc:
        raise ErroLeituraCatalogo("Falha na leitura do cadastro de subcategorias.") from exc
