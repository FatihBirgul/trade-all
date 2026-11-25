#!/usr/bin/env bash
# Trade Bot API'sini https://<IP>.sslip.io adresinden disari acar (Caddy + Let's Encrypt).
# Alan adi gerekmez: sslip.io, "203-0-113-7.sslip.io" adini 203.0.113.7 adresine cozer.
# Servis 127.0.0.1:8090'da kalir; disaridan yalnizca Caddy (80/443) gorunur. Tekrar calistirmak guvenlidir.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="${TEMPLATE:-$HERE/Caddyfile.template}"
CADDYFILE="${CADDYFILE:-/etc/caddy/Caddyfile}"
DRY="${CADDY_DRY:-0}"   # 1: yalnizca Caddyfile uret (testler icin)

detect_ip() {
  local ip=""
  ip="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i < NF; i++) if ($i == "src") print $(i + 1)}' | head -n 1)" || true
  [ -n "$ip" ] || ip="$(hostname -I 2>/dev/null | awk '{print $1}')" || true
  printf '%s' "$ip"
}

IP="${VPS_IP:-$(detect_ip)}"
if ! [[ "$IP" =~ ^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})$ ]]; then
  echo "HATA: gecerli bir IPv4 adresi bulunamadi (VPS_IP=$IP)." >&2
  exit 1
fi
for octet in "${BASH_REMATCH[@]:1}"; do
  if [ "$octet" -gt 255 ]; then
    echo "HATA: gecersiz IPv4 adresi: $IP" >&2
    exit 1
  fi
done
HOST="${IP//./-}.sslip.io"

render() {
  [ -r "$TEMPLATE" ] || { echo "HATA: sablon bulunamadi: $TEMPLATE" >&2; exit 1; }
  install -d -m 755 "$(dirname "$CADDYFILE")"
  sed "s/__HOST__/$HOST/g" "$TEMPLATE" >"$CADDYFILE.new"
  mv -f "$CADDYFILE.new" "$CADDYFILE"
}

if [ "$DRY" = 1 ]; then
  render
  echo "https://$HOST"
  exit 0
fi

if [ "$(id -u)" -ne 0 ]; then
  echo "Bu betik root olarak calistirilmali." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
if ! command -v caddy >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y -qq caddy >/dev/null
fi
render
caddy validate --config "$CADDYFILE" --adapter caddyfile >/dev/null
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q '^Status: active'; then
  ufw allow 80/tcp >/dev/null    # Let's Encrypt dogrulamasi ve HTTPS'e yonlendirme
  ufw allow 443/tcp >/dev/null
fi
systemctl enable caddy >/dev/null 2>&1 || true
systemctl restart caddy
install -d -m 755 /etc/tradebot
printf 'https://%s\n' "$HOST" >/etc/tradebot/public-url
chmod 644 /etc/tradebot/public-url
echo "https://$HOST"
