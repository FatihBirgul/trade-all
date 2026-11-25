#!/usr/bin/env bash
# Trade Bot — tek komutla sunucu kurulumu (Ubuntu 24.04, root).
#
#   bash <(curl -fsSL https://raw.githubusercontent.com/FatihBirgul/trade-all/main/trade-bot/deploy/bootstrap.sh)
#
# Sirasiyla: install.sh -> Exness degerlerini sorar ve /etc/tradebot/tradebot.env'e (600) yazar ->
# dagitim SSH anahtarini uretir -> telefon erisimi icin HTTPS'i kurar (Caddy, <IP>.sslip.io) ->
# GitHub Secrets degerlerini gosterir -> API kesif betigini calistirir ->
# servisi baslatir (dry-run: gercek emir gondermez). Tekrar calistirmak guvenlidir; girilen sirlar
# ekrana yazilmaz.
set -euo pipefail

RAW_BASE="${RAW_BASE:-https://raw.githubusercontent.com/FatihBirgul/trade-all/main/trade-bot/deploy}"
APP_DIR="${APP_DIR:-/opt/tradebot}"
ENV_FILE="${ENV_FILE:-/etc/tradebot/tradebot.env}"
VENV_PY="${VENV_PY:-$APP_DIR/.venv/bin/python}"
DEPLOY_USER="${DEPLOY_USER:-deploy}"
DEPLOY_HOME="${DEPLOY_HOME:-/home/$DEPLOY_USER}"
SSH_HOST_KEYS="${SSH_HOST_KEYS:-/etc/ssh}"
TTY="${BOOTSTRAP_TTY:-/dev/tty}"   # betik boruyla calistirilsa da girisler terminalden okunur
DRY="${BOOTSTRAP_DRY:-0}"          # 1: sistemde degisiklik yapan adimlari atla (yalnizca testler icin)
PUBLIC_URL=""

say()  { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
note() { printf '    %s\n' "$*"; }
die()  { printf '\nHATA: %s\n' "$*" >&2; exit 1; }

ask_secret() {  # ask_secret DEGISKEN "aciklama"  (giris ekranda gorunmez)
  local __name="$1" __value=""
  printf '%s: ' "$2" >&2
  IFS= read -r -s -u 3 __value || true
  printf '\n' >&2
  # Yapistirma sirasinda gelen bosluk ve satir sonu karakterlerini temizle.
  __value="${__value#"${__value%%[![:space:]]*}"}"
  __value="${__value%"${__value##*[![:space:]]}"}"
  printf -v "$__name" '%s' "$__value"
}

ask_yes() {  # ask_yes "soru"  -> e/E ise 0
  local answer=""
  printf '%s [e/H]: ' "$1" >&2
  IFS= read -r -u 3 answer || true
  [[ "$answer" =~ ^[eEyY] ]]
}

current_value() {  # mevcut env dosyasindaki degeri (tirnaksiz) dondurur
  [ -r "$ENV_FILE" ] || return 0
  sed -n "s/^$1=//p" "$ENV_FILE" | tail -n 1 | sed "s/^'\(.*\)'$/\1/; s/^\"\(.*\)\"$/\1/"
}

valid_shape() {  # yalnizca guvenli karakterler: tirnak, ters bolu, bosluk iceren deger env dosyasina yazilmaz
  [[ "$1" =~ ^[A-Za-z0-9._~:/+=@-]+$ ]]
}

collect_exness() {
  say "Exness API bilgileri"
  note "Degerler Exness Personal Area > Key Management ekranindan alinir."
  note "Yapistirdiginiz deger guvenlik icin ekranda GORUNMEZ; yapistirip Enter'a basin."
  if [ -n "$(current_value EXNESS_API_KEY)" ] && [ -n "$(current_value EXNESS_PRIVATE_KEY)" ]; then
    note "Daha once girilmis degerler bulundu (hesap: $(current_value EXNESS_ACCOUNT_ID))."
    if ! ask_yes "Bu degerleri degistirmek istiyor musunuz?"; then
      note "Mevcut degerler korunuyor."
      return 0
    fi
  fi
  local api_key private_key account_id gateway attempt
  for attempt in 1 2 3; do
    ask_secret api_key     "1/4  API anahtari kimligi (API key)"
    ask_secret private_key "2/4  Ozel anahtar (private key, 128 karakter)"
    ask_secret account_id  "3/4  Islem hesabi numarasi (cent hesap)"
    ask_secret gateway     "4/4  Gateway host (Key Management'taki DNS kutusu)"
    gateway="${gateway#https://}"; gateway="${gateway#http://}"; gateway="${gateway%%/*}"
    local problems=()
    valid_shape "$api_key" || problems+=("API anahtari bos ya da gecersiz karakter iceriyor")
    [[ "$private_key" =~ ^[0-9a-fA-F]{128}$ ]] || problems+=("ozel anahtar 128 hex karakter olmali (su an ${#private_key} karakter)")
    [[ "$account_id" =~ ^[1-9][0-9]{0,19}$ ]] || problems+=("hesap numarasi yalnizca rakamlardan olusmali")
    [[ "$gateway" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$ && "$gateway" == *.* ]] || problems+=("gateway host bir alan adi olmali (or. api.ornek.com)")
    if [ "${#problems[@]}" -eq 0 ] && [ -x "$VENV_PY" ]; then
      # Anahtarin gercekten gecerli bir Ed25519 anahtari oldugunu dogrula (deger ortam degiskeniyle gecer, ekrana yazilmaz).
      BOOT_KEY="$private_key" "$VENV_PY" -c 'import os; from tradebot.exness.signing import load_private_key; load_private_key(os.environ["BOOT_KEY"])' \
        2>/dev/null || problems+=("ozel anahtar gecerli degil (acik yarisi tohumla eslesmiyor); bastan sona eksiksiz kopyalayin")
    fi
    if [ "${#problems[@]}" -eq 0 ]; then
      write_env "$api_key" "$private_key" "$account_id" "$gateway"
      note "Kaydedildi: hesap $account_id, gateway $gateway, API anahtari ${#api_key} karakter, ozel anahtar ${#private_key} karakter."
      return 0
    fi
    printf '\n' >&2
    for problem in "${problems[@]}"; do printf '  ! %s\n' "$problem" >&2; done
    [ "$attempt" -lt 3 ] && note "Lutfen yeniden girin."
  done
  die "Exness degerleri uc denemede dogrulanamadi. Betigi yeniden calistirabilirsiniz."
}

write_env() {  # degerler tek tirnak icinde yazilir: hem systemd hem kabuk guvenle okur
  local tmp ap_host
  ap_host="$(current_value EXNESS_AP_HOST)"
  install -d -m 750 "$(dirname "$ENV_FILE")"
  tmp="$(mktemp "$(dirname "$ENV_FILE")/.tradebot.env.XXXXXX")"
  chmod 600 "$tmp"
  {
    printf '# Trade Bot sirlari. Bu dosya yalnizca sunucuda durur; kimseyle paylasmayin.\n'
    printf "EXNESS_API_KEY='%s'\n" "$1"
    printf "EXNESS_PRIVATE_KEY='%s'\n" "$2"
    printf "EXNESS_ACCOUNT_ID='%s'\n" "$3"
    printf "EXNESS_GATEWAY_HOST='%s'\n" "$4"
    if [ -n "$ap_host" ] && valid_shape "$ap_host"; then printf "EXNESS_AP_HOST='%s'\n" "$ap_host"; fi
  } >"$tmp"
  if [ "$DRY" != 1 ]; then
    chown tradebot:tradebot "$tmp"
    chown root:tradebot "$(dirname "$ENV_FILE")"
  fi
  mv -f "$tmp" "$ENV_FILE"
}

make_deploy_key() {
  say "Dagitim SSH anahtari"
  local ssh_dir="$DEPLOY_HOME/.ssh" key="$DEPLOY_HOME/.ssh/github_deploy"
  if [ "$DRY" = 1 ]; then
    install -d -m 700 "$ssh_dir"
    [ -f "$key" ] || ssh-keygen -q -t ed25519 -N "" -C github-deploy -f "$key"
  else
    sudo -u "$DEPLOY_USER" install -d -m 700 "$ssh_dir"
    [ -f "$key" ] || sudo -u "$DEPLOY_USER" ssh-keygen -q -t ed25519 -N "" -C github-deploy -f "$key"
    sudo -u "$DEPLOY_USER" touch "$ssh_dir/authorized_keys"
    chmod 600 "$ssh_dir/authorized_keys"
  fi
  touch "$ssh_dir/authorized_keys"
  grep -qxF "$(cat "$key.pub")" "$ssh_dir/authorized_keys" || cat "$key.pub" >>"$ssh_dir/authorized_keys"
  note "Hazir: $key"
}

public_ip() {
  local ip=""
  ip="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i < NF; i++) if ($i == "src") print $(i + 1)}' | head -n 1)" || true
  [ -n "$ip" ] || ip="$(hostname -I 2>/dev/null | awk '{print $1}')" || true
  printf '%s' "${VPS_IP:-$ip}"
}

ssh_port() {
  local port=""
  port="$(sshd -T 2>/dev/null | awk '$1 == "port" {print $2; exit}')" || true
  printf '%s' "${port:-22}"
}

show_secrets() {
  local ip port key="$DEPLOY_HOME/.ssh/github_deploy" host
  ip="$(public_ip)"; port="$(ssh_port)"
  host="$ip"; [ "$port" = 22 ] || host="[$ip]:$port"
  say "GitHub Secrets"
  note "GitHub'da: repo > Settings > Secrets and variables > Actions > New repository secret"
  note "Asagidaki her 'Ad' icin bir secret olusturun ve 'Deger'i aynen yapistirin."
  printf '\n  Ad:    VPS_HOST\n  Deger: %s\n' "$ip"
  printf '\n  Ad:    VPS_USER\n  Deger: %s\n' "$DEPLOY_USER"
  if [ "$port" != 22 ]; then printf '\n  Ad:    VPS_PORT\n  Deger: %s\n' "$port"; fi
  printf '\n  Ad:    VPS_KNOWN_HOSTS\n  Deger (asagidaki satirlarin TAMAMI):\n'
  printf -- '--------------------------- kopyalamaya buradan baslayin ---------------------------\n'
  local pub
  for pub in "$SSH_HOST_KEYS"/ssh_host_*_key.pub; do
    [ -r "$pub" ] && printf '%s %s\n' "$host" "$(cut -d' ' -f1,2 "$pub")"
  done
  printf -- '--------------------------------- buraya kadar ---------------------------------\n'
  printf '\n  Ad:    VPS_SSH_KEY\n  Deger: asagidaki OZEL ANAHTAR blogunun tamami (BEGIN ve END satirlari dahil).\n'
  printf '\n################ OZEL ANAHTAR — yalnizca GitHub Secret olarak yapistirin ################\n'
  cat "$key"
  printf '########################################################################################\n'
  note "Bu anahtari sohbete, e-postaya ya da baska bir yere yapistirmayin."
  note "GitHub'a ekledikten sonra sunucudaki kopyayi silebilirsiniz:  rm $key"
}

setup_https() {
  say "Telefon erisimi (HTTPS)"
  if [ "$DRY" = 1 ]; then note "(test modu: atlandi)"; return 0; fi
  local url=""
  if url="$(bash "$APP_DIR/trade-bot/deploy/setup-https.sh" 2>&1 | tail -n 1)" && [[ "$url" == https://* ]]; then
    PUBLIC_URL="$url"
    note "Uygulama adresi: $PUBLIC_URL"
    note "Sertifika ilk baglantida kendiliginden alinir (bir iki dakika surebilir)."
  else
    note "UYARI: HTTPS kurulamadi: $url"
    note "Sonra yeniden denemek icin:  bash $APP_DIR/trade-bot/deploy/setup-https.sh"
  fi
}

start_service() {
  say "Servis"
  if [ "$DRY" = 1 ]; then note "(test modu: atlandi)"; return 0; fi
  systemctl restart tradebot
  sleep 5
  if systemctl is-active --quiet tradebot; then
    note "tradebot calisiyor (dry-run: gercek emir gondermez)."
  else
    note "UYARI: servis baslamadi. Ayrinti icin:  journalctl -u tradebot -n 40 --no-pager"
  fi
}

run_discovery() {
  say "API kesfi (salt okuma; emir gondermez, yaklasik 1 dakika)"
  if [ "$DRY" = 1 ]; then note "(test modu: atlandi)"; return 0; fi
  local log status=0 archive=""
  # Kesif ve servis ayni anda calismasin: WebSocket baglanti siniri ve istek kotasi ortaktir.
  systemctl stop tradebot 2>/dev/null || true
  log="$(mktemp)"
  # shellcheck disable=SC2024  # log dosyasini bilerek root yazar; yalnizca komut tradebot olarak calisir
  sudo -u tradebot bash -c "set -a; . '$ENV_FILE'; set +a; cd '$APP_DIR/trade-bot' && '$VENV_PY' -m tradebot.discover" >"$log" 2>&1 || status=$?
  grep -E '^(Kesif tamam|Enstruman|  ! |Ayar hatasi)' "$log" | sed 's/^/    /' || true
  archive="$(sed -n 's/^Zip: //p' "$log" | tail -n 1)"
  rm -f "$log"
  if [ -n "$archive" ] && [ -f "$archive" ]; then
    install -m 600 "$archive" /root/tradebot-kesif.zip
    note "Kesif dosyasi: /root/tradebot-kesif.zip"
    note "Kendi bilgisayarinizda (sunucuda degil) su komutla indirip sohbete ekleyin:"
    printf '\n      scp -P %s root@%s:/root/tradebot-kesif.zip .\n\n' "$(ssh_port)" "$(public_ip)"
    note "Dosyada API anahtari ya da imza yoktur; hesap numarasi ve bakiye vardir."
  else
    note "UYARI: kesif tamamlanamadi (kod $status). Yukaridaki '!' satirlarini sohbete yazin."
  fi
}

main() {
  [ "$DRY" = 1 ] || [ "$(id -u)" -eq 0 ] || die "Bu betik root olarak calistirilmali."
  [ -r "$TTY" ] || die "Terminal bulunamadi. Komutu dogrudan sunucu terminaline yapistirin."
  exec 3<"$TTY"  # girisler her zaman terminalden okunur (betik boruyla gelse bile)
  if [ "$DRY" != 1 ]; then
    say "Kurulum (birkac dakika surebilir)"
    local installer
    installer="$(mktemp)"
    curl -fsSL "$RAW_BASE/install.sh" -o "$installer" || die "install.sh indirilemedi ($RAW_BASE)."
    DEPLOY_USER="$DEPLOY_USER" bash "$installer"
    rm -f "$installer"
  fi
  collect_exness
  make_deploy_key
  setup_https
  show_secrets
  run_discovery
  start_service
  say "Bitti"
  note "1) Yukaridaki dort secret'i GitHub'a ekleyin."
  note "2) /root/tradebot-kesif.zip dosyasini indirip sohbete ekleyin."
  if [ -n "$PUBLIC_URL" ]; then
    note "Telefon uygulamasi icin sunucu adresi: $PUBLIC_URL"
    note "Eslestirme kodu uretmek icin (uygulama kurulunca):  tradebot-pair"
  fi
  if [ -f /var/run/reboot-required ]; then
    note "3) Bekleyen bir sistem (cekirdek) guncellemesi var. Uygun oldugunuzda yeniden baslatin:  reboot"
    note "   Bot yeniden baslatmadan sonra kendiliginden calisir."
  fi
}

main "$@"
