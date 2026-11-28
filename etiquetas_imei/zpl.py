"""Gera o ZPL das etiquetas (padrão 40x25 mm, 2 colunas) para impressoras Zebra."""

from __future__ import annotations

from dataclasses import dataclass

from . import imei as imei_mod


class ErroEtiqueta(ValueError):
    pass


@dataclass(frozen=True)
class Etiqueta:
    """Conteúdo de uma etiqueta: um ou dois IMEIs (com o rótulo de cada um) e uma descrição opcional."""
    linhas: tuple[tuple[str, str], ...]   # ((rótulo, imei), ...)
    descricao: str = ""


def _modulos_code128_digitos(n: int) -> int:
    """Largura em módulos de um Code 128 só com dígitos (subconjunto C, troca para B no último se for ímpar)."""
    pares, sobra = divmod(n, 2)
    return 11 + 11 * pares + (22 if sobra else 0) + 11 + 13


def _dados_code128(numero: str) -> str:
    """Campo ^FD com subconjuntos explícitos: >; inicia Code C, >6 troca para Code B no último dígito ímpar."""
    if len(numero) % 2 == 0:
        return ">;" + numero
    return ">;" + numero[:-1] + ">6" + numero[-1]


def _texto(x: int, y: int, largura: int, altura: int, texto: str) -> str:
    texto = texto.replace("^", " ").replace("~", " ")
    larg_fonte = max(8, round(altura * 0.85))
    return f"^FO{x},{y}^A0N,{altura},{larg_fonte}^FB{largura},1,0,C^FD{texto}^FS"


def _cortar(texto: str, largura: int, altura: int) -> str:
    cabe = max(4, int(largura / (altura * 0.52)))
    return texto if len(texto) <= cabe else texto[: cabe - 1].rstrip() + "."


def _campos_etiqueta(et: Etiqueta, x0: int, larg: int, alt: int) -> list[str]:
    campos: list[str] = []
    margem = max(4, round(larg * 0.03))
    area = larg - 2 * margem
    topo = round(alt * 0.06)
    y = topo
    if et.descricao:
        h_desc = max(12, round(alt * 0.085))
        campos.append(_texto(x0 + margem, y, area, h_desc, _cortar(et.descricao, area, h_desc)))
        y += h_desc + round(alt * 0.03)

    n = len(et.linhas)
    h_txt = max(12, round(alt * 0.09))
    folga_txt = max(2, round(alt * 0.015))
    entre = round(alt * 0.06)
    livre = alt - y - topo - entre * (n - 1)
    bloco = livre / n
    h_barra = max(20, int(bloco - h_txt - folga_txt))

    for rotulo, numero in et.linhas:
        mods = _modulos_code128_digitos(len(numero))
        modulo = max(1, larg // (mods + 20))           # 10 módulos de zona livre de cada lado
        x_barra = x0 + (larg - mods * modulo) // 2
        campos.append(f"^BY{modulo},3,{h_barra}^FO{x_barra},{round(y)}^BCN,{h_barra},N,N,N^FD{_dados_code128(numero)}^FS")
        y += h_barra + folga_txt
        campos.append(_texto(x0 + margem, round(y), area, h_txt, f"{rotulo}: {numero}"))
        y += h_txt + entre
    return campos


def montar_etiquetas(itens: list[dict], layout: str = "par") -> list[Etiqueta]:
    """Transforma a lista de celulares em etiquetas, na ordem de impressão (esquerda→direita, linha a linha)."""
    etiquetas: list[Etiqueta] = []
    for n, item in enumerate(itens, 1):
        i1 = imei_mod.limpar(item.get("imei1"))
        i2 = imei_mod.limpar(item.get("imei2"))
        desc = " ".join(str(item.get("descricao") or "").split())[:60]
        try:
            copias = int(item.get("copias") or 1)
        except (TypeError, ValueError):
            copias = 1
        copias = max(1, min(copias, 500))
        if not i1 and i2:
            i1, i2 = i2, ""
        for valor in (i1, i2):
            if valor and len(valor) != 15:
                raise ErroEtiqueta(f"Celular {n}: o IMEI {valor} não tem 15 dígitos.")
        if not i1:
            raise ErroEtiqueta(f"Celular {n}: informe pelo menos um IMEI.")

        if layout == "separado":
            grupo = [Etiqueta((("IMEI 1", i1),), desc)]
            if i2:
                grupo.append(Etiqueta((("IMEI 2", i2),), desc))
        else:
            linhas = (("IMEI 1", i1), ("IMEI 2", i2)) if i2 else (("IMEI", i1),)
            grupo = [Etiqueta(linhas, desc)]
        etiquetas.extend(grupo * copias)
    return etiquetas


def gerar(itens: list[dict], cfg: dict) -> tuple[str, int]:
    """Devolve (zpl, quantidade de etiquetas)."""
    etiquetas = montar_etiquetas(itens, cfg.get("layout", "par"))
    return gerar_de_etiquetas(etiquetas, cfg), len(etiquetas)


def gerar_de_etiquetas(etiquetas: list[Etiqueta], cfg: dict) -> str:
    pmm = {203: 8, 300: 12, 600: 24}.get(int(cfg.get("dpi", 203)), 8)
    larg = round(float(cfg.get("largura_mm", 40)) * pmm)
    alt = round(float(cfg.get("altura_mm", 25)) * pmm)
    cols = int(cfg.get("colunas", 2))
    espaco = round(float(cfg.get("espaco_colunas_mm", 2)) * pmm)
    margem = round(float(cfg.get("margem_esquerda_mm", 0)) * pmm)
    topo = max(-120, min(120, round(float(cfg.get("ajuste_vertical_mm", 0)) * pmm)))
    largura_total = margem + cols * larg + (cols - 1) * espaco

    cabecalho = (
        f"^XA^CI28^PW{largura_total}^LL{alt}^LH0,0^LT{topo}"
        f"^PR{int(cfg.get('velocidade', 3))}^MD{int(cfg.get('escurecimento', 0))}"
    )

    fileiras: list[tuple[Etiqueta, ...]] = [tuple(etiquetas[i:i + cols]) for i in range(0, len(etiquetas), cols)]
    # Fileiras iguais seguidas viram uma só com ^PQ (quantidade), o que deixa a impressão mais rápida.
    blocos: list[list] = []
    for f in fileiras:
        if blocos and blocos[-1][0] == f:
            blocos[-1][1] += 1
        else:
            blocos.append([f, 1])

    partes: list[str] = []
    for fileira, qtd in blocos:
        campos: list[str] = []
        for c, et in enumerate(fileira):
            campos.extend(_campos_etiqueta(et, margem + c * (larg + espaco), larg, alt))
        partes.append(cabecalho + "".join(campos) + f"^PQ{qtd},0,1,Y^XZ")
    return "\n".join(partes) + ("\n" if partes else "")


def etiqueta_teste(cfg: dict) -> str:
    exemplo = Etiqueta((("IMEI 1", "490154203237518"), ("IMEI 2", "356938035643809")), "TESTE DE IMPRESSAO")
    return gerar_de_etiquetas([exemplo] * int(cfg.get("colunas", 2)), cfg)
