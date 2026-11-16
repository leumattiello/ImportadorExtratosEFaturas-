"""Identificadores derivados para movimentos sem ID bancario confiavel.

Somente memoria, sem arquivos de estado. Nunca considera hash uma prova
de identidade; os casos derivados precisam ser revisados antes da escrita.
"""
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json

from .identidade import ErroIdentidade, gerar_id_automatico


@dataclass(frozen=True)
class IdentificacaoCandidata:
    identificador: str | None
    derivado: bool
    repeticoes: int
    ocorrencia: int
    base: str | None = None


def _dados(mov):
    """Dados estaveis independentemente da ordem dos extratos e da formatacao."""
    if not isinstance(mov.valor, Decimal) or not mov.valor.is_finite():
        raise ErroIdentidade("Valor invalido para identificador derivado.")
    valor = mov.valor
    if valor == 0 or valor != valor.quantize(Decimal("0.01")):
        raise ErroIdentidade("Valor invalido para identificador derivado.")
    if not isinstance(mov.descricao, str) or not mov.descricao.strip():
        raise ErroIdentidade("Descricao invalida para identificador derivado.")
    if not hasattr(mov.data, "isoformat"):
        raise ErroIdentidade("Data invalida para identificador derivado.")
    bruto = mov.identificador
    if bruto is not None and not isinstance(bruto, str):
        raise ErroIdentidade("Identificador externo invalido.")
    if isinstance(bruto, str) and (len(bruto) > 200 or any(ord(c) < 32 or ord(c) == 127 for c in bruto)):
        raise ErroIdentidade("Identificador externo invalido.")
    return (mov.data.isoformat(), format(valor, ".2f"),
            " ".join(mov.descricao.split()).casefold(),
            bruto.strip() if isinstance(bruto, str) else "")


def gerar_candidatos(movimentos, origem: str, conta: str, *, id_externo_confiavel: bool):
    """Gera IDs deterministas por ocorrencia indistinguivel dentro do arquivo.

    Um hash igual entre arquivos nao prova que houve reimportacao; o fluxo
    interativo deve perguntar ou bloquear escolhas automatizadas perigosas.
    """
    if not isinstance(id_externo_confiavel, bool):
        raise ErroIdentidade("Confiabilidade invalida.")
    gerar_id_automatico(origem, conta, None)
    movimentos = tuple(movimentos)
    dados = [_dados(m) for m in movimentos]
    precisa_derivar = [not (id_externo_confiavel and chave[3]) for chave in dados]
    hashes = [
        sha256(json.dumps(chave, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
        if precisa else None
        for chave, precisa in zip(dados, precisa_derivar)
    ]
    totais = Counter(h for h in hashes if h is not None)
    ocorrencias = Counter()
    resultado = []
    for m, h in zip(movimentos, hashes):
        if h is None:
            resultado.append(IdentificacaoCandidata(
                gerar_id_automatico(origem, conta, m.identificador), False, 1, 1))
        else:
            ocorrencias[h] += 1
            base = f"AUTO:{origem}:{conta}:DERIVADO:{h}"
            resultado.append(IdentificacaoCandidata(
                f"{base}:{ocorrencias[h]}", True, totais[h], ocorrencias[h], base))
    return tuple(resultado)


def proxima_ocorrencia(base: str, ids_reservados: set[str]) -> str:
    """Reserva ID distinto apos confirmacao humana; nunca escolhe um ID ocupado."""
    prefixo = base + ":"
    numeros = []
    for identificador in ids_reservados:
        if identificador.startswith(prefixo):
            sufixo = identificador[len(prefixo):]
            if sufixo.isdecimal() and len(sufixo) <= 15:
                numeros.append(int(sufixo))
    novo = max(numeros, default=0) + 1
    if novo > 10**12:
        raise ErroIdentidade("Excesso de ocorrencias indistinguiveis.")
    return f"{prefixo}{novo}"
