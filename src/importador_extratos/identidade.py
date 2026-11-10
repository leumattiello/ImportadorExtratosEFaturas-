"""Identidade conservadora de lancamentos; nunca grava ou altera a planilha.

A planilha e a fonte de verdade. O chamador fornece as linhas das 12 abas;
a busca aqui e puramente em memoria e nao precisa de banco de dados.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import re
from urllib.parse import quote

_SISTEMA = re.compile(r"[A-Z0-9_-]{1,40}\Z")
_ID_LIMITE = 200
_SITUACOES = frozenset({"NOVO", "JA_EXISTENTE", "CONFLITO", "REVISAR"})


class ErroIdentidade(Exception):
    """Erro controlado: nao reproduz dados de movimentacoes ou da planilha."""


@dataclass(frozen=True)
class Lancamento:
    data: date
    descricao: str
    valor: Decimal
    identificador: str | None = None


@dataclass(frozen=True)
class ResultadoIdentidade:
    situacao: str
    id_proposto: str | None
    motivo: str


def gerar_id_automatico(origem: str, conta: str, identificador_externo: str | None) -> str | None:
    """Mantem o ID externo intacto; escapa separadores para evitar colisoes.

    Os codigos de origem e conta precisam ser definidos explicitamente pelo
    usuario: nao se deduz instituicao por nome de arquivo ou cabecalho.
    """
    for codigo in (origem, conta):
        if not isinstance(codigo, str) or not _SISTEMA.fullmatch(codigo):
            raise ErroIdentidade("Origem e conta exigem codigos estaveis A-Z, 0-9, _ ou -.")
    if identificador_externo is None:
        return None
    if (not isinstance(identificador_externo, str)
            or len(identificador_externo) > _ID_LIMITE
            or any(ord(c) < 32 or ord(c) == 127 for c in identificador_externo)):
        raise ErroIdentidade("Identificador bancario invalido.")
    if not identificador_externo.strip():
        return None
    return f"AUTO:{origem}:{conta}:{quote(identificador_externo, safe='-_.~')}"


def eh_manual(identificador: str | None) -> bool:
    return isinstance(identificador, str) and identificador.startswith("MAN:")


def _chave(m: Lancamento) -> tuple[date, Decimal, str]:
    if (not isinstance(m.data, date) or not isinstance(m.valor, Decimal)
            or not m.valor.is_finite() or not isinstance(m.descricao, str)):
        raise ErroIdentidade("Movimentacao invalida para verificacao de identidade.")
    return (m.data, m.valor, " ".join(m.descricao.split()).casefold())


def analisar_identificadores(
    movimentos: tuple[Lancamento, ...] | list[Lancamento],
    existentes: tuple[Lancamento, ...] | list[Lancamento],
    *,
    origem: str,
    conta: str,
    id_externo_confiavel: bool,
) -> tuple[ResultadoIdentidade, ...]:
    """Classifica candidatos sem atribuir ID a registros antigos e sem gravar.

    id_externo_confiavel deve ser True apenas apos validar a unicidade
    da origem (p.ex. FITID de conta OFX); numero de documento generico
    normalmente exige revisao.
    """
    if not isinstance(id_externo_confiavel, bool):
        raise ErroIdentidade("Confiabilidade de identificador invalida.")
    movimentos = tuple(movimentos)
    existentes = tuple(existentes)
    # Valida os codigos mesmo quando o lote nao tem identificadores.
    gerar_id_automatico(origem, conta, None)
    por_id: dict[str, list[tuple[date, Decimal, str]]] = {}
    por_dados: dict[tuple[date, Decimal], set[str | None]] = {}
    for m in existentes:
        chave = _chave(m)
        ident = m.identificador.strip() if isinstance(m.identificador, str) else None
        if ident:
            por_id.setdefault(ident, []).append(chave)
        por_dados.setdefault((chave[0], chave[1]), set()).add(ident)

    candidatos = []
    for mov in movimentos:
        chave = _chave(mov)
        ident = gerar_id_automatico(origem, conta, mov.identificador)
        candidatos.append((chave, ident))
    multiplicidade = Counter(ident for _, ident in candidatos if ident is not None)
    saida = []
    for chave, ident in candidatos:
        if ident is None:
            situacao, motivo = "REVISAR", "sem_identificador"
        elif multiplicidade[ident] > 1:
            situacao, motivo = "REVISAR", "id_repetido_no_lote"
        elif ident in por_id:
            if len(por_id[ident]) != 1 or por_id[ident][0] != chave:
                situacao, motivo = "CONFLITO", "mesmo_id_dados_divergentes_ou_repetido"
            elif not id_externo_confiavel:
                situacao, motivo = "REVISAR", "mesmo_id_externo_nao_confiavel"
            else:
                situacao, motivo = "JA_EXISTENTE", "mesmo_id_e_dados"
        elif not id_externo_confiavel:
            situacao, motivo = "REVISAR", "id_externo_nao_confiavel"
        elif (chave[0], chave[1]) in por_dados:
            # Comparar somente data/valor nao significa que seja duplicado.
            # Nunca descartar uma despesa legitima por coincidencia.
            situacao, motivo = "REVISAR", "possivel_sobreposicao"
        else:
            situacao, motivo = "NOVO", "id_nao_encontrado"
        if situacao not in _SITUACOES:
            raise ErroIdentidade("Resultado de verificacao invalido.")
        saida.append(ResultadoIdentidade(situacao, ident, motivo))
    return tuple(saida)
