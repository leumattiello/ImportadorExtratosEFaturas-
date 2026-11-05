"""Perfis privados de mapeamento CSV, escolhidos por cabecalho, nao por nome."""

import configparser
import csv
from io import StringIO
from dataclasses import dataclass
from pathlib import Path
import re

from .leitor_csv import ColunasCSV, ErroCSV, _ler_texto, _separador, _normalizar

_LIMITE_CONFIG = 128 * 1024
_LIMITE_PERFIS = 50
_CAMPOS = ("data", "descricao", "valor", "credito", "debito", "identificador")
_OPCOES = {"requer_colunas", "delimitador", "pular_linhas", "separador_descricao", *_CAMPOS}


class ErroPerfis(Exception):
    """Erro controlado que nao divulga o conteudo nem o caminho do arquivo."""


@dataclass(frozen=True)
class PerfilCSV:
    identificacao: frozenset[str]
    colunas: ColunasCSV
    delimitador: str | None
    pular_linhas: int


def _fora_do_repositorio(arquivo: Path) -> bool:
    raiz_git = Path(__file__).resolve().parents[2]
    caminho = arquivo.resolve()
    return caminho != raiz_git and raiz_git not in caminho.parents


def ler_perfis(arquivo: Path) -> tuple[PerfilCSV, ...]:
    """Le apenas configuracao local externa ao repo; nunca imprime o conteudo."""
    caminho = Path(arquivo).expanduser()
    if caminho.is_symlink() or not _fora_do_repositorio(caminho):
        raise ErroPerfis("O arquivo de perfis deve ficar fora do repositorio e nao ser link.")
    try:
        if not caminho.is_file() or caminho.stat().st_size > _LIMITE_CONFIG:
            raise ErroPerfis("Arquivo de perfis inexistente, invalido ou muito grande.")
        texto = caminho.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise ErroPerfis("Nao foi possivel ler o arquivo de perfis privado.") from exc
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    try:
        parser.read_string(texto)
    except configparser.Error as exc:
        raise ErroPerfis("Estrutura do arquivo de perfis invalida.") from exc
    if parser.defaults() or not parser.sections() or len(parser.sections()) > _LIMITE_PERFIS:
        raise ErroPerfis("O arquivo de perfis deve conter secoes de perfis validas.")
    saida = []
    for secao in parser.sections():
        if not re.fullmatch(r"perfil:[A-Za-z0-9_-]{1,40}", secao):
            raise ErroPerfis("Nome de secao de perfil invalido.")
        opcoes = parser[secao]
        if set(opcoes) - _OPCOES or "requer_colunas" not in opcoes:
            raise ErroPerfis("Opcao obrigatoria ausente ou desconhecida no perfil.")
        exigidas = [_normalizar(x) for x in opcoes["requer_colunas"].split("|")]
        if len(exigidas) < 2 or any(not x for x in exigidas) or len(set(exigidas)) != len(exigidas):
            raise ErroPerfis("Cada perfil exige ao menos duas colunas distintas para identificacao.")
        delim = opcoes.get("delimitador")
        if delim not in (None, ";", ",", "tab"):
            raise ErroPerfis("Delimitador de perfil invalido.")
        try:
            ignoradas = int(opcoes.get("pular_linhas", "0"))
        except ValueError as exc:
            raise ErroPerfis("Numero de linhas introdutorias invalido.") from exc
        if ignoradas < 0 or ignoradas > 50:
            raise ErroPerfis("Numero de linhas introdutorias fora do limite.")
        mapeamento = {campo: opcoes.get(campo) or None for campo in _CAMPOS}
        if any(valor is not None and not _normalizar(valor) for valor in mapeamento.values()):
            raise ErroPerfis("Nome de coluna configurada invalido.")
        if mapeamento["valor"] and (mapeamento["credito"] or mapeamento["debito"]):
            raise ErroPerfis("Perfil nao pode misturar valor e credito/debito configurados.")
        if mapeamento["descricao"] is not None:
            descricoes = [_normalizar(nome) for nome in mapeamento["descricao"].split("|")]
            if (not 1 <= len(descricoes) <= 16 or any(not nome for nome in descricoes)
                    or len(set(descricoes)) != len(descricoes)):
                raise ErroPerfis("Lista de colunas de descricao invalida.")
        separador = opcoes.get("separador_descricao")
        if separador is None:
            separador = " - "
        elif len(separador) >= 2 and separador[0] == separador[-1] and separador[0] in ("'", '"'):
            separador = separador[1:-1]
        elif "'" in separador or '"' in separador:
            raise ErroPerfis("Separador de descricao invalido.")
        if len(separador) > 40 or any(ord(c) < 32 or ord(c) == 127 for c in separador):
            raise ErroPerfis("Separador de descricao invalido.")
        saida.append(PerfilCSV(
            identificacao=frozenset(exigidas),
            colunas=ColunasCSV(**mapeamento, separador_descricao=separador),
            delimitador=delim, pular_linhas=ignoradas,
        ))
    return tuple(saida)


def _cabecalhos_csv(caminho: Path, delimitador: str | None, pular_linhas: int) -> tuple[str, ...]:
    """Le somente a estrutura do cabecalho usando o mesmo parser do CSV."""
    texto = _ler_texto(caminho)
    separador = _separador(texto, delimitador, pular_linhas)
    dados = "".join(texto.splitlines(keepends=True)[pular_linhas:])
    try:
        return tuple(next(csv.reader(StringIO(dados, newline=""), delimiter=separador, strict=True)))
    except (StopIteration, csv.Error) as exc:
        raise ErroCSV("Cabecalho CSV invalido.") from exc


def selecionar_perfil(caminho: Path, perfis: tuple[PerfilCSV, ...]) -> PerfilCSV:
    """Falha fechado se nenhum perfil ou mais de um perfil corresponder."""
    cabecalhos: dict[tuple[str | None, int], frozenset[str] | None] = {}
    correspondencias: list[PerfilCSV] = []
    for perfil in perfis:
        chave = (perfil.delimitador, perfil.pular_linhas)
        if chave not in cabecalhos:
            try:
                nomes = _cabecalhos_csv(caminho, delimitador=chave[0], pular_linhas=chave[1])
                cabecalhos[chave] = frozenset(_normalizar(n) for n in nomes)
            except ErroCSV:
                cabecalhos[chave] = None
        nomes = cabecalhos[chave]
        if nomes is not None and perfil.identificacao.issubset(nomes):
            correspondencias.append(perfil)
    if not correspondencias:
        raise ErroPerfis("Nenhum perfil CSV corresponde ao cabecalho; revise a configuracao privada.")
    if len(correspondencias) > 1:
        raise ErroPerfis("Mais de um perfil corresponde ao CSV; ajuste os cabecalhos exigidos.")
    return correspondencias[0]
