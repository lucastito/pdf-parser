<#
.SYNOPSIS
    PASSO 1 de 2 — instala tudo o que o experimento precisa. Rode uma vez.

.DESCRIPTION
    Instala e verifica, sem repetir trabalho: Python, dependências, servidor de
    inferência e os três modelos (~7 GB). Idempotente — interromper e rodar de
    novo continua de onde parou.

    Ao final roda a suíte de testes. Se ela falhar, o script para: medir com um
    clone inconsistente produziria números sem valor.

.EXAMPLE
    .\scripts\1-preparar-maquina.ps1

.EXAMPLE
    .\scripts\1-preparar-maquina.ps1 -SemModelos   # só o ambiente Python
#>
param([switch]$SemModelos)

$ErrorActionPreference = "Stop"
$RAIZ = Split-Path -Parent $PSScriptRoot
Set-Location $RAIZ
$env:PYTHONIOENCODING = "utf-8"

$MODELOS = @("qwen3:1.7b", "qwen3:4b", "qwen3-vl:4b")

function Passo($n, $t) { Write-Host "`n[$n/5] $t" -ForegroundColor Cyan }
function Ok($t)        { Write-Host "      ok   $t" -ForegroundColor Green }
function Aviso($t)     { Write-Host "      ...  $t" -ForegroundColor Yellow }
function Falha($t)     { Write-Host "      X    $t" -ForegroundColor Red }

function AtualizarPath {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
}

Write-Host "`n=== PASSO 1 de 2: PREPARAR A MAQUINA ===" -ForegroundColor White

Passo 1 "Python"
AtualizarPath
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Aviso "instalando Python..."
    winget install --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements --silent
    AtualizarPath
}
if (Get-Command python -ErrorAction SilentlyContinue) { Ok (python --version 2>&1) }
else { Falha "instale o Python e rode de novo"; exit 1 }

Passo 2 "Dependencias"
python -m pip install --quiet --upgrade pip
python -m pip install --quiet pymupdf pydantic pytest pytest-cov
Ok "pymupdf, pydantic, pytest, pytest-cov"

Passo 3 "Testes (valida o clone antes de qualquer medicao)"
$saida = python -m pytest --quiet 2>&1 | Select-Object -Last 2
if ($LASTEXITCODE -ne 0) {
    Falha "testes falharam — nao prossiga"
    $saida | ForEach-Object { Write-Host "           $_" }
    exit 1
}
Ok ($saida -join " ")

Passo 4 "Servidor de inferencia"
if ($SemModelos) {
    Aviso "pulado (-SemModelos)"
} else {
    AtualizarPath
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        Aviso "instalando Ollama..."
        winget install --id Ollama.Ollama --accept-source-agreements --accept-package-agreements --silent
        AtualizarPath
        Start-Sleep -Seconds 5
    }
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        Falha "instale manualmente: https://ollama.com/download"
        exit 1
    }
    Ok "ollama presente"

    if (-not (Get-Process ollama -ErrorAction SilentlyContinue)) {
        Aviso "iniciando servidor..."
        Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 6
    }
    try {
        Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 10 | Out-Null
        Ok "servidor respondendo"
    } catch {
        Falha "servidor nao responde — abra outro terminal e rode: ollama serve"
        exit 1
    }

    $presentes = (ollama list 2>&1 | Select-Object -Skip 1) -join "`n"
    foreach ($m in $MODELOS) {
        if ($presentes -match [regex]::Escape($m)) { Ok "$m ja presente" }
        else {
            Aviso "baixando $m ..."
            ollama pull $m
            if ($LASTEXITCODE -eq 0) { Ok $m } else { Falha "falhou: $m" }
        }
    }
}

Passo 5 "Diagnostico"
python -m parser.cli ambiente
$diag = $LASTEXITCODE

Write-Host "`n=== PASSO 1 CONCLUIDO ===" -ForegroundColor Green
if ($diag -eq 0) {
    Write-Host @"

Proximo passo:

    .\scripts\2-rodar-experimento.ps1 -Documento "C:\caminho\do\documento.pdf"

"@ -ForegroundColor White
} else {
    Write-Host "`nResolva os avisos acima antes do passo 2.`n" -ForegroundColor Yellow
}
