"""Consulta somente leitura de hashes previamente analisados no historico local."""

import csv
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Iterable

from .historico import CABECALHO, ErroHistorico, NOME_HISTORICO, RESULTADOS
from .inventario import ArquivoFonte

MAX_HISTORICO_BYTES = 20 * 1024 * 1024
_FORMATOS_ANALISADOS = frozenset({".csv", ".ofx"})
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ANO = re.compile(r"[0-9]{4}\Z")


@dataclass(frozen=True)
class ResumoHistorico:
    arquivos_csv_ofx: int
    nunca_analisados: int
    ja_analisados: int
    com_erro_anterior: int


def _verificar_linha(linha: list[str]) -> tuple[str, str]:
    """Valida a estrutura sem divulgar campos confidenciais em excecoes."""
    if len(linha) != len(CABECALHO):
        raise ErroHistorico("Linha invalida no historico local.")
    data, arquivo, formato, resultado, quantidade, assinatura = linha
    partes = PurePosixPath(arquivo).parts
    try:
        horario = datetime.fromisoformat(data)
        numero = int(quantidade)
    except ValueError as exc:
        raise ErroHistorico("Dados invalidos no historico local.") from exc
    if (horario.tzinfo is None or len(partes) != 2
            or not _ANO.fullmatch(partes[0])
            or formato not in _FORMATOS_ANALISADOS
            or not partes[1].lower().endswith(formato)
            or resultado not in RESULTADOS
            or numero < 0 or (resultado == "ERRO" and numero != 0)
            or not _SHA.fullmatch(assinatura)):
        raise ErroHistorico("Dados invalidos no historico local.")
    return assinatura, resultado


def consultar_historico(raiz: Path, arquivos: Iterable[ArquivoFonte]) -> ResumoHistorico:
    """Classifica arquivos pelo hash, sem bloquear processamento ou alterar nada.

    Um hash com qualquer ANALISADO e conhecido; apenas ERRO indica falha previa.
    Os contadores representam arquivos, nao hashes distintos nem importacoes.
    """
    candidatos = tuple(a for a in arquivos if a.formato in _FORMATOS_ANALISADOS)
    try:
        pasta = Path(raiz).expanduser().resolve(strict=True)
        destino = pasta.parent / NOME_HISTORICO
        raiz_codigo = Path(__file__).resolve().parents[2]
        destino_resolvido = destino.resolve()
        if (destino.is_symlink() or destino_resolvido == raiz_codigo
                or raiz_codigo in destino_resolvido.parents):
            raise ErroHistorico("O historico precisa ficar fora do repositorio e nao pode ser link.")
        flags = os.O_RDONLY
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        if hasattr(os, "O_NONBLOCK"):
            flags |= os.O_NONBLOCK
        try:
            descritor = os.open(destino, flags)
        except FileNotFoundError:
            return ResumoHistorico(len(candidatos), len(candidatos), 0, 0)
        with os.fdopen(descritor, "r", encoding="utf-8", newline="") as arquivo:
            info = os.fstat(arquivo.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise ErroHistorico("Destino do historico nao e arquivo regular.")
            if os.name == "posix" and stat.S_IMODE(info.st_mode) & 0o077:
                raise ErroHistorico("Permissoes do historico excessivamente abertas; use chmod 600.")
            if info.st_size > MAX_HISTORICO_BYTES:
                raise ErroHistorico("Arquivo de historico excede limite de tamanho.")
            linhas = csv.reader(arquivo, delimiter=";", strict=True)
            if tuple(next(linhas, ())) != CABECALHO:
                raise ErroHistorico("Formato do historico existente nao reconhecido.")
            estados: dict[str, str] = {}
            for linha in linhas:
                assinatura, resultado = _verificar_linha(linha)
                if resultado == "ANALISADO" or assinatura not in estados:
                    estados[assinatura] = resultado
    except ErroHistorico:
        raise
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        raise ErroHistorico("Nao foi possivel consultar o historico local privado.") from exc
    ja = sum(estados.get(a.sha256) == "ANALISADO" for a in candidatos)
    erro = sum(estados.get(a.sha256) == "ERRO" for a in candidatos)
    return ResumoHistorico(len(candidatos), len(candidatos) - ja - erro, ja, erro)
