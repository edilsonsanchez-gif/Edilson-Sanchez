import json
import os
import socket
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from etiquetas_imei import config, impressora, imei, zpl

CFG = dict(config.PADRAO)
I1, I2 = "490154203237518", "356938035643809"


class TestImei(unittest.TestCase):
    def test_luhn(self):
        self.assertTrue(imei.valido(I1))
        self.assertTrue(imei.valido(I2))
        self.assertFalse(imei.valido("490154203237519"))
        self.assertFalse(imei.valido("49015420323751"))

    def test_encontrar_em_texto(self):
        self.assertEqual(imei.encontrar(f"IMEI1: {I1}\nIMEI2:{I2} S/N 123"), [I1, I2])
        self.assertEqual(imei.encontrar("49 015420 323751 8"), [I1])
        self.assertEqual(imei.encontrar("123456789012345"), [])


class TestZpl(unittest.TestCase):
    def test_separado_duas_colunas(self):
        texto, qtd = zpl.gerar([{"imei1": I1, "imei2": I2}], CFG)
        self.assertEqual(qtd, 2)
        self.assertEqual(texto.count("^XA"), 1)
        self.assertIn("^PW656", texto)   # 40 + 2 + 40 mm a 8 pontos/mm
        self.assertIn("^LL200", texto)   # 25 mm
        self.assertIn(">;49015420323751>68", texto)
        self.assertIn(">;35693803564380>69", texto)
        self.assertLess(texto.index("IMEI 1"), texto.index("IMEI 2"))

    def test_copias_viram_quantidade(self):
        texto, qtd = zpl.gerar([{"imei1": I1, "imei2": I2, "copias": 3}], CFG)
        self.assertEqual(qtd, 6)
        self.assertEqual(texto.count("^XA"), 1)
        self.assertIn("^PQ3,", texto)

    def test_par_preenche_as_colunas_com_celulares_diferentes(self):
        cfg = {**CFG, "layout": "par"}
        itens = [{"imei1": I1, "imei2": I2}, {"imei1": I2}, {"imei1": I1}]
        texto, qtd = zpl.gerar(itens, cfg)
        self.assertEqual(qtd, 3)
        self.assertEqual(texto.count("^XA"), 2)  # 2 fileiras: (1, 2) e (3, vazio)

    def test_codigo_cabe_na_etiqueta(self):
        for dpi, pmm in ((203, 8), (300, 12)):
            texto, _ = zpl.gerar([{"imei1": I1, "imei2": I2}], {**CFG, "dpi": dpi})
            largura = 40 * pmm
            for linha in texto.split("^BY")[1:]:
                modulo = int(linha.split(",")[0])
                x = int(linha.split("^FO")[1].split(",")[0]) % (largura + 2 * pmm)
                self.assertLessEqual(x + 134 * modulo, largura)

    def test_erros(self):
        with self.assertRaises(zpl.ErroEtiqueta):
            zpl.gerar([{"imei1": "123"}], CFG)
        with self.assertRaises(zpl.ErroEtiqueta):
            zpl.gerar([{"imei1": "", "imei2": ""}], CFG)


class TestConfig(unittest.TestCase):
    def test_normalizar(self):
        c = config.normalizar({"dpi": "300", "colunas": "9", "layout": "xyz", "espaco_colunas_mm": "2,5", "outro": 1})
        self.assertEqual(c["dpi"], 300)
        self.assertEqual(c["colunas"], 4)
        self.assertEqual(c["layout"], config.PADRAO["layout"])
        self.assertEqual(c["espaco_colunas_mm"], 2.5)
        self.assertNotIn("outro", c)


class TestImpressoraRede(unittest.TestCase):
    def test_envia_para_porta_9100(self):
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        recebido = []

        def aceitar():
            con, _ = srv.accept()
            with con:
                dados = b""
                while chunk := con.recv(4096):
                    dados += chunk
                recebido.append(dados)

        t = threading.Thread(target=aceitar)
        t.start()
        impressora.enviar("^XA^XZ", {"modo": "rede", "ip": "127.0.0.1", "porta": srv.getsockname()[1]})
        t.join(5)
        srv.close()
        self.assertEqual(recebido, [b"^XA^XZ"])

    def test_erro_sem_impressora(self):
        with self.assertRaises(impressora.ErroImpressora):
            impressora.enviar("^XA^XZ", {"modo": "rede", "ip": "127.0.0.1", "porta": 1})


class TestServidor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.saida = Path(cls.tmp.name) / "saida.zpl"
        config.ARQUIVO = Path(cls.tmp.name) / "config.json"
        config.salvar({"modo": "arquivo", "arquivo_saida": str(cls.saida)})
        from http.server import ThreadingHTTPServer
        from etiquetas_imei.servidor import Handler
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.tmp.cleanup()

    def post(self, rota, dados):
        req = urllib.request.Request(self.url + rota, json.dumps(dados).encode(), {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            return json.load(e)

    def test_pagina_e_imprimir(self):
        with urllib.request.urlopen(self.url + "/") as r:
            self.assertIn(b"Etiquetas IMEI", r.read())
        r = self.post("/api/imprimir", {"itens": [{"imei1": I1, "imei2": I2}]})
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["etiquetas"], 2)
        self.assertIn(I1, self.saida.read_text())

    def test_erro_vira_mensagem(self):
        r = self.post("/api/imprimir", {"itens": [{"imei1": "12"}]})
        self.assertFalse(r["ok"])
        self.assertIn("15 dígitos", r["erro"])

    def test_nao_sai_da_pasta_static(self):
        with self.assertRaises(urllib.error.HTTPError):
            urllib.request.urlopen(self.url + "/static/../config.py")


if __name__ == "__main__":
    unittest.main()
