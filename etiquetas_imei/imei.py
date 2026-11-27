"""Validação de IMEI (15 dígitos com dígito verificador de Luhn)."""

from __future__ import annotations

import re


def luhn_valido(numero: str) -> bool:
    if not numero.isdigit():
        return False
    soma = 0
    for i, c in enumerate(reversed(numero)):
        d = int(c)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        soma += d
    return soma % 10 == 0


def limpar(texto: str | None) -> str:
    return re.sub(r"\D", "", texto or "")


def valido(imei: str) -> bool:
    return len(imei) == 15 and luhn_valido(imei)


def encontrar(texto: str) -> list[str]:
    """IMEIs válidos num texto qualquer (ex.: conteúdo de um código de barras), na ordem em que aparecem."""
    achados: list[str] = []
    for grupo in re.findall(r"\d[\d \-]{13,22}\d", texto or ""):
        num = limpar(grupo)
        if valido(num) and num not in achados:
            achados.append(num)
    return achados
