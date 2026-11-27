"""Painel web (somente biblioteca padrão) para ver os e-mails classificados."""

from __future__ import annotations

import json
import threading
from datetime import date, datetime, timedelta
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlencode, urlparse

from . import banco, coletor
from .classificador import Classificador
from .config import Config

ORDEM = ["venda", "pergunta", "mensagem", "outros"]
PERIODOS = {"7": "7 dias", "30": "30 dias", "90": "90 dias", "tudo": "Tudo"}

CSS = """
:root{color-scheme:light;--bg:#f6f6f4;--surface:#fff;--border:#e4e4e0;--text:#191919;
--text2:#666;--grid:#ececea;--accent:#257de0;
--c-venda:#257de0;--c-pergunta:#f47230;--c-mensagem:#00b894;--c-outros:#a3a3a3}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--bg:#111;
--surface:#191919;--border:#2e2e2e;--text:#efefef;--text2:#9c9c9c;--grid:#2a2a2a;--accent:#338ced;
--c-venda:#338ced;--c-pergunta:#e76624;--c-mensagem:#00a888;--c-outros:#6b6b6b}}
:root[data-theme="dark"]{color-scheme:dark;--bg:#111;--surface:#191919;--border:#2e2e2e;
--text:#efefef;--text2:#9c9c9c;--grid:#2a2a2a;--accent:#338ced;--c-venda:#338ced;
--c-pergunta:#e76624;--c-mensagem:#00a888;--c-outros:#6b6b6b}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
font:15px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--accent)}
.wrap{max-width:1100px;margin:0 auto;padding:20px 16px 48px}
header{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between}
h1{font-size:22px;margin:0}
.sub{color:var(--text2);font-size:13px}
.filtros{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:18px 0}
.seg{display:inline-flex;border:1px solid var(--border);border-radius:8px;overflow:hidden}
.seg a{padding:6px 12px;text-decoration:none;color:var(--text2);font-size:13px}
.seg a.on{background:var(--surface);color:var(--text);font-weight:600}
input[type=search]{flex:1;min-width:180px;padding:7px 10px;border:1px solid var(--border);
border-radius:8px;background:var(--surface);color:var(--text);font:inherit}
button,.btn{padding:7px 14px;border:1px solid var(--border);border-radius:8px;
background:var(--surface);color:var(--text);font:inherit;cursor:pointer;text-decoration:none}
button.prim{background:var(--accent);border-color:var(--accent);color:#fff}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px}
.gm{white-space:nowrap}
.card{display:block;background:var(--surface);border:1px solid var(--border);border-radius:12px;
padding:14px 16px;text-decoration:none;color:var(--text)}
.card.on{outline:2px solid var(--accent);outline-offset:-1px}
.card .rot{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--text2)}
.card .num{font-size:30px;font-weight:650;margin-top:4px;font-variant-numeric:tabular-nums}
.card .pct{font-size:12px;color:var(--text2)}
.dot{width:10px;height:10px;border-radius:3px;display:inline-block;flex:none}
.painel{background:var(--surface);border:1px solid var(--border);border-radius:12px;
padding:16px;margin-top:16px}
.painel h2{font-size:15px;margin:0 0 10px}
.legenda{display:flex;flex-wrap:wrap;gap:14px;font-size:12px;color:var(--text2);margin-bottom:6px}
.legenda span{display:inline-flex;align-items:center;gap:6px}
.grafico{position:relative}
.grafico svg{width:100%;height:auto;display:block}
.grafico text{fill:var(--text2);font-size:11px}
.tip{position:absolute;pointer-events:none;background:var(--surface);border:1px solid var(--border);
border-radius:8px;padding:8px 10px;font-size:12px;box-shadow:0 4px 14px rgba(0,0,0,.12);
display:none;white-space:nowrap;z-index:2}
.tip div{display:flex;align-items:center;gap:6px}
.tabela{width:100%;border-collapse:collapse;font-size:14px}
.tabela th{text-align:left;font-size:12px;color:var(--text2);font-weight:500;
border-bottom:1px solid var(--border);padding:6px 8px}
.tabela td{border-bottom:1px solid var(--grid);padding:9px 8px;vertical-align:top}
.tabela tr:hover td{background:var(--bg)}
.tag{display:inline-flex;align-items:center;gap:6px;font-size:12px;white-space:nowrap}
.assunto{font-weight:600;color:var(--text);text-decoration:none}
.trecho{color:var(--text2);font-size:13px;overflow:hidden;text-overflow:ellipsis;
display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.quando{white-space:nowrap;color:var(--text2);font-size:13px}
.aviso{background:var(--surface);border:1px solid var(--border);border-left:4px solid var(--accent);
padding:10px 14px;border-radius:8px;margin-top:14px;font-size:14px}
.vazio{color:var(--text2);text-align:center;padding:30px}
pre.corpo{white-space:pre-wrap;word-wrap:break-word;font:inherit;margin:0}
@media (max-width:640px){.col-quando,.col-rem{display:none}}
"""

JS = """
(function(){
  var g=document.querySelector('.grafico'); if(!g) return;
  var tip=g.querySelector('.tip');
  g.querySelectorAll('[data-tip]').forEach(function(el){
    el.addEventListener('mousemove',function(ev){
      tip.innerHTML=el.getAttribute('data-tip'); tip.style.display='block';
      var r=g.getBoundingClientRect(), x=ev.clientX-r.left+12, y=ev.clientY-r.top+12;
      if(x+tip.offsetWidth>r.width) x=ev.clientX-r.left-tip.offsetWidth-12;
      tip.style.left=x+'px'; tip.style.top=y+'px';
    });
    el.addEventListener('mouseleave',function(){tip.style.display='none'});
  });
})();
"""


def link_gmail(row, conta: str) -> str:
    base = "https://mail.google.com/mail/"
    if conta:
        base += "?authuser=" + quote(conta)
    if row["gm_msgid"]:
        return f"{base}#all/{int(row['gm_msgid']):x}"
    if row["message_id"]:
        return f"{base}#search/" + quote("rfc822msgid:" + row["message_id"].strip("<>"))
    return base


def _formatar_data(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return iso or ""
    if dt.date() == date.today():
        return "hoje " + dt.strftime("%H:%M")
    return dt.strftime("%d/%m/%Y %H:%M")


def _desde(periodo: str) -> str | None:
    if periodo == "tudo":
        return None
    return (date.today() - timedelta(days=int(periodo) - 1)).isoformat()


def _pagina(titulo: str, corpo: str) -> bytes:
    return (
        "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{escape(titulo)}</title><style>{CSS}</style></head>"
        f"<body><div class='wrap'>{corpo}</div><script>{JS}</script></body></html>"
    ).encode("utf-8")


def _grafico(linhas, periodo: str, cls: Classificador) -> str:
    dados: dict[str, dict[str, int]] = {}
    for r in linhas:
        dados.setdefault(r["dia"], {})[r["cat"]] = r["n"]
    if not dados:
        return "<p class='vazio'>Sem e-mails no período.</p>"
    if periodo == "tudo":
        inicio = date.fromisoformat(min(dados))
    else:
        inicio = date.today() - timedelta(days=int(periodo) - 1)
    fim = max(date.today(), date.fromisoformat(max(dados)))
    dias = [(inicio + timedelta(d)).isoformat() for d in range((fim - inicio).days + 1)]

    larg, alt, esq, base_y, topo = 900, 220, 34, 196, 10
    maximo = max(sum(v.values()) for v in dados.values()) or 1
    passo = max(1, -(-maximo // 4))
    eixo_max = passo * 4
    h_util = base_y - topo
    col = (larg - esq) / len(dias)
    barra = max(2.0, min(28.0, col * 0.7))
    partes = []
    for i in range(5):
        y = base_y - h_util * i / 4
        partes.append(
            f"<line x1='{esq}' x2='{larg}' y1='{y:.1f}' y2='{y:.1f}' stroke='var(--grid)'/>"
            f"<text x='{esq - 6}' y='{y + 4:.1f}' text-anchor='end'>{passo * i}</text>"
        )
    a_cada = max(1, len(dias) // 10)
    for idx, dia in enumerate(dias):
        cx = esq + col * idx + col / 2
        valores = dados.get(dia, {})
        y = base_y
        segs = [c for c in ORDEM if valores.get(c)]
        for j, cat in enumerate(segs):
            h = h_util * valores[cat] / eixo_max
            gap = 2 if j > 0 else 0
            topo_seg = y - h
            raio = min(4, barra / 2) if j == len(segs) - 1 else 0
            altura = max(h - gap, 1)
            if raio:
                partes.append(
                    f"<path d='M{cx - barra / 2:.1f},{y - gap:.1f} V{topo_seg + raio:.1f} "
                    f"Q{cx - barra / 2:.1f},{topo_seg:.1f} {cx - barra / 2 + raio:.1f},{topo_seg:.1f} "
                    f"H{cx + barra / 2 - raio:.1f} Q{cx + barra / 2:.1f},{topo_seg:.1f} "
                    f"{cx + barra / 2:.1f},{topo_seg + raio:.1f} V{y - gap:.1f} Z' "
                    f"fill='var(--c-{cat})'/>"
                )
            else:
                partes.append(
                    f"<rect x='{cx - barra / 2:.1f}' y='{topo_seg:.1f}' width='{barra:.1f}' "
                    f"height='{altura:.1f}' fill='var(--c-{cat})'/>"
                )
            y = topo_seg
        d = date.fromisoformat(dia)
        linhas_tip = "".join(
            f"<div><span class='dot' style='background:var(--c-{c})'></span>"
            f"{escape(cls.rotulo(c))}: <b>{valores.get(c, 0)}</b></div>"
            for c in ORDEM if c in cls.categorias
        )
        tip = escape(f"<b>{d.strftime('%d/%m/%Y')}</b>{linhas_tip}", quote=True)
        partes.append(
            f"<rect x='{esq + col * idx:.1f}' y='{topo}' width='{col:.1f}' height='{h_util}' "
            f"fill='transparent' data-tip=\"{tip}\"/>"
        )
        if idx % a_cada == 0:
            partes.append(f"<text x='{cx:.1f}' y='{base_y + 16}' text-anchor='middle'>{d.strftime('%d/%m')}</text>")
    partes.append(f"<line x1='{esq}' x2='{larg}' y1='{base_y}' y2='{base_y}' stroke='var(--text2)' stroke-opacity='.4'/>")
    legenda = "".join(
        f"<span><span class='dot' style='background:var(--c-{c})'></span>{escape(cls.rotulo(c))}</span>"
        for c in ORDEM if c in cls.categorias
    )
    return (
        f"<div class='legenda'>{legenda}</div><div class='grafico'>"
        f"<svg viewBox='0 0 {larg} {alt}' role='img' aria-label='E-mails por dia e tipo'>{''.join(partes)}</svg>"
        "<div class='tip'></div></div>"
    )


class Painel:
    def __init__(self, cfg: Config, demo: bool = False):
        self.cfg = cfg
        self.demo = demo
        self.cls = Classificador()
        self.trava = threading.Lock()

    def conexao(self):
        return banco.conectar(self.cfg.banco)

    def inicio(self, params: dict[str, str]) -> bytes:
        periodo = params.get("periodo", "30")
        periodo = periodo if periodo in PERIODOS else "30"
        categoria = params.get("categoria") or None
        busca = params.get("q", "").strip()
        desde = _desde(periodo)
        con = self.conexao()
        try:
            resumo = banco.resumo(con, desde)
            dias = banco.por_dia(con, desde)
            emails = banco.listar(con, desde, categoria, busca)
            ultima = banco.ler_estado(con, "ultima_sincronizacao")
        finally:
            con.close()

        def url(**mudar):
            atual = {"periodo": periodo, "categoria": categoria or "", "q": busca}
            atual.update(mudar)
            return "/?" + urlencode({k: v for k, v in atual.items() if v})

        total = sum(resumo.values())
        cards = []
        for c in ORDEM:
            if c not in self.cls.categorias:
                continue
            n = resumo.get(c, 0)
            pct = f"{100 * n / total:.0f}% do total" if total else "—"
            ativo = categoria == c
            cards.append(
                f"<a class='card{' on' if ativo else ''}' href='{escape(url(categoria='' if ativo else c))}'>"
                f"<div class='rot'><span class='dot' style='background:var(--c-{c})'></span>"
                f"{escape(self.cls.rotulo(c))}</div><div class='num'>{n}</div>"
                f"<div class='pct'>{pct}</div></a>"
            )

        seg = "".join(
            f"<a class='{'on' if p == periodo else ''}' href='{escape(url(periodo=p))}'>{r}</a>"
            for p, r in PERIODOS.items()
        )
        linhas = []
        for e in emails:
            linhas.append(
                "<tr>"
                f"<td><span class='tag'><span class='dot' style='background:var(--c-{e['cat']})'></span>"
                f"{escape(self.cls.rotulo(e['cat']))}{' ✎' if e['categoria_manual'] else ''}</span></td>"
                f"<td><a class='assunto' href='/email/{e['id']}'>{escape(e['assunto'] or '')}</a>"
                f"<div class='trecho'>{escape(e['trecho'] or '')}</div></td>"
                f"<td class='col-rem'>{escape(e['remetente'] or '')}<div class='sub'>{escape(e['remetente_email'] or '')}</div></td>"
                f"<td class='quando col-quando'>{_formatar_data(e['data'])}</td>"
                f"<td><a class='gm' href='{escape(link_gmail(e, self.cfg.conta_gmail))}' target='_blank' rel='noopener'>Gmail ↗</a></td>"
                "</tr>"
            )
        tabela = (
            "<table class='tabela'><thead><tr><th>Tipo</th><th>Assunto</th>"
            "<th class='col-rem'>Remetente</th><th class='col-quando'>Recebido</th><th></th></tr></thead>"
            f"<tbody>{''.join(linhas)}</tbody></table>"
            if linhas else "<p class='vazio'>Nenhum e-mail encontrado com esses filtros.</p>"
        )
        titulo_lista = escape(self.cls.rotulo(categoria)) if categoria else "Todos os e-mails"
        aviso = ""
        if self.demo:
            aviso = "<div class='aviso'>Modo demonstração: dados de exemplo. Configure o .env e rode <code>python -m painel_emails sincronizar</code> para usar seus e-mails.</div>"
        elif not self.cfg.tem_credenciais:
            aviso = "<div class='aviso'>Configure <code>EMAIL_USUARIO</code> e <code>EMAIL_SENHA_APP</code> no arquivo <code>.env</code> para buscar seus e-mails (veja o README).</div>"
        botao = "" if self.demo else (
            "<form method='post' action='/sincronizar'><button class='prim'>Buscar novos e-mails</button></form>"
        )
        corpo = (
            "<header><div><h1>Painel de e-mails</h1>"
            f"<div class='sub'>{escape(self.cfg.usuario or 'Gmail')} · última busca: "
            f"{_formatar_data(ultima) if ultima else 'nunca'}</div></div>{botao}</header>"
            f"{aviso}"
            "<form class='filtros' method='get' action='/'>"
            f"<div class='seg'>{seg}</div>"
            f"<input type='hidden' name='periodo' value='{escape(periodo)}'>"
            f"<input type='hidden' name='categoria' value='{escape(categoria or '')}'>"
            f"<input type='search' name='q' value='{escape(busca)}' placeholder='Buscar por assunto, remetente ou texto'>"
            "<button>Buscar</button></form>"
            f"<div class='cards'>{''.join(cards)}</div>"
            f"<section class='painel'><h2>E-mails por dia</h2>{_grafico(dias, periodo, self.cls)}</section>"
            f"<section class='painel'><h2>{titulo_lista} <span class='sub'>({len(emails)})</span></h2>{tabela}</section>"
        )
        return _pagina("Painel de e-mails", corpo)

    def detalhe(self, email_id: int) -> bytes | None:
        con = self.conexao()
        try:
            e = banco.obter(con, email_id)
        finally:
            con.close()
        if e is None:
            return None
        opcoes = "".join(
            f"<option value='{c}'{' selected' if c == e['cat'] else ''}>{escape(self.cls.rotulo(c))}</option>"
            for c in ORDEM if c in self.cls.categorias
        )
        motivos = escape(e["motivos"] or "").replace("\n", "<br>")
        responder = ""
        if e["remetente_email"]:
            mailto = "mailto:" + e["remetente_email"] + "?subject=" + quote("Re: " + (e["assunto"] or ""))
            responder = f" <a class='btn' href='{escape(mailto)}'>Responder</a>"
        corpo = (
            "<p><a href='/'>← Voltar ao painel</a></p>"
            f"<h1>{escape(e['assunto'] or '')}</h1>"
            f"<p class='sub'>De {escape(e['remetente'] or '')} &lt;{escape(e['remetente_email'] or '')}&gt; · "
            f"{_formatar_data(e['data'])}</p>"
            f"<p><a class='btn' href='{escape(link_gmail(e, self.cfg.conta_gmail))}' target='_blank' rel='noopener'>Abrir no Gmail ↗</a>{responder}</p>"
            "<section class='painel'><h2>Tipo</h2>"
            f"<form method='post' action='/email/{e['id']}/categoria' style='display:flex;gap:8px;flex-wrap:wrap'>"
            f"<select name='categoria' style='padding:7px;border-radius:8px;font:inherit'>{opcoes}</select>"
            "<button class='prim'>Salvar tipo</button>"
            + ("<button name='categoria' value=''>Voltar à classificação automática</button>" if e["categoria_manual"] else "")
            + "</form>"
            f"<p class='sub' style='margin-top:10px'>Classificação automática: {escape(self.cls.rotulo(e['categoria']))}<br>{motivos}</p>"
            "</section>"
            f"<section class='painel'><h2>Mensagem</h2><pre class='corpo'>{escape(e['corpo'] or '')}</pre></section>"
        )
        return _pagina(e["assunto"] or "E-mail", corpo)

    def sincronizar(self) -> str:
        if self.demo:
            return "Modo demonstração: nada a buscar."
        if not self.trava.acquire(blocking=False):
            return "Já existe uma busca em andamento."
        try:
            con = self.conexao()
            try:
                n = coletor.sincronizar(self.cfg, con, self.cls, log=lambda *_: None)
            finally:
                con.close()
            return f"{n} e-mail(s) novo(s)."
        except Exception as erro:  # mostra o erro no painel em vez de derrubar o servidor
            return f"Erro ao buscar e-mails: {erro}"
        finally:
            self.trava.release()


def criar_handler(painel: Painel):
    class Handler(BaseHTTPRequestHandler):
        def _enviar(self, status: int, corpo: bytes, tipo="text/html; charset=utf-8"):
            self.send_response(status)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def _redirecionar(self, destino: str):
            self.send_response(303)
            self.send_header("Location", destino)
            self.end_headers()

        def _form(self) -> dict[str, str]:
            tamanho = int(self.headers.get("Content-Length", 0) or 0)
            dados = self.rfile.read(tamanho).decode("utf-8") if tamanho else ""
            return {k: v[-1] for k, v in parse_qs(dados, keep_blank_values=True).items()}

        def do_GET(self):
            u = urlparse(self.path)
            params = {k: v[-1] for k, v in parse_qs(u.query).items()}
            if u.path == "/":
                corpo = painel.inicio(params)
                if "msg" in params:
                    corpo = corpo.replace(
                        b"</header>",
                        f"</header><div class='aviso'>{escape(params['msg'])}</div>".encode(), 1,
                    )
                return self._enviar(200, corpo)
            if u.path.startswith("/email/") and u.path[7:].isdigit():
                corpo = painel.detalhe(int(u.path[7:]))
                if corpo:
                    return self._enviar(200, corpo)
            if u.path == "/api/resumo":
                periodo = params.get("periodo", "30")
                con = painel.conexao()
                try:
                    dados = banco.resumo(con, _desde(periodo if periodo in PERIODOS else "30"))
                finally:
                    con.close()
                return self._enviar(200, json.dumps(dados).encode(), "application/json")
            self._enviar(404, _pagina("Não encontrado", "<p>Página não encontrada. <a href='/'>Voltar</a></p>"))

        def do_POST(self):
            u = urlparse(self.path)
            if u.path == "/sincronizar":
                msg = painel.sincronizar()
                return self._redirecionar("/?" + urlencode({"msg": msg}))
            partes = u.path.strip("/").split("/")
            if len(partes) == 3 and partes[0] == "email" and partes[1].isdigit() and partes[2] == "categoria":
                cat = self._form().get("categoria") or None
                if cat is not None and cat not in painel.cls.categorias:
                    return self._enviar(400, b"Categoria invalida", "text/plain")
                con = painel.conexao()
                try:
                    banco.corrigir_categoria(con, int(partes[1]), cat)
                finally:
                    con.close()
                return self._redirecionar(f"/email/{partes[1]}")
            self._enviar(404, b"", "text/plain")

        def log_message(self, *args):
            pass

    return Handler


def servir(cfg: Config, demo: bool = False, host: str = "127.0.0.1") -> None:
    painel = Painel(cfg, demo)
    servidor = ThreadingHTTPServer((host, cfg.porta), criar_handler(painel))
    print(f"Painel em http://{host if host != '0.0.0.0' else 'localhost'}:{cfg.porta}  (Ctrl+C para sair)")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
