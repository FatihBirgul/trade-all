param(
    [ValidateSet('live', 'fixture')][string]$Mode = 'live',
    [string]$Database = '',
    [switch]$Scanner
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$Python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) {
    throw 'Create backend\.venv and install requirements-v2.txt first; see docs/V2_WINDOWS_SETUP.md.'
}
if (-not $env:V2_API_TOKEN -or $env:V2_API_TOKEN.Length -lt 24) {
    throw 'Set V2_API_TOKEN to your private random token in this session. Do not paste it into source files.'
}
if (-not $Database) { $Database = "..\local_data\v2-$Mode.sqlite" }
$LaunchArgs = @('start_v2.py', '--database', $Database, '--mode', $Mode)
if ($Scanner) { $LaunchArgs += '--scanner' }
& $Python @LaunchArgs
exit $LASTEXITCODE
