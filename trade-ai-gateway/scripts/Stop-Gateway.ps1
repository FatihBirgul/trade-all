$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$PidPath = Join-Path (Get-Location) 'local_data\gateway.pid.json'
$StopPath = Join-Path (Get-Location) 'local_data\gateway.stop.json'
if (-not (Test-Path $PidPath)) { Write-Host 'Bu klasör için çalışan gateway kaydı yok.'; return }
$State = Get-Content -Raw $PidPath | ConvertFrom-Json
if ($State.pid -le 0 -or $State.run_id -notmatch '^[a-f0-9]{32}$') { throw 'Gateway kontrol kaydı doğrulanamadı.' }
# Signal only the gateway which owns this exact run record. Never kill a PID.
$Body = @{ pid = $State.pid; run_id = $State.run_id } | ConvertTo-Json -Compress
[IO.File]::WriteAllText($StopPath, $Body, [Text.UTF8Encoding]::new($false))
$Deadline = (Get-Date).AddSeconds(15)
while ((Test-Path $PidPath) -and (Get-Date) -lt $Deadline) { Start-Sleep -Milliseconds 250 }
if (Test-Path $PidPath) { throw 'Gateway kapanışı doğrulanamadı. Gateway terminalinde Ctrl+C kullanın; başka süreç sonlandırılmadı.' }
Write-Host 'Gateway normal kapanışını tamamladı. Serve terminalinde de Ctrl+C kullanın.'
