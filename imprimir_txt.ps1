# Envia um .txt de etiquetas (comandos ZPL ou EPL) direto para a impressora de etiquetas, sem o driver "desenhar" o texto.
# Uso: arraste o .txt sobre "Imprimir TXT na Elgin.bat", ou dê dois cliques nele para imprimir
# o etiquetas-imei*.txt / etiqueta-teste*.txt mais recente da pasta Downloads.
param([string]$Arquivo = "", [string]$Impressora = "")

$ErrorActionPreference = "Stop"

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class ImpressoraRaw {
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public class DOCINFO { public string pDocName; public string pOutputFile; public string pDataType; }
    [DllImport("winspool.drv", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool OpenPrinter(string nome, out IntPtr h, IntPtr padrao);
    [DllImport("winspool.drv", SetLastError = true)] static extern bool ClosePrinter(IntPtr h);
    [DllImport("winspool.drv", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern int StartDocPrinter(IntPtr h, int nivel, DOCINFO di);
    [DllImport("winspool.drv", SetLastError = true)] static extern bool EndDocPrinter(IntPtr h);
    [DllImport("winspool.drv", SetLastError = true)] static extern bool StartPagePrinter(IntPtr h);
    [DllImport("winspool.drv", SetLastError = true)] static extern bool EndPagePrinter(IntPtr h);
    [DllImport("winspool.drv", SetLastError = true)] static extern bool WritePrinter(IntPtr h, byte[] dados, int tam, out int escrito);
    public static void Enviar(string impressora, byte[] dados) {
        IntPtr h;
        if (!OpenPrinter(impressora, out h, IntPtr.Zero)) throw new Exception("Nao encontrei a impressora '" + impressora + "'.");
        try {
            DOCINFO di = new DOCINFO(); di.pDocName = "Etiquetas IMEI"; di.pDataType = "RAW";
            if (StartDocPrinter(h, 1, di) == 0) throw new Exception("O Windows recusou a impressao (erro " + Marshal.GetLastWin32Error() + ").");
            StartPagePrinter(h);
            int escrito;
            bool ok = WritePrinter(h, dados, dados.Length, out escrito);
            EndPagePrinter(h); EndDocPrinter(h);
            if (!ok || escrito != dados.Length) throw new Exception("Falha ao enviar os dados (erro " + Marshal.GetLastWin32Error() + ").");
        } finally { ClosePrinter(h); }
    }
}
"@

try {
    if (-not $Arquivo) {
        $downloads = Join-Path $env:USERPROFILE "Downloads"
        $ultimo = Get-ChildItem -Path $downloads -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like "etiquetas-imei*.txt" -or $_.Name -like "etiqueta-teste*.txt" } |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if (-not $ultimo) { throw "Nenhum etiquetas-imei*.txt na pasta Downloads. Arraste o arquivo sobre o atalho." }
        $Arquivo = $ultimo.FullName
    }
    if (-not (Test-Path -LiteralPath $Arquivo)) { throw "Arquivo nao encontrado: $Arquivo" }

    # Impressora: a do parametro, a salva em impressora.txt ao lado deste script, ou a primeira com L42 / Elgin no nome.
    $salva = Join-Path $PSScriptRoot "impressora.txt"
    if (-not $Impressora -and (Test-Path -LiteralPath $salva)) { $Impressora = (Get-Content -LiteralPath $salva -TotalCount 1).Trim() }
    if (-not $Impressora) {
        $nomes = @(Get-CimInstance Win32_Printer | Select-Object -ExpandProperty Name)
        $Impressora = $nomes | Where-Object { $_ -match "L42|Elgin" } | Select-Object -First 1
        if (-not $Impressora) {
            Write-Host "Nao achei uma impressora Elgin L42. Impressoras instaladas:"
            for ($i = 0; $i -lt $nomes.Count; $i++) { Write-Host ("  {0}) {1}" -f ($i + 1), $nomes[$i]) }
            $n = Read-Host "Digite o numero da impressora de etiquetas"
            $Impressora = $nomes[[int]$n - 1]
            Set-Content -LiteralPath $salva -Value $Impressora -Encoding UTF8
            Write-Host "Impressora guardada em impressora.txt (apague o arquivo para escolher de novo)."
        }
    }

    $dados = [System.IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $Arquivo))
    [ImpressoraRaw]::Enviar($Impressora, $dados)
    Write-Host ""
    Write-Host "Enviado: $(Split-Path -Leaf $Arquivo)  ->  $Impressora"
    exit 0
} catch {
    Write-Host ""
    Write-Host "ERRO: $($_.Exception.Message)"
    exit 1
}
