# Envia um .txt de etiquetas (comandos ZPL ou EPL) direto para a impressora de etiquetas, sem o driver "desenhar" o texto.
# Uso: arraste o .txt sobre "Imprimir TXT na Elgin.bat", ou de dois cliques nele para imprimir o .txt de
# etiquetas mais recente da pasta Downloads (o de teste so se nao houver outro). Depois de impresso, o arquivo
# vai para Downloads\Etiquetas impressas.
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
    $automatico = -not $Arquivo
    if ($automatico) {
        # Pega o .txt de etiquetas mais novo da pasta Downloads (qualquer nome), deixando o de teste por ultimo.
        $downloads = Join-Path $env:USERPROFILE "Downloads"
        $candidatos = Get-ChildItem -Path $downloads -Filter *.txt -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Length -lt 2MB } |
            Where-Object { $t = [System.IO.File]::ReadAllText($_.FullName); ($t -match '\^XA' -and $t -match '\^XZ') -or ($t -match '(?m)^N\s*$' -and $t -match '(?m)^P\d+') } |
            Sort-Object @{ Expression = { $_.Name -like "etiqueta-teste*" } }, @{ Expression = { $_.LastWriteTime }; Descending = $true }
        $escolhido = $candidatos | Select-Object -First 1
        if (-not $escolhido) {
            throw "Nenhum arquivo de etiquetas (.txt) na pasta Downloads deste computador. Se voce baixou pelo celular, o arquivo ficou no celular: passe o .txt para este computador (ou abra a pagina aqui no computador e baixe de novo)."
        }
        if ($escolhido.Name -like "etiqueta-teste*") {
            Write-Host "Atencao: o unico arquivo de etiquetas encontrado em Downloads e o de TESTE."
            Write-Host "As etiquetas dos IMEIs que voce fotografou nao estao neste computador."
            $r = Read-Host "Imprimir o teste mesmo assim? (s/n)"
            if ($r -notmatch '^[sS]') { exit 1 }
        }
        $Arquivo = $escolhido.FullName
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

    $info = Get-Item -LiteralPath $Arquivo
    $dados = [System.IO.File]::ReadAllBytes($info.FullName)
    $texto = [System.Text.Encoding]::ASCII.GetString($dados)
    $imeis = [regex]::Matches($texto, '(?<![0-9])[0-9]{15}(?![0-9])') | ForEach-Object { $_.Value } | Select-Object -Unique
    Write-Host "Arquivo: $($info.Name)  (baixado em $($info.LastWriteTime.ToString('dd/MM/yyyy HH:mm')))"
    Write-Host "IMEIs:   $($imeis -join ', ')"
    [ImpressoraRaw]::Enviar($Impressora, $dados)
    Write-Host ""
    Write-Host "Enviado para $Impressora"

    # Guarda o arquivo ja impresso, para o proximo duplo clique nao imprimir de novo.
    if ($automatico) {
        $pasta = Join-Path $info.DirectoryName "Etiquetas impressas"
        New-Item -ItemType Directory -Force -Path $pasta | Out-Null
        $destino = Join-Path $pasta ("{0:yyyyMMdd-HHmmss}-{1}" -f (Get-Date), $info.Name)
        Move-Item -LiteralPath $info.FullName -Destination $destino -Force
        Write-Host "Arquivo guardado em: Downloads\Etiquetas impressas"
    }
    exit 0
} catch {
    Write-Host ""
    Write-Host "ERRO: $($_.Exception.Message)"
    exit 1
}
