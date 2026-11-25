"""Cadastro lateral de subcategorias (RF-065/P8), sem acesso a dados financeiros.

Recebe os valores M2:T36 das doze abas mensais, lidos em modo somente leitura.
A categoria e determinada pela posicao; nao depende da aba Dados.
"""
from dataclasses import dataclass
from unicodedata import normalize

MESES = ("Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
         "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro")
CATEGORIAS = {
    (0, 2): "Habitação",
    (2, 2): "Alimentação",
    (4, 2): "Transportes",
    (6, 2): "Financeiras e Impostos",
    (0, 20): "Transferências",
    (2, 20): "Despesas Gerais",
}
# Indices das colunas relativos a M:T; indices das linhas sao os da planilha.
FAIXAS = ((0, 3, 18, "Habitação"),
          (2, 3, 18, "Alimentação"),
          (4, 3, 18, "Transportes"),
          (6, 3, 18, "Financeiras e Impostos"),
          (0, 21, 36, "Transferências"),
          (2, 21, 36, "Despesas Gerais"))


class ErroSubcategoria(ValueError):
    """Inconsistencia de cadastro ou classificacao ambigua."""


@dataclass(frozen=True)
class Subcategoria:
    nome: str
    categoria: str
    celula: str


@dataclass(frozen=True)
class Classificacao:
    subcategoria: str
    categoria: str
    descricao: str


def _chave(texto):
    return normalize("NFC", texto).casefold()


def _nome(valor):
    if not isinstance(valor, str):
        if valor in (None, ""):
            return ""
        raise ErroSubcategoria("Cadastro contem um nome que nao e texto.")
    nome = valor.strip()
    if nome.endswith("*"):
        nome = nome[:-1].strip()
    if "*" in nome or not nome:
        if nome:
            raise ErroSubcategoria("Curinga de subcategoria invalido.")
        return ""
    if " - " in nome:
        raise ErroSubcategoria("Nome de subcategoria contem separador reservado.")
    return nome


def _extrair(linhas):
    """Le M2:T36 (35 linhas, ate oito colunas), sem alterar valores."""
    if not isinstance(linhas, (tuple, list)) or len(linhas) != 35:
        raise ErroSubcategoria("Cadastro M2:T36 incompleto.")
    nomes = {}
    for coluna, inicio, fim, categoria in FAIXAS:
        for numero in range(inicio, fim + 1):
            linha = linhas[numero - 2]
            if not isinstance(linha, (tuple, list)):
                raise ErroSubcategoria("Linha de cadastro invalida.")
            valor = linha[coluna] if len(linha) > coluna else ""
            nome = _nome(valor)
            if nome:
                nomes[(coluna, numero)] = Subcategoria(
                    nome, categoria, f"{'MOQS'[coluna // 2]}{numero}")
    # Cabecalhos explicitam as seis categorias; nao inferir de formula ou saldo.
    for (coluna, numero), esperado in CATEGORIAS.items():
        linha = linhas[numero - 2]
        encontrado = linha[coluna] if len(linha) > coluna else None
        if encontrado != esperado:
            raise ErroSubcategoria("Cabecalho de categoria divergente.")
    return nomes


def carregar_catalogo(por_mes):
    """Dezembro e a referencia; todos os outros meses devem coincidir.

    por_mes: mapeamento exato dos doze nomes de meses para matrizes M2:T36.
    Retorna tupla imutavel de  subcategorias em ordem de posicao.
    """
    if not isinstance(por_mes, dict) or set(por_mes) != set(MESES):
        raise ErroSubcategoria("Esperadas exatamente as doze abas mensais.")
    referencia = _extrair(por_mes["Dezembro"])
    if not referencia:
        raise ErroSubcategoria("Cadastro sem subcategorias.")
    for mes in MESES:
        if _extrair(por_mes[mes]) != referencia:
            raise ErroSubcategoria("Subcategorias divergentes entre meses.")
    nomes = list(referencia.values())
    for i, atual in enumerate(nomes):
        for anterior in nomes[:i]:
            a, b = _chave(atual.nome), _chave(anterior.nome)
            if a == b or a.startswith(b) or b.startswith(a):
                raise ErroSubcategoria("Subcategorias repetidas ou prefixos conflitantes.")
    return tuple(nomes)


def classificar_descricao(catalogo, descricao, escolha=None):
    """Reconhece prefixo valido ou aplica escolha explicita.

    Nunca adivinha uma subcategoria; recusa conflito entre prefixo e escolha.
    Recebimentos e transferencias patrimoniais exigem tratamento contábil separado
    no fluxo chamador, que deve decidir se a classificacao e aplicavel.
    """
    if not isinstance(descricao, str) or not descricao.strip():
        raise ErroSubcategoria("Descricao vazia.")
    if not catalogo:
        raise ErroSubcategoria("Cadastro vazio.")
    por_nome = {_chave(item.nome): item for item in catalogo}
    if len(por_nome) != len(catalogo):
        raise ErroSubcategoria("Catalogo com nomes duplicados.")
    existentes = [item for item in catalogo
                  if _chave(descricao).startswith(_chave(item.nome + " - "))]
    if len(existentes) > 1:
        raise ErroSubcategoria("Prefixo ambiguo.")
    escolhida = por_nome.get(_chave(escolha.strip())) if isinstance(escolha, str) else None
    if escolha is not None and escolhida is None:
        raise ErroSubcategoria("Subcategoria escolhida inexistente.")
    reconhecida = existentes[0] if existentes else None
    if reconhecida and escolhida and reconhecida != escolhida:
        raise ErroSubcategoria("Prefixo existente diverge da escolha.")
    item = reconhecida or escolhida
    if item is None:
        raise ErroSubcategoria("Lancamento sem subcategoria: requer escolha.")
    texto = descricao if reconhecida else item.nome + " - " + descricao
    return Classificacao(item.nome, item.categoria, texto)
