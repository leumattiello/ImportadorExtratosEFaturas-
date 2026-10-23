"""Testes com nomes ficticios; nenhum dado financeiro real e usado."""

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from importador_extratos.__main__ import main  # noqa: E402


class EntradaInicialTests(unittest.TestCase):
    def test_execucao_nao_importa(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            exit_code = main()
        self.assertEqual(exit_code, 0)
        self.assertIn("Nenhum arquivo financeiro", output.getvalue())


@unittest.skipUnless(shutil.which("git"), "Git nao instalado")
class GitignoreTests(unittest.TestCase):
    def ignorado(self, caminho: str) -> bool:
        command = ["git", "check-ignore", "-q", "--", caminho]
        result = subprocess.run(
            command, cwd=ROOT, capture_output=True, check=False, timeout=10
        )
        self.assertIn(result.returncode, (0, 1), result.stderr.decode(errors="replace"))
        return result.returncode == 0

    def test_arquivos_sensiveis_ficticios_sao_ignorados(self) -> None:
        caminhos = (
            "extratos/2026/amostra.ofx",
            "faturas/2027/amostra.csv",
            "dados/2026/amostra.xlsx",
            "historico/controle.sqlite",
            ".env",
            ".env.local",
            "tokens.json",
            "config.local.toml",
            "credenciais.pem",
            "logs/importacao.log",
        )
        for caminho in caminhos:
            with self.subTest(caminho=caminho):
                self.assertTrue(self.ignorado(caminho))

    def test_codigo_e_documentacao_nao_sao_ignorados(self) -> None:
        for caminho in ("README.md", "docs/PRIVACIDADE.md", "src/importador_extratos/__main__.py"):
            with self.subTest(caminho=caminho):
                self.assertFalse(self.ignorado(caminho))


if __name__ == "__main__":
    unittest.main()
