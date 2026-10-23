"""Testes sinteticos criados apenas em diretorios temporarios."""

from contextlib import redirect_stderr, redirect_stdout
from hashlib import sha256
from io import StringIO
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from importador_extratos.__main__ import main  # noqa: E402
from importador_extratos.inventario import ErroInventario, inventariar  # noqa: E402


class InventarioTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.raiz = Path(self.temp.name)
        (self.raiz / "2026").mkdir()
        (self.raiz / "2027").mkdir()

    def escrever(self, nome: str, dados: bytes) -> Path:
        p = self.raiz / nome
        p.write_bytes(dados)
        return p

    def test_preserva_arquivos(self) -> None:
        a = self.escrever("2026/exemplo.csv", b"data;valor\n01;1\n")
        b = self.escrever("2027/outro.OFX", b"FICTICIO")
        antes = [(p.read_bytes(), p.stat().st_mtime_ns) for p in (a, b)]
        resultado = inventariar(self.raiz)
        self.assertEqual(antes, [(p.read_bytes(), p.stat().st_mtime_ns) for p in (a, b)])
        self.assertEqual(resultado.anos, (2026, 2027))
        self.assertEqual(len(resultado.arquivos), 2)
        self.assertEqual(resultado.arquivos[0].sha256, sha256(a.read_bytes()).hexdigest())

    def test_hash_igual_nao_descarta_documento(self) -> None:
        self.escrever("2026/um.csv", b"ficticio")
        self.escrever("2027/dois.csv", b"ficticio")
        r = inventariar(self.raiz)
        self.assertEqual(len(r.arquivos), 2)
        self.assertEqual(r.possiveis_repetidos, 1)

    def test_regras_de_pastas_e_extensoes(self) -> None:
        self.escrever("fora.csv", b"x")
        self.escrever("2026/exemplo.pdf", b"x")
        self.escrever("2027/exemplo.xlsx", b"x")
        (self.raiz / "2026" / "subpasta").mkdir()
        r = inventariar(self.raiz)
        self.assertEqual((len(r.arquivos), r.ignorados), (1, 3))

    def test_saida_nao_expoe_nomes_privados(self) -> None:
        self.escrever("2026/NOME-CONFIDENCIAL-FICTICIO.csv", b"amostra")
        saida = StringIO()
        with redirect_stdout(saida):
            self.assertEqual(main(["--pasta", str(self.raiz)]), 0)
        self.assertIn("Arquivos candidatos: 1", saida.getvalue())
        self.assertNotIn("NOME-CONFIDENCIAL", saida.getvalue())
        self.assertNotIn(str(self.raiz), saida.getvalue())

    def test_erro_sem_expor_caminho(self) -> None:
        p = self.raiz / "PASTA-PRIVADA"
        saida = StringIO()
        with redirect_stderr(saida):
            self.assertEqual(main(["--pasta", str(p)]), 1)
        self.assertNotIn("PASTA-PRIVADA", saida.getvalue())
        with self.assertRaises(ErroInventario):
            inventariar(p)

    def test_sem_parametros_nao_acessa_documentos(self) -> None:
        saida = StringIO()
        with redirect_stdout(saida):
            self.assertEqual(main([]), 0)
        self.assertIn("Nenhum arquivo financeiro", saida.getvalue())
