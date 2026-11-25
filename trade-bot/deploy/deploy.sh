#!/usr/bin/env bash
# GitHub Actions'in SSH ile cagirdigi dagitim adimi. Dagitim kullanicisi olarak calisir.
set -euo pipefail

APP_DIR=/opt/tradebot
cd "$APP_DIR"
git pull --ff-only
.venv/bin/pip install --quiet -e trade-bot -r trade-ai-unified/requirements-lock.txt
sudo /usr/bin/systemctl restart tradebot
sleep 5
if ! sudo /usr/bin/systemctl is-active tradebot >/dev/null; then
  echo "tradebot servisi baslamadi" >&2
  sudo /usr/bin/journalctl -u tradebot -n 40 --no-pager >&2 || true
  exit 1
fi
echo "dagitim tamam: $(git rev-parse --short HEAD)"
# Servis acilisini ve Exness akislarini dogrula (yalnizca calisma durumu; hesap bilgisi yazilmaz).
"$APP_DIR/trade-bot/deploy/status.sh" --wait 60 || true
