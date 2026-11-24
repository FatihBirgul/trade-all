# 8008 korunarak PWA-only operasyon planı

Durum BLOCKED_BACKEND_RUNTIME; bu belge canlı yetki değildir. Eski 8006 restart
planları bu paket için geçerli değildir. 8006/8008/5173/bridge/news/Tailscale
ayarlarına bu hazırlıkta dokunulmaz.

1. 8008 rolü ve proxy8008 doğrulandı; exact loaded version için same-process
   güvenilir startup/code attestation eksiktir. Disk/public content digest
   buna çevrilemez. Önce bu kanıt ayrı yetkili çalışma hattından sağlanmalı.
2. Kanıt gelirse PID/start/executable, expected 56cbd7e, environment/source
   bütünlüğü, REAL/USC, null plan/lot, missing historical ve spread BLOCK tekrar
   kontrol edilir. Geçerli schema tek başına source version kabulü değildir.
3. Original PWA fresh envanteri/hash'leri ve 8008 proxy kimliği tekrar doğrulanır.
   Yeni manifest/backup güncel hedefle yeniden mühürlenir. Eski BLOCKED ZIP veya
   deployable=false bayrağı elle değiştirilmez.
4. Sonra yalnız PWA dosya aktarımı/HMR/cache kontrolü, dört-sembol manuel UI smoke
   ve gerektiğinde exact backup rollback için tek yeni kullanıcı onayı istenir.
   Bu onay backend restart, hesap değişimi, spread approval veya emir kapsamaz.
5. Dokuz dosya dışına yazılmaz; NewsPanel ve vite.config.ts kopyalanmaz.
   MarketChart expected hash dışında yazılmaz; drift'te STOP. Backup checksum
   ve restore koşulları doğrulanmadan APPLY yapılmaz. Güncel review aracı yalnız
   dry-run/kanıt paketidir; hazır live APPLY wrapper'ı olarak kullanılmaz.
6. Fiziksel telefonda HTTPS/standalone, dört sembol, hypothetical USC,
   BLOCKED/INSUFFICIENT_DATA, null plan, NOT_EVALUATED, descriptive patterns,
   timeout/cancellation, chart/news ve origin'e özgü SW/cache kontrol edilir.
   API POST cache'den dönmemeli; mobil viewport fiziksel telefon PASS değildir.

Şimdi sadece read-only `tools/runtime8008-preflight.py dry-run` kullanılabilir.
Loaded version kanıtı sağlanmadan sonraki canlı adım yoktur.
