"""Testes sinteticos: nenhum dado financeiro real."""

from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from importador_extratos.ofx import ErroOFX, ler_ofx  # noqa: E402

SGML = b'''OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\nENCODING:USASCII\nCHARSET:1252\n\n<OFX><BANKTRANLIST><STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260305120000[-3:BRT]<TRNAMT>-12.34<FITID>TESTE001<NAME>Compra ficticia</STMTTRN><STMTTRN><DTPOSTED>20260306<TRNAMT>5.60<MEMO>Estorno inventado</STMTTRN></BANKTRANLIST></OFX>'''
XML = b'''<?xml version="1.0" encoding="UTF-8"?><OFX><BANKTRANLIST><STMTTRN><DTPOSTED>20270101</DTPOSTED><TRNAMT>10.25</TRNAMT><FITID>EXEMPLO</FITID><NAME>Recebimento ficticio</NAME></STMTTRN></BANKTRANLIST></OFX>'''


class OFXTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)

    def escrever(self, texto):
        p = self.raiz / "exemplo.ofx"
        p.write_bytes(texto)
        return p

    def test_sgml_e_sinais(self):
        p = self.escrever(SGML)
        antes = (p.read_bytes(), p.stat().st_mtime_ns)
        mov = ler_ofx(p)
        self.assertEqual(len(mov), 2)
        self.assertEqual([x.valor for x in mov], [Decimal("-12.34"), Decimal("5.60")])
        self.assertEqual(str(mov[0].data), "2026-03-05")
        self.assertEqual(mov[0].identificador, "TESTE001")
        self.assertEqual(mov[1].descricao, "Estorno inventado")
        self.assertEqual(antes, (p.read_bytes(), p.stat().st_mtime_ns))

    def test_xml(self):
        x = ler_ofx(self.escrever(XML))
        self.assertEqual(len(x), 1)
        self.assertEqual(str(x[0].data), "2027-01-01")

    def test_invalido_nao_expoe_dados(self):
        for conteudo in (
            b"SECRETO",
            b"<OFX><STMTTRN><DTPOSTED>20260230<TRNAMT>-2<NAME>NOME CONFIDENCIAL</STMTTRN></OFX>",
            b"<OFX><STMTTRN><DTPOSTED>20260101<TRNAMT>1,20</STMTTRN></OFX>",
        ):
            with self.subTest(conteudo=conteudo[:10]):
                with self.assertRaises(ErroOFX) as result:
                    ler_ofx(self.escrever(conteudo))
                self.assertNotIn("CONFIDENCIAL", str(result.exception))

    def test_rejeita_link(self):
        original = self.escrever(XML)
        link = self.raiz / "atalho.ofx"
        try:
            link.symlink_to(original)
        except OSError:
            self.skipTest("sem suporte a links simbolicos")
        with self.assertRaises(ErroOFX):
            ler_ofx(link)

    def test_sem_transacao(self):
        with self.assertRaises(ErroOFX):
            ler_ofx(self.escrever(b"<OFX><BANKTRANLIST></BANKTRANLIST></OFX>"))


if __name__ == "__main__":
    unittest.main()
