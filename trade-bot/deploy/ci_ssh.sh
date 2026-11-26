#!/usr/bin/env bash
# GitHub Actions adimlarinda sunucuya SSH baglantisini hazirlar (anahtar ~/.ssh/deploy_key, known_hosts).
# Ortam: VPS_HOST, VPS_USER, VPS_SSH_KEY (zorunlu), VPS_PORT, VPS_KNOWN_HOSTS. Anahtarin icerigi gunluge yazilmaz.
set -euo pipefail
if [ -z "${VPS_HOST:-}" ] || [ -z "${VPS_USER:-}" ] || [ -z "${VPS_SSH_KEY:-}" ]; then
  echo "::error::VPS_HOST, VPS_USER ve VPS_SSH_KEY secret'lari tanimli olmali (trade-bot/deploy/README.md)"
  exit 1
fi
port="${VPS_PORT:-22}"
install -d -m 700 ~/.ssh
python3 "$(dirname "$0")/ssh_key_normalize.py" ~/.ssh/deploy_key
if ! ssh-keygen -y -f ~/.ssh/deploy_key >/dev/null 2>&1; then
  echo "::error::VPS_SSH_KEY gecerli bir ozel anahtar degil"
  exit 1
fi
if [ -n "${VPS_KNOWN_HOSTS:-}" ]; then
  printf '%s\n' "$VPS_KNOWN_HOSTS" > ~/.ssh/known_hosts
else
  ssh-keyscan -p "$port" "$VPS_HOST" > ~/.ssh/known_hosts 2>/dev/null
fi
