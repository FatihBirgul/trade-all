# Historical main sonrası runtime teslimi

11 Kasım 2026. Source SHA `24df2ed6a6c94b8eea8548ec8980ba897057e0b5`
yerel fast-forward ile main'e alındı. Ana başlangıç SHA
`3c8adb810058b4738640f46bde84de8ec12205ad`; recovery ref
`refs/recovery/historical-main-20261111-39c4c1b98405`.
Son docs commit'i üretim Python kodunu değiştirmez.

## Gözlenen canlı durum

8006 listener PID 8284, global Python311 executable; V5Runtime/Scripts/python.exe
launcher PID 11380, manuel PowerShell parent 7028. Cwd ana V3; bu nedenle disk
source promotion'un runtime'a etkisi özellikle incelendi. Reload CLI/env,
watcher child veya ilgili supervisor/service/task bulunmadı. PWA Vite izleyicisi
ayrı frontend root'tadır; /engine yalnız 8006 HTTP proxy'sidir.

Canlı `/openapi.json` promotion öncesinde ve sonrasında version 0.2.0 döndürür;
UnifiedAnalysis içinde historical_session_evidence alanı yoktur. Başka interpreter
ile hesaplanan disk fingerprint'i çalışan kodun sürüm ispatı değildir.
Runtime sürümü **UNVERIFIED**; yeni modülün kullanıldığı varsayılmaz.
Yeni live analysis çağrısı veya MT5 account/quote/candle erişimi bu görevde
yapılmadı. Canlı BUY/SELL değişimi veya terminal veri kalitesi kabulü iddia edilmez.

8005 bridge schema title `Trade AI MT5 Veri Sunucusu`, version 0.1.0;
listener 9880. 5173/8007 listener'ları 10320/12152. Süreçler korunur; yalnız
QA'nın farklı ephemeral portlarında kendi fixture process/listener'ları yönetildi.

## Sonraki ayrı yetkili operasyon

1. O anki process kimliğini, immutable source/config ve rollback koşullarını tekrar kaydet.
2. Test edilmiş release SHA'sını ayrı dizin ve ayrı deployment venv'e hazırla;
   global Python/NumPy'yi değiştirme. NumPy 2.2.6 ve pinned V2 bağımlılıklarını doğrula.
3. Gerçek evidence hâlâ yokken production review listesi boş kalır. Spread
   limitleri onaysız/null ise BLOCK korunur. MT5_HISTORICAL_EVIDENCE_ROOT/FILES
   yalnız file selection'dır; onay mekanizması değildir.
4. Ayrı izinle reload'suz, farklı localhost portunda candidate başlat; aynı process'te
   loaded-code/source/config attestation, REAL_READONLY_DATA, exact server/USC ve
   alias doğrula. execution_permission=false ve beklenen güvenli retleri test et.
5. Ayrı runtime yetkisiyle kontrollü cutover yap; 8005/PWA/news süreçlerini koru.
   Source recovery ref canlı süreci geri kurmaz; process rollback ayrıca planlanır.

## Gerçek Exness belgesi

Exness-MT5Real50 / Standard Cent / USC için exact XAUUSDc ve EURUSDc,
6-11 Kasım 2026 günleri, source timezone ve dated UTC offset, quote açık/kapalı,
ayrı trade, close-only, bakım, weekend, holiday ve exceptional kapsam gerekir.
Genel XAUUSD/EURUSD veya current-weekly export yeterli değildir.
Original belge + bağımsız kaynak kimliği + hash + operator review tamamlanınca
SourceReview ayrı code review ile eklenir; scoped reconciliation ve regresyon
tekrarlanır. Hazır destek mesajı/tek komut:
V3_EXNESS_EVIDENCE_OPERATOR_HANDOFF_TR.md.
