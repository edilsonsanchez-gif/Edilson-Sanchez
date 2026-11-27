import sys
import unittest
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from painel_emails import banco, coletor  # noqa: E402
from painel_emails.classificador import Classificador  # noqa: E402
from painel_emails.servidor import link_gmail  # noqa: E402


class TestClassificador(unittest.TestCase):
    def setUp(self):
        self.c = Classificador()

    def cat(self, assunto, corpo="", rem=""):
        return self.c.classificar(assunto, corpo, rem).categoria

    def test_venda(self):
        self.assertEqual(self.cat("Nova venda realizada - Pedido #123"), "venda")
        self.assertEqual(self.cat("Você recebeu um pagamento", "Pagamento aprovado via Pix"), "venda")

    def test_venda_de_noreply_continua_venda(self):
        self.assertEqual(self.cat("Pedido confirmado", "Não responda este e-mail", "noreply@loja.com"), "venda")

    def test_pergunta(self):
        self.assertEqual(self.cat("Dúvida sobre tamanho"), "pergunta")
        self.assertEqual(self.cat("Oi", "Vocês entregam em Curitiba?"), "pergunta")

    def test_mensagem(self):
        self.assertEqual(self.cat("Produto chegou", "Muito obrigada, ficou ótimo!"), "mensagem")
        self.assertEqual(self.cat("Olá", "Tudo bem com vocês"), "mensagem")  # padrão

    def test_reclamacao_sobre_pedido_e_mensagem(self):
        self.assertEqual(self.cat("Não recebi meu pedido", "Fiz a compra há 10 dias."), "mensagem")

    def test_saudacao_nao_e_pergunta(self):
        self.assertEqual(self.cat("Parceria", "Olá, tudo bem? Adoraria conversar."), "mensagem")

    def test_outros(self):
        self.assertEqual(self.cat("Ofertas", "Para descadastrar clique aqui"), "outros")

    def test_sem_acento_e_palavra_inteira(self):
        self.assertEqual(self.cat("DUVIDA"), "pergunta")
        self.assertNotEqual(self.cat("Expedido", "texto qualquer"), "venda")


class TestColetor(unittest.TestCase):
    def test_montar_registro_html(self):
        m = EmailMessage()
        m["From"] = "Ana <ana@ex.com>"
        m["Subject"] = "Dúvida"
        m["Date"] = "Fri, 27 Nov 2026 10:00:00 -0300"
        m.set_content("<p>Qual o prazo?</p><style>x{}</style>", subtype="html")
        r = coletor.montar_registro(m.as_bytes(), "INBOX", 1, 5, "1234", Classificador())
        self.assertEqual(r["remetente"], "Ana")
        self.assertEqual(r["remetente_email"], "ana@ex.com")
        self.assertEqual(r["categoria"], "pergunta")
        self.assertIn("Qual o prazo?", r["corpo"])
        self.assertNotIn("<p>", r["corpo"])


class TestBanco(unittest.TestCase):
    def test_correcao_manual_tem_prioridade(self):
        con = banco.conectar(":memory:")
        banco.inserir_email(con, dict(pasta="INBOX", uidvalidity=1, uid=1, gm_msgid="255",
                                      message_id="<a@b>", remetente="X", remetente_email="x@y",
                                      assunto="Oi", data="2026-11-27T10:00:00", trecho="",
                                      corpo="", categoria="mensagem", motivos=""))
        self.assertEqual(banco.resumo(con, None), {"mensagem": 1})
        banco.corrigir_categoria(con, 1, "venda")
        self.assertEqual(banco.resumo(con, None), {"venda": 1})
        banco.reclassificar_tudo(con, Classificador())
        self.assertEqual(banco.resumo(con, None), {"venda": 1})
        row = banco.obter(con, 1)
        self.assertTrue(link_gmail(row, "eu@gmail.com").endswith("#all/ff"))


if __name__ == "__main__":
    unittest.main()
