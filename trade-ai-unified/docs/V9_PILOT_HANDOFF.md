# V9 Windows MT5 pilot — güvenli devir

Gerçek Windows terminali bu ortamda çalıştırılmadı: UNVERIFIED.
Mevcut yerel PWA/MT5/Gateway projesini değiştirmeden bu private depoyu ayrı dizine
alın. V8_WINDOWS_MT5_HANDOFF.md salt-okunur toplama adımları korunur. Aynı V9 kod
checkpoint'ini kullanın; portable SOURCE_SHA256 dört CI ortamında eşleşti.

```powershell
python -m pip install -r requirements-lock.txt
$pilotStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
python scripts/windows_pilot.py | Out-File -Encoding utf8 "mt5-pilot-$pilotStamp.json"
python scripts/validate_pilot.py --root . --file "mt5-pilot-$pilotStamp.json"
python scripts/reconcile_pilot.py --reference expected.json --evidence "mt5-pilot-$pilotStamp.json"
```

MetaTrader5 binding'i Windows'a ayrıca kurulur; terminal bağlantısını kullanıcı
kendisi açar. Kimlik bilgilerini komut/Git/rapora koymayın. Önce validate_pilot
başarılı olmalı; sonra whitelist beklenti alanlarını reconcile ile inceleyin.
Backend'e otomatik metadata/kontrat override veya emir onayı yoktur.

V8 export şeması fx-windows-pilot-v8-1 uyumluluk için korunur. Yeni doğrulayıcı
256KB/nesting32/duplicate-key sınırları, checksum, exact code hash, aware collection
time (en fazla24saat), quote age (en fazla120s), broker/server/symbol/currency,
pozitif tick/grid/contract alanları, profit/margin örnekleri ve kapalı privacy
bayraklarını denetler. Ek kişisel alanları, yanlış hash/clock/source ve geçersiz
profit işaretini reddeder. UTF-8 BOM'lu PowerShell çıktısı desteklenir.

Geçen sonuç VALID_UNTRUSTED_LOCAL_EVIDENCE: yalnız incelemeye uygun yerel beyan.
Checksum broker kaynağını doğrulamaz; real_terminal_validated ve automatic_contract_
override false kalır. Account number/login/password/token/terminal path/kişisel
kimlik whitelist dışında; detaylı exception metni dışarı verilmez. Beklenen/live
farklar insan incelemesi gerektirir; fixture gerçeğe dönüştürülmez.

Gerçek pilot gelince alias, USD/EUR/JPY tick dönüşümü, min lot, stop/freeze,
session/holiday/DST, fee/swap/rollover ve read-only profit/margin örneklerini
karşılaştırın. Margin örneği mevcut pozisyonları içermeyen bir hesap tahminidir;
order_check/order_send veya execution değildir. Çıktı yokken Gate L açılmaz.
