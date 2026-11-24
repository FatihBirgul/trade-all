$ErrorActionPreference = 'Stop'
# Explicit user-run network action. This script is never invoked by setup/start.
# First inspect existing mappings. Do not replace another mapping on port 443.
tailscale serve status
Write-Host 'Var olan 443 eşlemesini koruyun. Devam yalnızca bu port gateway için ayrıldıysa uygundur.'
$answer = Read-Host 'Özel HTTPS Serve başlatılsın mı? EVET yazın'
if ($answer -cne 'EVET') { return }
# Foreground: Ctrl+C removes this session; no persistent --bg mapping.
tailscale serve --https=443 http://127.0.0.1:8787
