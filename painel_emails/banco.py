"""Armazenamento local dos e-mails classificados (SQLite)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

ESQUEMA = """
CREATE TABLE IF NOT EXISTS emails (
    id            INTEGER PRIMARY KEY,
    pasta         TEXT NOT NULL,
    uidvalidity   INTEGER NOT NULL,
    uid           INTEGER NOT NULL,
    gm_msgid      TEXT,
    message_id    TEXT,
    remetente     TEXT,
    remetente_email TEXT,
    assunto       TEXT,
    data          TEXT,          -- ISO 8601
    trecho        TEXT,
    corpo         TEXT,
    categoria     TEXT NOT NULL,
    categoria_manual TEXT,       -- correção feita no painel; tem prioridade
    motivos       TEXT,
    UNIQUE (pasta, uidvalidity, uid)
);
CREATE INDEX IF NOT EXISTS idx_emails_data ON emails (data);
CREATE TABLE IF NOT EXISTS estado (
    chave TEXT PRIMARY KEY,
    valor TEXT
);
"""

CATEGORIA_EFETIVA = "COALESCE(categoria_manual, categoria)"


def conectar(caminho: str | Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(caminho))
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA)
    return con


def ler_estado(con: sqlite3.Connection, chave: str, padrao: str | None = None) -> str | None:
    row = con.execute("SELECT valor FROM estado WHERE chave = ?", (chave,)).fetchone()
    return row["valor"] if row else padrao


def gravar_estado(con: sqlite3.Connection, chave: str, valor: str) -> None:
    con.execute(
        "INSERT INTO estado (chave, valor) VALUES (?, ?) "
        "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
        (chave, valor),
    )


def inserir_email(con: sqlite3.Connection, e: dict) -> bool:
    cur = con.execute(
        """INSERT OR IGNORE INTO emails
           (pasta, uidvalidity, uid, gm_msgid, message_id, remetente, remetente_email,
            assunto, data, trecho, corpo, categoria, motivos)
           VALUES (:pasta, :uidvalidity, :uid, :gm_msgid, :message_id, :remetente,
                   :remetente_email, :assunto, :data, :trecho, :corpo, :categoria, :motivos)""",
        e,
    )
    return cur.rowcount > 0


def resumo(con: sqlite3.Connection, desde: str | None) -> dict[str, int]:
    sql = f"SELECT {CATEGORIA_EFETIVA} AS cat, COUNT(*) AS n FROM emails"
    params: list = []
    if desde:
        sql += " WHERE data >= ?"
        params.append(desde)
    sql += " GROUP BY cat"
    return {r["cat"]: r["n"] for r in con.execute(sql, params)}


def por_dia(con: sqlite3.Connection, desde: str | None) -> list[sqlite3.Row]:
    sql = f"SELECT substr(data, 1, 10) AS dia, {CATEGORIA_EFETIVA} AS cat, COUNT(*) AS n FROM emails"
    params: list = []
    if desde:
        sql += " WHERE data >= ?"
        params.append(desde)
    sql += " GROUP BY dia, cat ORDER BY dia"
    return list(con.execute(sql, params))


def listar(
    con: sqlite3.Connection,
    desde: str | None,
    categoria: str | None,
    busca: str | None,
    limite: int = 200,
) -> list[sqlite3.Row]:
    sql = f"SELECT *, {CATEGORIA_EFETIVA} AS cat FROM emails WHERE 1=1"
    params: list = []
    if desde:
        sql += " AND data >= ?"
        params.append(desde)
    if categoria:
        sql += f" AND {CATEGORIA_EFETIVA} = ?"
        params.append(categoria)
    if busca:
        sql += " AND (assunto LIKE ? OR remetente LIKE ? OR remetente_email LIKE ? OR trecho LIKE ?)"
        params.extend([f"%{busca}%"] * 4)
    sql += " ORDER BY data DESC LIMIT ?"
    params.append(limite)
    return list(con.execute(sql, params))


def obter(con: sqlite3.Connection, email_id: int) -> sqlite3.Row | None:
    return con.execute(
        f"SELECT *, {CATEGORIA_EFETIVA} AS cat FROM emails WHERE id = ?", (email_id,)
    ).fetchone()


def corrigir_categoria(con: sqlite3.Connection, email_id: int, categoria: str | None) -> None:
    con.execute("UPDATE emails SET categoria_manual = ? WHERE id = ?", (categoria, email_id))
    con.commit()


def reclassificar_tudo(con: sqlite3.Connection, classificador) -> int:
    """Aplica de novo as regras (após editar regras.json). Correções manuais são mantidas."""
    n = 0
    for r in con.execute("SELECT id, assunto, corpo, remetente_email FROM emails").fetchall():
        res = classificador.classificar(r["assunto"] or "", r["corpo"] or "", r["remetente_email"] or "")
        con.execute(
            "UPDATE emails SET categoria = ?, motivos = ? WHERE id = ?",
            (res.categoria, "\n".join(res.motivos), r["id"]),
        )
        n += 1
    con.commit()
    return n
