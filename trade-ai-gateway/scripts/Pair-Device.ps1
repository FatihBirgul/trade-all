param([switch]$ScannerWrite)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if ($ScannerWrite) { & '.\.venv\Scripts\python.exe' -m trade_gateway pair --scanner-write }
else { & '.\.venv\Scripts\python.exe' -m trade_gateway pair }
