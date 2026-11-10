"""Registro privado e local de tentativas de leitura; nunca marca importacao."""

import csv
from datetime import datetime
from pathlib import Path
import os
import re
import stat

from .inventario import ArquivoFonte, ErroInventario, _assinatura

NOME_HISTORICO = "historico_importacoes.csv"
CABECALHO = ("processado_em", "arquivo", "formato", "resultado", "movimentacoes", "sha256")
RESULTADOS = frozenset({"ANALISADO", "ERRO"})


class ErroHistorico(Exception):
    """Erro controlado, sem divulgar nomes, caminhos ou dados privados."""


def registrar_tentativa(raiz: Path, arquivo: ArquivoFonte,
                       resultado: str, movimentacoes: int) -> None:
    """Acrescenta uma linha ao CSV privado, preservando os extratos originais.

    ANAlISADO confirma apenas a interpretacao, nunca a importacao no Sheets.
    """
    if (resultado not in RESULTADOS or not isinstance(movimentacoes, int)
            or movimentacoes < 0 or (resultado == "ERRO" and movimentacoes != 0)):
        raise ErroHistorico("Parametros de registro de tentativa invalidos.")
    try:
        pasta = Path(raiz).expanduser().resolve(strict=True)
        caminho_fonte = arquivo.caminho.resolve(strict=True)
        relativo = caminho_fonte.relative_to(pasta)
        if len(relativo.parts) != 2 or not re.fullmatch(r"[0-9]{4}", relativo.parts[0]):
            raise ErroHistorico("Arquivo de origem fora das pastas anuais.")
        if not re.fullmatch(r"[0-9a-f]{64}", arquivo.sha256):
            raise ErroHistorico("Assinatura de arquivo invalida.")
        destino = pasta.parent / NOME_HISTORICO
        raiz_codigo = Path(__file__).resolve().parents[2]
        destino_resolvido = destino.resolve()
        if (destino.is_symlink() or destino_resolvido == raiz_codigo
                or raiz_codigo in destino_resolvido.parents):
            raise ErroHistorico("O historico precisa ficar fora do repositorio e nao pode ser link.")
        if resultado == "ANALISADO":
            tamanho, assinatura = _assinatura(arquivo.caminho)
            if (tamanho, assinatura) != (arquivo.bytes, arquivo.sha256):
                raise ErroHistorico("Arquivo alterado entre inventario e leitura; historico nao atualizado.")
    except (OSError, ValueError, ErroInventario) as exc:
        raise ErroHistorico("Nao foi possivel validar a origem do registro.") from exc

    flags = os.O_RDWR | os.O_APPEND | os.O_CREAT
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descritor = os.open(destino, flags, 0o600)
        with os.fdopen(descritor, "a+", encoding="utf-8", newline="") as registro:
            info = os.fstat(registro.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise ErroHistorico("Destino do historico nao e um arquivo regular.")
            if os.name == "posix" and stat.S_IMODE(info.st_mode) & 0o077:
                raise ErroHistorico("Permissoes do historico excessivamente abertas; use chmod 600.")
            registro.seek(0)
            cabecalho_existente = registro.readline(256).rstrip("\r\n")
            cabecalho_esperado = ";".join(CABECALHO)
            if cabecalho_existente and cabecalho_existente != cabecalho_esperado:
                raise ErroHistorico("Formato do historico existente nao reconhecido.")
            registro.seek(0, os.SEEK_END)
            gravador = csv.writer(registro, delimiter=";", lineterminator="\n")
            if registro.tell() == 0:
                gravador.writerow(CABECALHO)
            gravador.writerow((
                datetime.now().astimezone().isoformat(timespec="seconds"),
                relativo.as_posix(), arquivo.formato, resultado, movimentacoes,
                arquivo.sha256,
            ))
            registro.flush()
            os.fsync(registro.fileno())
    except OSError as exc:
        raise ErroHistorico("Nao foi possivel gravar o historico local privado.") from exc
