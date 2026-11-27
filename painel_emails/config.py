"""Configuração lida de variáveis de ambiente ou do arquivo .env na raiz do projeto."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _carregar_dotenv(caminho: Path) -> None:
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


@dataclass
class Config:
    usuario: str
    senha: str
    servidor: str
    pastas: list[str]
    dias_iniciais: int
    banco: Path
    porta: int
    conta_gmail: str  # usado para montar o link "abrir no Gmail"

    @property
    def tem_credenciais(self) -> bool:
        return bool(self.usuario and self.senha)


def carregar() -> Config:
    _carregar_dotenv(RAIZ / ".env")
    usuario = os.environ.get("EMAIL_USUARIO", "")
    return Config(
        usuario=usuario,
        senha=os.environ.get("EMAIL_SENHA_APP", "").replace(" ", ""),
        servidor=os.environ.get("EMAIL_SERVIDOR_IMAP", "imap.gmail.com"),
        pastas=[p.strip() for p in os.environ.get("EMAIL_PASTAS", "INBOX").split(",") if p.strip()],
        dias_iniciais=int(os.environ.get("EMAIL_DIAS_INICIAIS", "30")),
        banco=Path(os.environ.get("PAINEL_BANCO", RAIZ / "emails.db")),
        porta=int(os.environ.get("PAINEL_PORTA", "8000")),
        conta_gmail=os.environ.get("GMAIL_CONTA_LINK", usuario),
    )
