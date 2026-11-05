"""Leitura local e conservadora de CSVs financeiros, sem efeitos colaterais.

Nao tenta inferir competencia, classificar contas ou gravar transacoes.
Em caso de ambiguidades, rejeita a entrada em vez de assumir valores.
"""

import csv
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import StringIO
from pathlib import Path
import re
import unicodedata

MAX_BYTES = 20 * 1024 * 1024
DELIMITADORES = (";", ",", "\t")


class ErroCSV(Exception):
    """Falha controlada: nao inclui caminhos, valores ou descricoes privadas."""


@dataclass(frozen=True)
class MovimentoCSV:
    data: date
    descricao: str
    valor: Decimal
    identificador: str | None


@dataclass(frozen=True)
class ColunasCSV:
    data: str | None = None
    descricao: str | None = None
    valor: str | None = None
    credito: str | None = None
    debito: str | None = None
    identificador: str | None = None
    separador_descricao: str = " - "


_ALIASES = {
    "data": ("data", "data lancamento", "data do lancamento", "data movimento",
             "data movimentacao", "data transacao", "data da transacao",
             "data operacao", "data da operacao", "date", "transaction date"),
    "descricao": ("descricao", "descricao da transacao", "historico", "historico lancamento",
                  "lancamento", "detalhes", "estabelecimento", "description", "memo"),
    "valor": ("valor", "valor r", "valor em reais", "valor da transacao", "amount",
              "valor lancamento", "valor do lancamento"),
    "credito": ("credito", "creditos", "entrada", "entradas", "valor credito", "credit"),
    "debito": ("debito", "debitos", "saida", "saidas", "valor debito", "debit"),
    "identificador": ("id", "identificador", "id transacao", "id da transacao",
                      "identificador da transacao", "numero da transacao", "fitid", "nsu", "transaction id"),
}


def _normalizar(cabecalho: str) -> str:
    letras = unicodedata.normalize("NFKD", cabecalho).casefold()
    letras = "".join(c for c in letras if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", letras).strip()


def _ler_texto(caminho: Path) -> str:
    caminho = Path(caminho)
    if caminho.is_symlink() or not caminho.is_file() or caminho.suffix.lower() != ".csv":
        raise ErroCSV("Arquivo CSV invalido ou link simbolico.")
    try:
        antes = caminho.stat()
        if antes.st_size > MAX_BYTES:
            raise ErroCSV("Arquivo CSV excede o limite de tamanho.")
        with caminho.open("rb") as arquivo:
            conteudo = arquivo.read(MAX_BYTES + 1)
        depois = caminho.stat()
    except OSError as exc:
        raise ErroCSV("Nao foi possivel ler um arquivo CSV.") from exc
    if len(conteudo) > MAX_BYTES:
        raise ErroCSV("Arquivo CSV excede o limite de tamanho.")
    if (antes.st_size, antes.st_mtime_ns) != (depois.st_size, depois.st_mtime_ns):
        raise ErroCSV("Um arquivo mudou durante a leitura; repita a operacao.")
    try:
        texto = conteudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            texto = conteudo.decode("cp1252", errors="strict")
        except UnicodeDecodeError as exc:
            raise ErroCSV("Codificacao CSV nao suportada.") from exc
    if "\x00" in texto:
        raise ErroCSV("Conteudo CSV invalido.")
    return texto


def _separador(texto: str, escolhido: str | None, linhas_ignoradas: int) -> str:
    if escolhido is not None:
        if escolhido == "tab":
            return "\t"
        if escolhido not in DELIMITADORES:
            raise ErroCSV("Delimitador CSV nao suportado.")
        return escolhido
    trecho = "".join(texto.splitlines(keepends=True)[linhas_ignoradas:])
    propostas: list[tuple[int, int, str]] = []
    for delimitador in DELIMITADORES:
        try:
            cabecalho = next(csv.reader(StringIO(trecho, newline=""), delimiter=delimitador, strict=True))
        except (csv.Error, StopIteration):
            continue
        if len(cabecalho) <= 1:
            continue
        conhecidos = sum(
            _normalizar(nome) in {alias for grupo in _ALIASES.values() for alias in grupo}
            for nome in cabecalho
        )
        propostas.append((conhecidos, len(cabecalho), delimitador))
    if not propostas:
        raise ErroCSV("Delimitador CSV nao identificado; informe --csv-delimitador.")
    propostas.sort(reverse=True)
    if len(propostas) > 1 and propostas[0][:2] == propostas[1][:2]:
        raise ErroCSV("Delimitador CSV ambiguo; informe --csv-delimitador.")
    return propostas[0][2]


def _posicao(cabecalhos: list[str], nome: str, manual: str | None) -> int | None:
    opcoes = {_normalizar(manual)} if manual else set(_ALIASES[nome])
    indices = [i for i, h in enumerate(cabecalhos) if _normalizar(h) in opcoes]
    if len(indices) > 1:
        raise ErroCSV(f"Colunas ambiguas para {nome}; especifique o cabecalho exato.")
    if manual and not indices:
        raise ErroCSV(f"Coluna configurada para {nome} nao encontrada no cabecalho.")
    return indices[0] if indices else None


def _indices_descricao(cabecalhos: list[str], configurada: str | None) -> tuple[int, ...] | None:
    """Resolve uma ou varias colunas em ordem, sem aceitar ambiguidades."""
    if configurada is None:
        unica = _posicao(cabecalhos, "descricao", None)
        return (unica,) if unica is not None else None
    nomes = [nome.strip() for nome in configurada.split("|")]
    normalizados = [_normalizar(nome) for nome in nomes]
    if (not 1 <= len(nomes) <= 16 or any(not nome for nome in normalizados)
            or len(set(normalizados)) != len(nomes)):
        raise ErroCSV("Configuracao de colunas de descricao invalida.")
    indices = []
    for nome in nomes:
        indice = _posicao(cabecalhos, "descricao", nome)
        if indice is None:
            raise ErroCSV("Coluna de descricao nao encontrada.")
        indices.append(indice)
    return tuple(indices)


def _escolher_colunas(cabecalhos: list[str], config: ColunasCSV) -> dict[str, int | tuple[int, ...] | None]:
    if not cabecalhos or any(not c.strip() for c in cabecalhos):
        raise ErroCSV("Cabecalho CSV invalido.")
    colunas = {
        nome: _posicao(cabecalhos, nome, getattr(config, nome))
        for nome in _ALIASES if nome != "descricao"
    }
    colunas["descricao"] = _indices_descricao(cabecalhos, config.descricao)
    if colunas["data"] is None or colunas["descricao"] is None:
        raise ErroCSV("Nao foi possivel identificar as colunas de data e descricao.")
    if config.valor and (config.credito or config.debito):
        raise ErroCSV("Escolha valor unico ou colunas de credito/debito, nao ambos.")
    if config.valor:
        colunas["credito"] = colunas["debito"] = None
    elif config.credito or config.debito:
        colunas["valor"] = None
    elif colunas["valor"] is not None and (
        colunas["credito"] is not None or colunas["debito"] is not None
    ):
        raise ErroCSV("Valor e credito/debito coexistem; escolha colunas explicitamente.")
    if colunas["valor"] is None and colunas["credito"] is None and colunas["debito"] is None:
        raise ErroCSV("Nao foi possivel identificar as colunas monetarias.")
    indices = [
        indice
        for entrada in colunas.values()
        for indice in (entrada if isinstance(entrada, tuple)
                       else ((entrada,) if entrada is not None else ()))
    ]
    if len(indices) != len(set(indices)):
        raise ErroCSV("A mesma coluna foi atribuida a diferentes campos.")
    return colunas


def _data(valor: str) -> date:
    texto = valor.strip()
    for formato in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d",
                    "%d/%m/%y", "%Y%m%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    raise ErroCSV("Data CSV invalida ou formato de data nao suportado.")


def _quantia(valor: str) -> Decimal:
    texto = re.sub(r"\s+", "", valor).replace("R$", "")
    negativo = texto.startswith("(") and texto.endswith(")")
    if negativo:
        texto = texto[1:-1]
    formato_pt = r"[+-]?\d{1,3}(?:\.\d{3})+,[0-9]{1,2}"
    formato_en = r"[+-]?\d{1,3}(?:,\d{3})+\.[0-9]{1,2}"
    formato_simples = r"[+-]?\d+(?:[.,][0-9]{1,2})?"
    if re.fullmatch(formato_pt, texto):
        texto = texto.replace(".", "").replace(",", ".")
    elif re.fullmatch(formato_en, texto):
        texto = texto.replace(",", "")
    elif re.fullmatch(formato_simples, texto):
        texto = texto.replace(",", ".")
    else:
        raise ErroCSV("Valor monetario CSV invalido ou ambiguo.")
    try:
        numero = Decimal(texto)
    except InvalidOperation as exc:
        raise ErroCSV("Valor monetario CSV invalido.") from exc
    if negativo:
        if numero.is_signed():
            raise ErroCSV("Sinal de valor CSV ambiguo.")
        numero = -numero
    if not numero.is_finite():
        raise ErroCSV("Valor monetario CSV invalido.")
    return numero


def _extrair_quantia(linha: list[str], indices: dict[str, int | None]) -> Decimal:
    if indices["valor"] is not None:
        return _quantia(linha[indices["valor"]])
    credito = linha[indices["credito"]].strip() if indices["credito"] is not None else ""
    debito = linha[indices["debito"]].strip() if indices["debito"] is not None else ""
    c = _quantia(credito) if credito else Decimal("0")
    d = _quantia(debito) if debito else Decimal("0")
    if c < 0 or d < 0 or (c != 0 and d != 0) or (c == 0 and d == 0):
        raise ErroCSV("Colunas de credito/debito inconsistentes.")
    return c - d


def ler_csv(
    caminho: Path, *, colunas: ColunasCSV | None = None,
    delimitador: str | None = None, pular_linhas: int = 0,
) -> tuple[MovimentoCSV, ...]:
    """Interpreta CSV com cabecalho; aborta integralmente em caso de ambiguidade."""
    if pular_linhas < 0:
        raise ErroCSV("Numero de linhas ignoradas invalido.")
    config = colunas or ColunasCSV()
    separador_descricao = config.separador_descricao
    if (not isinstance(separador_descricao, str) or len(separador_descricao) > 40
            or any(ord(caractere) < 32 or ord(caractere) == 127
                   for caractere in separador_descricao)):
        raise ErroCSV("Separador de descricao invalido.")
    conteudo = _ler_texto(caminho)
    separador = _separador(conteudo, delimitador, pular_linhas)
    dados = "".join(conteudo.splitlines(keepends=True)[pular_linhas:])
    try:
        linhas = csv.reader(StringIO(dados, newline=""), delimiter=separador, strict=True)
        cabecalho = next(linhas)
        indices = _escolher_colunas(cabecalho, config)
        movimentos = []
        for linha in linhas:
            numero = pular_linhas + linhas.line_num
            if not any(c.strip() for c in linha):
                continue
            if len(linha) != len(cabecalho):
                raise ErroCSV(f"Quantidade de campos invalida na linha {numero}.")
            try:
                partes = [
                    linha[indice].strip()
                    for indice in indices["descricao"]
                    if linha[indice].strip()
                ]
                if not partes:
                    raise ErroCSV("Descricao CSV ausente.")
                descricao = separador_descricao.join(partes)
                ident = indices["identificador"]
                movimentos.append(MovimentoCSV(
                    data=_data(linha[indices["data"]]), descricao=descricao,
                    valor=_extrair_quantia(linha, indices),
                    identificador=linha[ident].strip() or None if ident is not None else None,
                ))
            except ErroCSV as exc:
                raise ErroCSV(f"Linha {numero}: {exc}") from exc
    except StopIteration as exc:
        raise ErroCSV("CSV vazio ou sem cabecalho.") from exc
    except csv.Error as exc:
        raise ErroCSV("Estrutura CSV malformada.") from exc
    if not movimentos:
        raise ErroCSV("CSV sem movimentacoes para leitura.")
    return tuple(movimentos)
