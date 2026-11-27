"""Servidor web local: entrega a página (celular ou computador) e manda o ZPL para a Zebra."""

from __future__ import annotations

import json
import mimetypes
import socket
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import config, impressora, zpl

PASTA_STATIC = Path(__file__).with_name("static")
mimetypes.add_type("application/wasm", ".wasm")
mimetypes.add_type("text/javascript", ".js")


class Handler(BaseHTTPRequestHandler):
    server_version = "EtiquetasIMEI/1.0"

    def log_request(self, code="-", size="-"):  # não registra cada pedido, só erros e impressões
        if str(getattr(code, "value", code)).startswith(("4", "5")):
            super().log_request(code, size)

    # --- respostas ---
    def _json(self, dados, status=HTTPStatus.OK):
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def _erro(self, msg, status=HTTPStatus.BAD_REQUEST):
        self._json({"ok": False, "erro": msg}, status)

    def _ler_json(self) -> dict:
        tam = int(self.headers.get("Content-Length") or 0)
        if tam > 2_000_000:
            raise ValueError("Pedido grande demais.")
        dados = json.loads(self.rfile.read(tam) or b"{}")
        if not isinstance(dados, dict):
            raise ValueError("Formato inválido.")
        return dados

    def _arquivo(self, caminho: Path):
        try:
            caminho = caminho.resolve()
            caminho.relative_to(PASTA_STATIC.resolve())
        except ValueError:
            return self._erro("Não encontrado", HTTPStatus.NOT_FOUND)
        if not caminho.is_file():
            return self._erro("Não encontrado", HTTPStatus.NOT_FOUND)
        corpo = caminho.read_bytes()
        tipo = mimetypes.guess_type(caminho.name)[0] or "application/octet-stream"
        if caminho.name.endswith(".gz"):
            tipo = "application/octet-stream"   # o tesseract descompacta sozinho
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", tipo + ("; charset=utf-8" if tipo.startswith("text/") else ""))
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "max-age=86400" if "vendor" in caminho.parts else "no-cache")
        self.end_headers()
        self.wfile.write(corpo)

    # --- rotas ---
    def do_GET(self):
        rota = self.path.split("?", 1)[0]
        if rota in ("/", "/index.html"):
            return self._arquivo(PASTA_STATIC / "index.html")
        if rota.startswith("/static/"):
            return self._arquivo(PASTA_STATIC / rota[len("/static/"):])
        if rota == "/api/config":
            return self._json({"ok": True, "config": config.carregar()})
        if rota == "/api/impressoras":
            return self._json({"ok": True, "impressoras": impressora.listar()})
        return self._erro("Não encontrado", HTTPStatus.NOT_FOUND)

    def do_POST(self):
        rota = self.path.split("?", 1)[0]
        try:
            dados = self._ler_json()
        except ValueError as e:
            return self._erro(str(e) or "JSON inválido.")
        try:
            if rota == "/api/config":
                return self._json({"ok": True, "config": config.salvar(dados.get("config") or {})})
            cfg = config.carregar()
            if rota == "/api/zpl":
                texto, qtd = zpl.gerar(dados.get("itens") or [], cfg)
                return self._json({"ok": True, "zpl": texto, "etiquetas": qtd})
            if rota == "/api/imprimir":
                itens = dados.get("itens") or []
                if not itens:
                    return self._erro("Nenhum celular para imprimir.")
                texto, qtd = zpl.gerar(itens, cfg)
                destino = impressora.enviar(texto, cfg)
                self.log_message("imprimiu %s etiqueta(s): %s", qtd, destino)
                return self._json({"ok": True, "etiquetas": qtd, "destino": destino})
            if rota == "/api/teste":
                destino = impressora.enviar(zpl.etiqueta_teste(cfg), cfg)
                return self._json({"ok": True, "destino": destino})
        except (zpl.ErroEtiqueta, impressora.ErroImpressora) as e:
            return self._erro(str(e))
        except Exception as e:  # noqa: BLE001
            return self._erro(f"Erro inesperado: {e}", HTTPStatus.INTERNAL_SERVER_ERROR)
        return self._erro("Não encontrado", HTTPStatus.NOT_FOUND)


def ip_local() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return None


def rodar(host: str = "0.0.0.0", porta: int = 8100) -> None:
    srv = ThreadingHTTPServer((host, porta), Handler)
    print("Etiquetas IMEI rodando.")
    print(f"  Neste computador:  http://localhost:{porta}")
    ip = ip_local()
    if host in ("0.0.0.0", "") and ip:
        print(f"  No celular (mesmo Wi-Fi):  http://{ip}:{porta}")
    print("Para parar, feche esta janela ou aperte Ctrl+C.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
