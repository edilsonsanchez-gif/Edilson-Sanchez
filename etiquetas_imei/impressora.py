"""Envio do ZPL "cru" (RAW) para a Zebra: pela rede (porta 9100), pelo spooler do Windows, pelo CUPS ou para um arquivo."""

from __future__ import annotations

import shutil
import socket
import subprocess
import sys
from pathlib import Path


class ErroImpressora(RuntimeError):
    pass


def enviar(zpl: str, cfg: dict) -> str:
    """Envia e devolve uma frase dizendo para onde foi."""
    dados = zpl.encode("utf-8")
    modo = cfg.get("modo", "rede")
    if modo == "rede":
        return _rede(dados, str(cfg.get("ip", "")).strip(), int(cfg.get("porta", 9100)))
    if modo == "windows":
        return _windows(dados, str(cfg.get("nome_impressora", "")).strip())
    if modo == "cups":
        return _cups(dados, str(cfg.get("nome_impressora", "")).strip())
    if modo == "arquivo":
        caminho = Path(str(cfg.get("arquivo_saida") or "etiquetas.zpl")).expanduser()
        with caminho.open("ab") as f:
            f.write(dados)
        return f"salvo em {caminho.resolve()}"
    raise ErroImpressora(f"Modo de impressora desconhecido: {modo}")


def listar() -> list[str]:
    """Impressoras instaladas no computador (Windows ou CUPS). Vazio se não houver como listar."""
    try:
        if sys.platform == "win32":
            return _windows_listar()
        if shutil.which("lpstat"):
            saida = subprocess.run(["lpstat", "-e"], capture_output=True, text=True, timeout=5).stdout
            return [linha.strip() for linha in saida.splitlines() if linha.strip()]
    except Exception:  # noqa: BLE001 - listar é só uma ajuda na tela de configuração
        pass
    return []


# --- Rede -----------------------------------------------------------------

def _rede(dados: bytes, ip: str, porta: int) -> str:
    if not ip:
        raise ErroImpressora("Informe o IP da impressora nas configurações.")
    try:
        with socket.create_connection((ip, porta), timeout=8) as s:
            s.sendall(dados)
    except OSError as e:
        raise ErroImpressora(f"Não consegui falar com a impressora em {ip}:{porta} ({e}). "
                             "Confira se ela está ligada, na mesma rede e se o IP está certo.") from e
    return f"enviado para {ip}:{porta}"


# --- CUPS (Linux/macOS) ---------------------------------------------------

def _cups(dados: bytes, nome: str) -> str:
    if not shutil.which("lp"):
        raise ErroImpressora("O comando 'lp' (CUPS) não foi encontrado neste computador.")
    cmd = ["lp", "-o", "raw"] + (["-d", nome] if nome else [])
    r = subprocess.run(cmd, input=dados, capture_output=True, timeout=20)
    if r.returncode != 0:
        raise ErroImpressora("CUPS recusou a impressão: " + (r.stderr.decode(errors="replace").strip() or "erro desconhecido"))
    return f"enviado para {nome or 'a impressora padrão'} (CUPS)"


# --- Windows (spooler, modo RAW, sem instalar nada) -----------------------

def _winspool():
    import ctypes
    from ctypes import wintypes

    ws = ctypes.WinDLL("winspool.drv", use_last_error=True)

    class DOC_INFO_1(ctypes.Structure):
        _fields_ = [("pDocName", wintypes.LPWSTR), ("pOutputFile", wintypes.LPWSTR), ("pDatatype", wintypes.LPWSTR)]

    ws.OpenPrinterW.argtypes = [wintypes.LPWSTR, ctypes.POINTER(wintypes.HANDLE), ctypes.c_void_p]
    ws.OpenPrinterW.restype = wintypes.BOOL
    ws.StartDocPrinterW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(DOC_INFO_1)]
    ws.StartDocPrinterW.restype = wintypes.DWORD
    ws.StartPagePrinter.argtypes = [wintypes.HANDLE]
    ws.WritePrinter.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    ws.WritePrinter.restype = wintypes.BOOL
    ws.EndPagePrinter.argtypes = [wintypes.HANDLE]
    ws.EndDocPrinter.argtypes = [wintypes.HANDLE]
    ws.ClosePrinter.argtypes = [wintypes.HANDLE]
    ws.GetDefaultPrinterW.argtypes = [wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    ws.GetDefaultPrinterW.restype = wintypes.BOOL
    ws.EnumPrintersW.argtypes = [wintypes.DWORD, wintypes.LPWSTR, wintypes.DWORD, ctypes.c_void_p,
                                 wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD)]
    ws.EnumPrintersW.restype = wintypes.BOOL
    return ctypes, wintypes, ws, DOC_INFO_1


def _windows(dados: bytes, nome: str) -> str:
    if sys.platform != "win32":
        raise ErroImpressora("O modo 'Windows' só funciona com o programa rodando num computador Windows.")
    ctypes, wintypes, ws, DOC_INFO_1 = _winspool()
    if not nome:
        tam = wintypes.DWORD(0)
        ws.GetDefaultPrinterW(None, ctypes.byref(tam))
        buf = ctypes.create_unicode_buffer(tam.value or 1)
        if not ws.GetDefaultPrinterW(buf, ctypes.byref(tam)):
            raise ErroImpressora("Escolha a impressora Zebra nas configurações.")
        nome = buf.value
    h = wintypes.HANDLE()
    if not ws.OpenPrinterW(nome, ctypes.byref(h), None):
        raise ErroImpressora(f"Não encontrei a impressora '{nome}' no Windows.")
    try:
        info = DOC_INFO_1("Etiquetas IMEI", None, "RAW")
        if not ws.StartDocPrinterW(h, 1, ctypes.byref(info)):
            raise ErroImpressora(f"O Windows recusou a impressão em '{nome}' (erro {ctypes.get_last_error()}).")
        try:
            ws.StartPagePrinter(h)
            escrito = wintypes.DWORD(0)
            buf = ctypes.create_string_buffer(dados, len(dados))
            ok = ws.WritePrinter(h, buf, len(dados), ctypes.byref(escrito))
            ws.EndPagePrinter(h)
        finally:
            ws.EndDocPrinter(h)
        if not ok or escrito.value != len(dados):
            raise ErroImpressora(f"Falha ao enviar os dados para '{nome}' (erro {ctypes.get_last_error()}).")
    finally:
        ws.ClosePrinter(h)
    return f"enviado para {nome}"


def _windows_listar() -> list[str]:
    ctypes, wintypes, ws, _ = _winspool()

    class PRINTER_INFO_4(ctypes.Structure):
        _fields_ = [("pPrinterName", wintypes.LPWSTR), ("pServerName", wintypes.LPWSTR), ("Attributes", wintypes.DWORD)]

    flags = 0x2 | 0x4  # PRINTER_ENUM_LOCAL | PRINTER_ENUM_CONNECTIONS
    precisa, qtd = wintypes.DWORD(0), wintypes.DWORD(0)
    ws.EnumPrintersW(flags, None, 4, None, 0, ctypes.byref(precisa), ctypes.byref(qtd))
    if not precisa.value:
        return []
    buf = ctypes.create_string_buffer(precisa.value)
    if not ws.EnumPrintersW(flags, None, 4, buf, precisa, ctypes.byref(precisa), ctypes.byref(qtd)):
        return []
    lista = ctypes.cast(buf, ctypes.POINTER(PRINTER_INFO_4))
    return [lista[i].pPrinterName for i in range(qtd.value)]
