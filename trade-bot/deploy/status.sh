#!/usr/bin/env bash
# Botun herkese acik saglik ciktisini yazar (calisma durumu ve son taramanin sayilari; hesap bilgisi yok).
#   status.sh            : simdiki durum
#   status.sh --wait 60  : Exness akislari baglanana kadar en cok 60 sn bekler
set -euo pipefail

URL="${TRADEBOT_HEALTH_URL:-http://127.0.0.1:8090/health}"
wait_for=0
if [ "${1:-}" = "--wait" ]; then
  wait_for="${2:-60}"
fi

fetch() { curl -fsS --max-time 5 "$URL" 2>/dev/null; }

deadline=$(( $(date +%s) + wait_for ))
body=""
while :; do
  body="$(fetch || true)"
  case "$body" in *'"stream_connected":true'*) break ;; esac
  [ "$(date +%s)" -ge "$deadline" ] && break
  sleep 3
done

if [ -z "$body" ]; then
  echo "saglik: yanit yok ($URL)" >&2
  exit 1
fi
echo "saglik: $body"
# Son 24 saatin tarama ozeti (yalnizca sayilar ve nedenler; hesap bilgisi icermez). Eski surumde yoktur.
summary="$(curl -fsS --max-time 10 "${TRADEBOT_SUMMARY_URL:-${URL%/health}/health/summary}" 2>/dev/null || true)"
[ -n "$summary" ] && echo "ozet: $summary"
# Gunluk yedek: 36 saatten eskiyse (ya da hic alinmadiysa) uyar. Servis yeni baslamissa ilk yedek 30 dk icinde alinir.
backup_at="$(printf '%s' "$body" | sed -n 's/.*"last_backup_at":\([0-9][0-9]*\).*/\1/p')"
if [ -n "$backup_at" ] && [ $(( $(date +%s) - backup_at )) -gt 129600 ]; then
  echo "yedek: UYARI son yedek 36 saatten eski" >&2
elif [ -n "$backup_at" ]; then
  echo "yedek: guncel"
else
  echo "yedek: henuz alinmadi"
fi
case "$body" in
  *'"stream_connected":true'*) echo "akislar: bagli" ;;
  *) echo "akislar: BAGLI DEGIL" >&2; exit 2 ;;
esac
