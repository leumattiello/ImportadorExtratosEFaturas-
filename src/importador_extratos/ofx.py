"""Leitura estritamente local de transacoes OFX (XML e SGML)."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from html import unescape
from pathlib import Path
import re

MAX_BYTES = 20 * 1024 * 1024
_TRANSACAO = re.compile(r"<STMTTRN\s*>(.*?)(?=</STMTTRN\s*>|<STMTTRN\s*>|</BANKTRANLIST\s*>|\Z)", re.I | re.S)
_TAG = re.compile(r"<([A-Z][A-Z0-9_]*)\s*>\s*([^<\r\n]*)", re.I)


class ErroOFX(Exception):
    """Falha controlada sem copiar conteudo financeiro na mensagem."""


@dataclass(frozen=True)
class Movimento:
    data: date
    valor: Decimal
    descricao: str
    identificador: str | None
    tipo: str | None


def _decodificar(conteudo: bytes) -> str:
    inicio = conteudo[:1024].decode("ascii", errors="ignore")
    declaracao = re.search(r'<\?xml[^>]*encoding=["\']([\w-]+)', inicio, re.I)
    if declaracao:
        encoding = declaracao.group(1).lower()
    elif re.search(r'(?im)^CHARSET\s*:\s*1252\s*$', inicio):
        encoding = "cp1252"
    elif re.search(r'(?im)^ENCODING\s*:\s*UNICODE\s*$', inicio):
        encoding = "utf-16"
    else:
        encoding = "utf-8"
    if encoding not in {"utf-8", "utf8", "utf-16", "iso-8859-1", "latin1",
                        "windows-1252", "cp1252", "us-ascii", "ascii"}:
        raise ErroOFX("Codificacao OFX nao suportada.")
    try:
        return conteudo.decode(encoding, errors="strict").lstrip("\ufeff")
    except UnicodeError as exc:
        raise ErroOFX("Nao foi possivel decodificar o OFX.") from exc


def _campos(bloco: str) -> dict[str, str]:
    return {chave.upper(): unescape(valor.strip()) for chave, valor in _TAG.findall(bloco)}


def _movimento(campos: dict[str, str]) -> Movimento:
    try:
        bruto = campos["DTPOSTED"]
        if not re.fullmatch(r"\d{8}(?:\d{6}(?:\.\d+)?)?(?:\[[^\]]+\])?", bruto):
            raise ValueError("data")
        data = date(int(bruto[:4]), int(bruto[4:6]), int(bruto[6:8]))
        quantia = campos["TRNAMT"]
        if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)", quantia):
            raise ValueError("quantia")
        valor = Decimal(quantia)
        if not valor.is_finite():
            raise ValueError("quantia")
    except (KeyError, ValueError, InvalidOperation) as exc:
        raise ErroOFX("Transacao OFX com data ou valor invalido.") from exc
    descricao = campos.get("NAME") or campos.get("MEMO") or ""
    return Movimento(data=data, valor=valor, descricao=descricao,
                     identificador=campos.get("FITID") or None,
                     tipo=campos.get("TRNTYPE") or None)


def ler_ofx(caminho: Path) -> tuple[Movimento, ...]:
    """Le um arquivo OFX sem modificar seu conteudo nem produzir saida/log."""
    caminho = Path(caminho)
    if caminho.is_symlink() or not caminho.is_file():
        raise ErroOFX("Arquivo OFX invalido ou link simbolico.")
    try:
        if caminho.stat().st_size > MAX_BYTES:
            raise ErroOFX("Arquivo OFX excede o limite de tamanho.")
        with caminho.open("rb") as origem:
            conteudo = origem.read(MAX_BYTES + 1)
    except OSError as exc:
        raise ErroOFX("Nao foi possivel ler o arquivo OFX.") from exc
    if len(conteudo) > MAX_BYTES:
        raise ErroOFX("Arquivo OFX excede o limite de tamanho.")
    texto = _decodificar(conteudo)
    if not re.search(r"<OFX(?:\s[^>]*)?>", texto, re.I):
        raise ErroOFX("Estrutura OFX nao reconhecida.")
    blocos = _TRANSACAO.findall(texto)
    if not blocos:
        raise ErroOFX("Nenhuma transacao STMTTRN encontrada no OFX.")
    return tuple(_movimento(_campos(bloco)) for bloco in blocos)
