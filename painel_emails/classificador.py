"""Classifica e-mails em venda, pergunta, mensagem ou outros por palavras-chave."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

ARQUIVO_REGRAS = Path(__file__).with_name("regras.json")

# Palavras que indicam envio automático: só contam para "outros" se não
# houver sinal de venda (lojas mandam vendas de endereços no-reply).
PESO_ASSUNTO = 2
PESO_CORPO = 1


def normalizar(texto: str) -> str:
    """Minúsculas, sem acentos e com espaços simples."""
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto.lower()).strip()


@dataclass
class Resultado:
    categoria: str
    pontos: dict[str, int]
    motivos: list[str]


class Classificador:
    def __init__(self, regras: dict | None = None):
        if regras is None:
            regras = json.loads(ARQUIVO_REGRAS.read_text(encoding="utf-8"))
        self.padrao = regras.get("padrao", "mensagem")
        self.categorias = regras["categorias"]
        self.desempate = regras.get("desempate", list(self.categorias))
        self.saudacoes = [normalizar(x) for x in regras.get("saudacoes", [])]
        self._padroes = {
            nome: [
                (p, re.compile(r"(?<![a-z0-9])" + re.escape(normalizar(p)) + r"(?![a-z0-9])"))
                for p in cfg.get("palavras", [])
            ]
            for nome, cfg in self.categorias.items()
        }

    def rotulo(self, categoria: str) -> str:
        return self.categorias.get(categoria, {}).get("rotulo", categoria.capitalize())

    def classificar(self, assunto: str, corpo: str, remetente: str = "") -> Resultado:
        assunto_n = normalizar(assunto)
        corpo_n = normalizar(corpo)[:5000]
        remetente_n = normalizar(remetente)
        pontos = {nome: 0 for nome in self.categorias}
        motivos: list[str] = []

        for nome, padroes in self._padroes.items():
            for palavra, rx in padroes:
                if rx.search(assunto_n):
                    pontos[nome] += PESO_ASSUNTO
                    motivos.append(f"{nome}: '{palavra}' no assunto")
                elif rx.search(corpo_n):
                    pontos[nome] += PESO_CORPO
                    motivos.append(f"{nome}: '{palavra}' no texto")
                elif nome == "outros" and rx.search(remetente_n):
                    pontos[nome] += PESO_CORPO
                    motivos.append(f"{nome}: '{palavra}' no remetente")

        cfg_pergunta = self.categorias.get("pergunta", {})
        if cfg_pergunta.get("ponto_interrogacao") and "pergunta" in pontos:
            trecho = assunto_n + " " + corpo_n[:1500]
            for saudacao in self.saudacoes:
                trecho = trecho.replace(saudacao, " ")
            if "?" in trecho:
                pontos["pergunta"] += PESO_ASSUNTO
                motivos.append("pergunta: contém '?'")

        # Uma venda vinda de no-reply continua sendo venda.
        if pontos.get("venda", 0) > 0 and "outros" in pontos:
            pontos["outros"] = 0

        ordem = {n: i for i, n in enumerate(self.desempate)}
        melhor = min(pontos, key=lambda n: (-pontos[n], ordem.get(n, len(ordem))))
        if pontos[melhor] == 0:
            melhor = self.padrao
            motivos.append(f"nenhuma palavra-chave: categoria padrão ({self.padrao})")
        return Resultado(melhor, pontos, motivos)
