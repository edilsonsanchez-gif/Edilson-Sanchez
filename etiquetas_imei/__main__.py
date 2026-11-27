"""Linha de comando: python -m etiquetas_imei [--porta 8100] [--host 0.0.0.0]"""

from __future__ import annotations

import argparse

from . import servidor


def main() -> None:
    p = argparse.ArgumentParser(prog="etiquetas_imei", description="Lê os IMEIs da caixa do celular e imprime na Zebra.")
    p.add_argument("--host", default="0.0.0.0", help="0.0.0.0 deixa abrir pelo celular na mesma rede (padrão)")
    p.add_argument("--porta", type=int, default=8100)
    a = p.parse_args()
    servidor.rodar(a.host, a.porta)


if __name__ == "__main__":
    main()
