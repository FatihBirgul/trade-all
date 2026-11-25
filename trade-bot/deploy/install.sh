#!/usr/bin/env bash
# Trade Bot tek seferlik sunucu kurulumu (Ubuntu 24.04). root olarak calistirilir, tekrar calistirmak guvenlidir.
#
#   sudo REPO_URL=https://github.com/FatihBirgul/trade-all.git bash install.sh
#
# Yaptiklari: servis kullanicisi (tradebot) ve dagitim kullanicisi (deploy), klasorler, NTP,
# repo + venv, /etc/tradebot/tradebot.env sablonu (600), systemd servisi, dagitim icin dar sudo izni.
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/FatihBirgul/trade-all.git}"
BRANCH="${BRANCH:-main}"
DEPLOY_USER="${DEPLOY_USER:-deploy}"
APP_DIR=/opt/tradebot
ENV_DIR=/etc/tradebot
ENV_FILE="$ENV_DIR/tradebot.env"
DATA_DIR=/var/lib/tradebot

if [ "$(id -u)" -ne 0 ]; then
  echo "Bu betik root olarak calistirilmali: sudo bash install.sh" >&2
  exit 1
fi

echo "==> Paketler"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git python3.12 python3.12-venv >/dev/null

echo "==> Saat esitleme (imza zaman damgasi buna bagli)"
timedatectl set-ntp true || echo "UYARI: NTP acilamadi; 'timedatectl status' ile kontrol edin" >&2

echo "==> Kullanicilar"
if ! id tradebot >/dev/null 2>&1; then
  useradd --system --home-dir "$DATA_DIR" --shell /usr/sbin/nologin tradebot
fi
if ! id "$DEPLOY_USER" >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash "$DEPLOY_USER"
fi

echo "==> Klasorler"
install -d -o "$DEPLOY_USER" -g "$DEPLOY_USER" -m 755 "$APP_DIR"
install -d -o tradebot -g tradebot -m 750 "$DATA_DIR"
install -d -o root -g tradebot -m 750 "$ENV_DIR"

echo "==> Kod"
if [ ! -d "$APP_DIR/.git" ]; then
  sudo -u "$DEPLOY_USER" git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
else
  sudo -u "$DEPLOY_USER" git -C "$APP_DIR" pull --ff-only
fi

echo "==> Python ortami"
if [ ! -x "$APP_DIR/.venv/bin/python" ]; then
  sudo -u "$DEPLOY_USER" python3.12 -m venv "$APP_DIR/.venv"
fi
sudo -u "$DEPLOY_USER" "$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
sudo -u "$DEPLOY_USER" "$APP_DIR/.venv/bin/pip" install --quiet \
  -e "$APP_DIR/trade-bot" -r "$APP_DIR/trade-ai-unified/requirements-lock.txt"

echo "==> Sir dosyasi"
if [ ! -f "$ENV_FILE" ]; then
  install -o tradebot -g tradebot -m 600 "$APP_DIR/trade-bot/.env.example" "$ENV_FILE"
  echo "    $ENV_FILE olusturuldu; degerleri doldurun: sudo nano $ENV_FILE"
fi
chown tradebot:tradebot "$ENV_FILE"
chmod 600 "$ENV_FILE"

echo "==> systemd"
install -o root -g root -m 644 "$APP_DIR/trade-bot/deploy/tradebot.service" /etc/systemd/system/tradebot.service
systemctl daemon-reload
systemctl enable tradebot >/dev/null

echo "==> Dagitim kullanicisi icin sudo izni (yalnizca servis yonetimi)"
SUDOERS=/etc/sudoers.d/tradebot-deploy
cat >"$SUDOERS.tmp" <<SUDO
$DEPLOY_USER ALL=(root) NOPASSWD: /usr/bin/systemctl restart tradebot, /usr/bin/systemctl is-active tradebot, /usr/bin/systemctl status tradebot --no-pager, /usr/bin/journalctl -u tradebot *
SUDO
visudo -cf "$SUDOERS.tmp" >/dev/null
install -o root -g root -m 440 "$SUDOERS.tmp" "$SUDOERS"
rm -f "$SUDOERS.tmp"

if grep -Eq '^EXNESS_API_KEY=.+' "$ENV_FILE"; then
  systemctl restart tradebot
  echo "Kurulum tamam; servis yeniden baslatildi: systemctl status tradebot"
else
  echo "Kurulum tamam. $ENV_FILE doldurulduktan sonra: sudo systemctl restart tradebot"
fi
