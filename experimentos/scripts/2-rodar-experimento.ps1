<#
.SYNOPSIS
    PASSO 2 de 2 — roda o experimento, grava os resultados e commita numa branch.

.DESCRIPTION
    Executa todas as estratégias de extração no mesmo ambiente, grava os
    resultados com procedência em resultados/<maquina>/, cria a branch
    experimento/<maquina> e commita.

    O push NAO acontece aqui: é o único passo irreversível em repositório
    público, e fica por sua conta depois de conferir com 'git show'.

    As estratégias com modelo são lentas em CPU. Uma página pode levar minutos —
    ou não terminar. Isso é resultado do experimento, não defeito dele.

.EXAMPLE
    .\scripts\2-rodar-experimento.ps1 -Documento "C:\docs\tabela.pdf"

.EXAMPLE
    .\scripts\2-rodar-experimento.ps1 -Documento "C:\docs\tabela.pdf" -SemModelos
#>
param(
    [Parameter(Mandatory = $true)][string]$Documento,
    [int]$Dpi = 150,
    [int]$TimeoutSegundos = 3600,
    [switch]$SemModelos,
    [switch]$SemCommit
)

$ErrorActionPreference = "Stop"
$RAIZ = Split-Path -Parent $PSScriptRoot
Set-Location $RAIZ
$env:PYTHONIOENCODING = "utf-8"

function Passo($n, $t) { Write-Host "`n[$n/3] $t" -ForegroundColor Cyan }
function Ok($t)        { Write-Host "      ok   $t" -ForegroundColor Green }
function Aviso($t)     { Write-Host "      ...  $t" -ForegroundColor Yellow }
function Falha($t)     { Write-Host "      X    $t" -ForegroundColor Red }

Write-Host "`n=== PASSO 2 de 2: RODAR O EXPERIMENTO ===" -ForegroundColor White

Passo 1 "Pre-condicoes"

if (-not (Test-Path $Documento)) { Falha "documento nao encontrado: $Documento"; exit 1 }
Ok (Split-Path -Leaf $Documento)

$saida = python -m pytest --quiet 2>&1 | Select-Object -Last 2
if ($LASTEXITCODE -ne 0) {
    Falha "testes falharam — rode .\scripts\1-preparar-maquina.ps1"
    exit 1
}
Ok ($saida -join " ")

if (-not $SemModelos) {
    try {
        Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 10 | Out-Null
        Ok "servidor de inferencia respondendo"
    } catch {
        Falha "servidor nao responde. Use -SemModelos ou rode: ollama serve"
        exit 1
    }
}

Passo 2 "Execucao"
Write-Host "      (pode levar muito tempo — as estrategias com modelo sao lentas em CPU)`n" -ForegroundColor Gray

$argumentos = @(
    "-m", "parser.cli", "experimento",
    "--documento", $Documento,
    "--dpi", $Dpi,
    "--timeout", $TimeoutSegundos
)
if ($SemModelos) { $argumentos += "--sem-modelos" }

python @argumentos
if ($LASTEXITCODE -ne 0) { Falha "o experimento falhou; nada foi commitado"; exit 1 }

Passo 3 "Registro no git"

if ($SemCommit) {
    Aviso "pulado (-SemCommit)"
    Write-Host "`n=== CONCLUIDO ===`n" -ForegroundColor Green
    exit 0
}

$maquina = python -c "import sys; sys.path.insert(0,'src'); from parser.procedencia import identificador_de_maquina as f; print(f())"
$branch = "experimento/$maquina"

if ((git rev-parse --abbrev-ref HEAD) -ne $branch) {
    if (git show-ref --verify --quiet "refs/heads/$branch") { git checkout $branch }
    else { git checkout -b $branch }
}
Ok "branch $branch"

# resultados/ e' ignorado por padrao para que a execucao seja cega; a rodada
# desta maquina entra explicitamente, com -f.
git add -f "experimentos/resultados/$maquina"
if (-not (git diff --cached --name-only)) {
    Aviso "nada novo a registrar"
    exit 0
}

$mensagem = "exp: rodada em $maquina`n`nExecucao completa das estrategias no mesmo ambiente, com procedencia`nregistrada. A acuracia sera calculada depois, sobre estes dados brutos."
git commit -q -m $mensagem
if ($LASTEXITCODE -ne 0) {
    Falha "commit bloqueado — provavelmente pela guarda de confidencialidade"
    exit 1
}
Ok (git log --oneline -1)

Write-Host @"

=== CONCLUIDO ===

Para enviar:

    git push -u origin $branch

Depois abra o pull request de '$branch' para 'main' no GitHub.

O push ficou de fora deste script porque e' irreversivel em repositorio
publico. Confira antes com:  git show

"@ -ForegroundColor Green
