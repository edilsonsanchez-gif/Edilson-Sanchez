"""Configurações da etiqueta e da impressora, salvas em config.json ao lado do programa."""

from __future__ import annotations

import json
import os
from pathlib import Path

ARQUIVO = Path(os.environ.get("ETIQUETAS_CONFIG", Path(__file__).with_name("config.json")))

PADRAO: dict = {
    # Impressora
    "modo": "computador",        # computador (janela de impressão do navegador) | rede | windows | cups | arquivo
    "ip": "192.168.0.100",
    "porta": 9100,
    "nome_impressora": "",       # nome no Windows ou no CUPS (Linux/macOS)
    "arquivo_saida": "etiquetas.zpl",
    # Etiqueta
    "dpi": 203,                  # 203 (8 pontos/mm) ou 300 (12 pontos/mm)
    "largura_mm": 50.0,
    "altura_mm": 25.0,
    "colunas": 2,
    "espaco_colunas_mm": 1.0,    # espaço entre as duas etiquetas da mesma fileira
    "margem_esquerda_mm": 0.0,
    "ajuste_vertical_mm": 0.0,   # move tudo para baixo (+) ou para cima (-)
    "layout": "separado",        # separado: IMEI 1 na etiqueta da esquerda e IMEI 2 na da direita | par: os dois IMEIs na mesma etiqueta
    "escurecimento": 0,          # -30 a 30 (ajuste relativo ^MD)
    "velocidade": 3,             # polegadas por segundo (^PR)
}

INTEIROS = {"porta", "dpi", "colunas", "escurecimento", "velocidade"}
DECIMAIS = {"largura_mm", "altura_mm", "espaco_colunas_mm", "margem_esquerda_mm", "ajuste_vertical_mm"}
OPCOES = {"modo": {"computador", "rede", "windows", "cups", "arquivo"}, "layout": {"par", "separado"}, "dpi": {203, 300, 600}}
LIMITES = {
    "porta": (1, 65535), "colunas": (1, 4), "escurecimento": (-30, 30), "velocidade": (1, 14),
    "largura_mm": (10, 120), "altura_mm": (10, 120), "espaco_colunas_mm": (0, 20),
    "margem_esquerda_mm": (0, 50), "ajuste_vertical_mm": (-10, 10),
}


def normalizar(dados: dict) -> dict:
    """Junta com o padrão, converte tipos e descarta valores inválidos."""
    cfg = dict(PADRAO)
    for chave, valor in (dados or {}).items():
        if chave not in PADRAO:
            continue
        try:
            if chave in INTEIROS:
                valor = int(float(valor))
            elif chave in DECIMAIS:
                valor = float(str(valor).replace(",", "."))
            else:
                valor = str(valor).strip()
        except (TypeError, ValueError):
            continue
        if chave in OPCOES and valor not in OPCOES[chave]:
            continue
        if chave in LIMITES:
            mn, mx = LIMITES[chave]
            valor = max(mn, min(mx, valor))
        cfg[chave] = valor
    return cfg


def carregar() -> dict:
    try:
        return normalizar(json.loads(ARQUIVO.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return dict(PADRAO)


def salvar(dados: dict) -> dict:
    cfg = normalizar({**carregar(), **(dados or {})})
    ARQUIVO.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    return cfg
