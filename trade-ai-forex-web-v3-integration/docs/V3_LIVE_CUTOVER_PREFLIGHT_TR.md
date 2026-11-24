# Canlı geçiş ön kontrolü — 11 Kasım 2026

Durum: READY_FOR_APPROVAL. Canlı işlem onayı henüz verilmedi. Bu görev 8006/5173 üzerinde canlı yazma, restart veya APPLY yapmadı.

Backend başlangıç/aday SHA 3c8adb810058b4738640f46bde84de8ec12205ad, branch codex/v3-real-readonly-analysis; temiz. PWA başlangıç SHA 91f093eca02eae666cfeaf67cbc7ef45179e2c53, branch codex/pwa-v3-manual-analysis. Yeni araç/belge commit'i yalnız PWA izolasyonundadır; dokuz UI payload dosyası değişmedi. Source version final teslim git log'undadır.

RC ZIP SHA-256 c62f6c8e811246ef61a904f06e7ed8385d0ad9054724c817bb9ee81c09895426; RC manifest SHA-256 1035c98420554d268c32f1a38bd0ed19379c18a67c53d93362edee216105b715. Dokuz source/target hash'i ve 27 guard yeniden doğrulandı, drift yok. BASE 01c96bb, disk CRLF/LF ayrı hash ve canonical kıyas aynı; 19 source/config satırı tekrar karşılaştırıldı. MarketChart'ta izinli tek lazy clock satırı, NewsPanel payload dışı. Yeni araçlar payload değildir.

| Kapı | Son kabul |
|---|---|
| Python3.11/NumPy2.2.6 | 519/519 PASS |
| Python3.13/NumPy2.2.6 | 519/519 PASS |
| Yeni bağımsız runtime venv | 519/519 PASS; pip check PASS |
| Fixture HTTP | 63/63 PASS, iki interpreter |
| Eski canlı PWA source contract | 9/9 PASS; eski iki-sembol/pattern eksikliği bilinen baseline |
| PWA API/client | 42/42 PASS |
| PWA browser | 34/34 PASS |
| PWA production/SW cache | 3/3 PASS |
| RC dry-run güvenliği | 12/12 PASS |
| APPLY/rollback | 18/18 PASS, sahte hedefler |
| Canlı kabul kapısı guard testleri | 12/12 PASS, canlıya bağlanmadan |
| Runtime launcher | 4/4 PASS |
| Yeni gerçek read-only aday | 43/43 PASS; kendi portu kapandı |
| Gerçek read-only UI E2E | Dört manuel POST, dört güvenli ret, emir çağrısı0, taşma yok; kendi portları kapandı |
| Mevcut baseline failback | 14/14 PASS, gerçek V5Runtime2.2.6 ile ayrı portta |
| Tam ESLint/typecheck/build | PASS |
| Source preservation | Orijinal38 / backend234 hash değişikliği0 |
| Ön yedek | 27 dosya hash doğrulaması PASS |

Ön yedek: %USERPROFILE%\trade-ai-forex-web-v3-integration\release\cutover\preapproval-backup-20261111T162555Z-63c7fd2d; backup manifest SHA-256 79e7f8318a199e4ea0a68036372b0153c60e097bc71955026a270e8832571578. Bu yedek ön kontrol kopyasıdır. APPLY anında tekrar tam preflight ve UUID ile yeni backup alınır; eski hashler değişirse BLOCK. .env, node_modules, credential, hesap numarası yedeklenmedi. Backend immutable archive ve güvenli config/V2 pin snapshot'ları release/cutover altında.

## Güncel canlı süreç gerçeği

İlk gözlem 8006 PID7532 idi. Görev sırasında DIŞARIDAN PID15996, 19:13:03 İstanbul başlangıçlı yeni süreç oluştu. Bu görev onu başlatmadı/durdurmadı. Parent8532 gerçek V5Runtime/Scripts/python.exe launcher'ıdır; child executable global Python311 yolu olması ortamın global olduğunu göstermez. Gerçek launch venv'i AppData/Local/TradeAI/V5Runtime, NumPy2.2.6, FastAPI0.162.0, include-system-site-packages=true. Child executable yolundan yapılan ilk global ortam yorumu düzeltildi. Global disk NumPy2.4.6, yeni bağımsız aday2.2.6; global paketler değiştirilmedi.

Yerel8006, /engine proxy ve Tailscale schema SHA f0938f9e11b33e169ea12b55d0ae429fe840f0ff6c2d97184aa1fff9ce7f9c6a: yeni broker/spread alanları artık mevcut. Bu yüzden önceki BACKEND_RUNTIME_OLD etiketi güncel schema için kullanılmaz. Çalışan sürecin exact loaded-code attestation'ı yok; source/loaded sürüm kesinliği halen VERSION_UNVERIFIED. Ayrıca mevcut env'de V2_CHART_GIT_ROOT yok; eski candlestick3ab258… pin var. Yeni aday startup aynı interpreterdan source/config/NumPy/loaded code kimliği kaydeder; candlestick45ee833… ve Git-pinned chart adaptörünü açık ayarlar. Public endpoint eklenmez.

8005 PID9880 health connected;8007 PID12152 /api/news HTTP200;5173 PID10320 orijinal Vite kaynağı / UI HTTP200. Bunlar değişmedi. Parent chain'de reload/watch bayrağı veya bağlı Windows service tespit edilmedi; bu, tüm makinedeki her supervisor'ın yokluğu ispatı değildir. Operasyon öncesi process identity yeniden doğrulanır.

## Hesap ve sınırlamalar

Yeni aday REAL_READONLY_DATA / Exness-MT5Real50 / USC. Dört exact broker alias ve bridge'in digits/point/tick/contract/volume/currency değerleri eşleşti. Account login yalnız RAM'de önce/sonra karşılaştırıldı, kaydedilmedi. Bridge API hesap numarası/server attestation vermez; bridge için birebir hesap ID ispatı iddia edilmez. Veri eşleşmesi ve aynı terminal read-only account gate kanıtıdır.

Dört aday gerçek yanıt INSUFFICIENT_DATA, plan/lot null, execution=false, broker_contract CURRENT_MT5_OBSERVED, spread UNAPPROVED/BLOCK. XAUUSDc historical quote/trade session kanıtı ve dört limit/onay/birim/effective date/provenance eksikleri sürer. Bu güvenli ret kabulüdür, işlem izni veya BUY/SELL başarısı değildir. V2 canlı formasyon listesi snapshot QC nedeniyle unavailable/boş olabilir; fixture descriptive-only/pin kabulü ayrı geçti.

Fiziksel telefon/standalone kabulü NOT_RUN. Tailscale HTTPS GET200 ve host/proxy browser kabulü PASS; gerçek cihazdan manuel kabul henüz yapılmadı. SW eski kabuk riski sürer; RC preview SW/controller/cache ve offline POST reddi geçti.

İlk parallel browser koşusu yoğun yükte page.goto20s timeout aldı (33/34); kaynak/test silinmeden seri tekrar34/34 geçti. Runtime unittest ilk komutunda importable olmayan tests için -t kullanımı hata verdi; repo cwd'de doğru discover ile519 geçti. Failback ilk global reference denemesi gerçek launch ortamı sayılmadı; parent venv tespit edilip doğru2.2.6 ortamında14/14 tekrarlandı. Geçersiz referans/başarısız loglar saklandı; nihai kanıt olarak kullanılmaz.

Yeni runtime config SHA-256: a5eea178328aa00c85ef650f0d9104deba5e828a89f1689a3e35e41e010054ae. Hassas env/account number loglanmadı. Git push/remote merge/Actions, V2/bridge/news kaynak yazımı, emir veya order_check yapılmadı.
