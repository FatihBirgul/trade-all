param([Parameter(Mandatory=$true)][string]$PublicOrigin)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    py -3.11 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 kurulamadı.' }
    & '.\.venv\Scripts\python.exe' -m pip install -e .
    if ($LASTEXITCODE -ne 0) { throw 'Gateway bağımlılıkları kurulamadı.' }
}
$env:GATEWAY_PUBLIC_ORIGIN = $PublicOrigin
# Foreground, loopback only. Ctrl+C stops only this gateway process.
& '.\.venv\Scripts\python.exe' -m trade_gateway serve
