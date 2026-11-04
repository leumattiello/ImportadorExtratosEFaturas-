"""Inventario local somente leitura. Nao interpreta nem importa operacoes."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re

FORMATOS = frozenset({".csv", ".ofx", ".xlsx"})
_ANO = re.compile(r"^[0-9]{4}$")
_BLOCO = 1024 * 1024


class ErroInventario(Exception):
    """Erro controlado: nao divulgar nomes de arquivos privados."""


@dataclass(frozen=True)
class ArquivoFonte:
    caminho: Path
    ano_competencia: int
    formato: str
    bytes: int
    sha256: str
    possivel_repeticao: bool


@dataclass(frozen=True)
class Inventario:
    arquivos: tuple[ArquivoFonte, ...]
    ignorados: int
    anos: tuple[int, ...]

    @property
    def possiveis_repetidos(self) -> int:
        return sum(a.possivel_repeticao for a in self.arquivos)


def _assinatura(caminho: Path) -> tuple[int, str]:
    try:
        antes = caminho.stat()
        digest = sha256()
        with caminho.open("rb") as origem:
            while bloco := origem.read(_BLOCO):
                digest.update(bloco)
        depois = caminho.stat()
        if (antes.st_size, antes.st_mtime_ns) != (depois.st_size, depois.st_mtime_ns):
            raise ErroInventario("Um arquivo mudou durante a leitura; repita a operacao.")
    except OSError as exc:
        raise ErroInventario("Nao foi possivel ler um arquivo; verifique o acesso.") from exc
    return depois.st_size, digest.hexdigest()


def inventariar(pasta_raiz: Path) -> Inventario:
    """Inspeciona arquivos diretos das pastas AAAA, sem seguir links simbolicos."""
    raiz = Path(pasta_raiz).expanduser()
    if raiz.is_symlink() or not raiz.is_dir():
        raise ErroInventario("Pasta raiz inexistente, invalida ou link simbolico.")
    arquivos: list[ArquivoFonte] = []
    anos: list[int] = []
    ignorados = 0
    vistos: set[str] = set()
    try:
        for pasta in sorted(raiz.iterdir(), key=lambda p: p.name.casefold()):
            if pasta.is_symlink() or not _ANO.fullmatch(pasta.name) or not pasta.is_dir():
                ignorados += 1
                continue
            ano = int(pasta.name)
            anos.append(ano)
            for caminho in sorted(pasta.iterdir(), key=lambda p: p.name.casefold()):
                if caminho.is_symlink() or not caminho.is_file() or caminho.suffix.lower() not in FORMATOS:
                    ignorados += 1
                    continue
                tamanho, assinatura = _assinatura(caminho)
                repetido = assinatura in vistos
                vistos.add(assinatura)
                arquivos.append(ArquivoFonte(
                    caminho=caminho, ano_competencia=ano,
                    formato=caminho.suffix.lower(), bytes=tamanho,
                    sha256=assinatura, possivel_repeticao=repetido,
                ))
    except OSError as exc:
        raise ErroInventario("Nao foi possivel percorrer as pastas; verifique o acesso.") from exc
    return Inventario(tuple(arquivos), ignorados, tuple(anos))
