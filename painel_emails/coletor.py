"""Busca e-mails novos no Gmail via IMAP, classifica e grava no banco local."""

from __future__ import annotations

import email
import html
import imaplib
import re
from datetime import datetime, timedelta, timezone
from email import policy
from email.utils import parseaddr, parsedate_to_datetime

from . import banco
from .classificador import Classificador
from .config import Config

LOTE = 50
RX_UID = re.compile(rb"UID (\d+)")
RX_GMID = re.compile(rb"X-GM-MSGID (\d+)")


def _texto_de_html(conteudo: str) -> str:
    conteudo = re.sub(r"(?is)<(script|style).*?</\1>", " ", conteudo)
    conteudo = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", conteudo)
    conteudo = re.sub(r"<[^>]+>", " ", conteudo)
    return html.unescape(conteudo)


def extrair_corpo(msg: email.message.EmailMessage) -> str:
    try:
        parte = msg.get_body(preferencelist=("plain", "html"))
    except Exception:
        parte = None
    if parte is None:
        return ""
    try:
        conteudo = parte.get_content()
    except Exception:
        payload = parte.get_payload(decode=True) or b""
        conteudo = payload.decode(parte.get_content_charset() or "utf-8", errors="replace")
    if parte.get_content_type() == "text/html":
        conteudo = _texto_de_html(conteudo)
    # Remove o histórico citado ("> ...") para não confundir a classificação.
    linhas = [l for l in conteudo.splitlines() if not l.lstrip().startswith(">")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(linhas)).strip()


def data_iso(cabecalho: str | None) -> str:
    try:
        dt = parsedate_to_datetime(cabecalho) if cabecalho else None
    except (TypeError, ValueError):
        dt = None
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().isoformat(timespec="seconds")


def montar_registro(bruto: bytes, pasta: str, uidvalidity: int, uid: int,
                    gm_msgid: str | None, classificador: Classificador) -> dict:
    msg = email.message_from_bytes(bruto, policy=policy.default)
    nome, endereco = parseaddr(str(msg.get("From", "")))
    assunto = str(msg.get("Subject", "") or "(sem assunto)")
    corpo = extrair_corpo(msg)
    res = classificador.classificar(assunto, corpo, endereco)
    return {
        "pasta": pasta,
        "uidvalidity": uidvalidity,
        "uid": uid,
        "gm_msgid": gm_msgid,
        "message_id": str(msg.get("Message-ID", "") or ""),
        "remetente": nome or endereco,
        "remetente_email": endereco,
        "assunto": assunto,
        "data": data_iso(msg.get("Date")),
        "trecho": re.sub(r"\s+", " ", corpo)[:240],
        "corpo": corpo[:20000],
        "categoria": res.categoria,
        "motivos": "\n".join(res.motivos),
    }


def _sincronizar_pasta(imap: imaplib.IMAP4, con, pasta: str, cfg: Config,
                       classificador: Classificador, log) -> int:
    tipo, _ = imap.select(f'"{pasta}"', readonly=True)
    if tipo != "OK":
        log(f"Pasta '{pasta}' não encontrada; pulando.")
        return 0
    uidvalidity = int(imap.response("UIDVALIDITY")[1][0])
    chave = f"ultimo_uid:{pasta}:{uidvalidity}"
    ultimo = int(banco.ler_estado(con, chave, "0"))

    if ultimo:
        _, dados = imap.uid("SEARCH", None, f"UID {ultimo + 1}:*")
    else:
        desde = (datetime.now() - timedelta(days=cfg.dias_iniciais)).strftime("%d-%b-%Y")
        _, dados = imap.uid("SEARCH", None, f"SINCE {desde}")
    uids = sorted(int(u) for u in (dados[0] or b"").split() if int(u) > ultimo)
    log(f"{pasta}: {len(uids)} e-mail(s) novo(s).")

    novos = 0
    for i in range(0, len(uids), LOTE):
        lote = uids[i:i + LOTE]
        _, resposta = imap.uid("FETCH", ",".join(map(str, lote)), "(X-GM-MSGID BODY.PEEK[])")
        for item in resposta:
            if not isinstance(item, tuple):
                continue
            cabecalho, bruto = item
            m_uid = RX_UID.search(cabecalho)
            if not m_uid:
                continue
            m_gm = RX_GMID.search(cabecalho)
            registro = montar_registro(
                bruto, pasta, uidvalidity, int(m_uid.group(1)),
                m_gm.group(1).decode() if m_gm else None, classificador,
            )
            novos += banco.inserir_email(con, registro)
        banco.gravar_estado(con, chave, str(lote[-1]))
        con.commit()
        log(f"  {min(i + LOTE, len(uids))}/{len(uids)} processados")
    return novos


def sincronizar(cfg: Config, con, classificador: Classificador | None = None, log=print) -> int:
    if not cfg.tem_credenciais:
        raise RuntimeError(
            "Configure EMAIL_USUARIO e EMAIL_SENHA_APP no arquivo .env (veja o README)."
        )
    classificador = classificador or Classificador()
    with imaplib.IMAP4_SSL(cfg.servidor) as imap:
        imap.login(cfg.usuario, cfg.senha)
        total = sum(_sincronizar_pasta(imap, con, p, cfg, classificador, log) for p in cfg.pastas)
    banco.gravar_estado(con, "ultima_sincronizacao", datetime.now().isoformat(timespec="seconds"))
    con.commit()
    log(f"Concluído: {total} e-mail(s) adicionados.")
    return total
