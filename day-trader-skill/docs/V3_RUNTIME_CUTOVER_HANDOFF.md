# Ana V3 sonrası ayrı runtime cutover

11 Kasım 2026. Yerel kaynak promotion tamamlandı; canlı restart yapılmadı ve bu görev böyle yetki kullanmaz. Ayrıntılı önceki plan `V3_RUNTIME_CUTOVER_READINESS.md`; bu belge main promotion sonrası exact operasyon bağını verir.

## Sabit kaynak ve ortam

Test edilmiş backend release SHA: `93c3382d20540ee40653c43176fac2974eedbb76`. Ana dal bunu içerir; sonraki promotion belge commit'i üretim kodunu değiştirmez. Production source fingerprint `8ae5f726d7fae3dd8311c9d0a0c53a49a187ccc33831305fdf1c18ae296ea99a`. Bu disk fingerprint'idir; loaded-code attestation değildir.

Ayrı Python 3.11.9 venv gerekir; mevcut test venv'i `%USERPROFILE%\trade-ai-v3-v2-p1\.venv\Scripts\python.exe` ile doğrulandı, canlıya bu paylaşılan test ortamı taşınmamalı. Ayrı deployment venv'e requirements-test-py311.txt pinleri/NumPy 2.2.6 ve gerekiyorsa bağımsız doğrulanmış MT5 bağımlılığı hazırlanır. Global Python/NumPy downgrade yapılmaz. Immutable release için yukarıdaki exact SHA git archive ile yeni klasöre çıkarılabilir; eski klasör/env korunur.

## Operasyon sırası

1. Mevcut 8006 PID/start/executable/parent kimliğini yeniden doğrula; şu an 7532, global Python311, start 15:30:28. Mevcut tam private launch config'i operatör güvenli saklar; raw env/credential/account numarası public rapora konmaz. Sadece sanitize özet rollback komutu sayılmaz.
2. Aday sürece explicit REAL_READONLY_DATA, exact Exness-MT5Real50 / USC ve XAUUSDc/EURUSDc/GBPUSDc/USDJPYc mapping sağla. MT5_SPREAD_POLICY_FILE için dört onaysız/null template korunabilir: güvenli BLOCK beklenir. Onaysız değer, geçmiş spread gözlemi veya eski MT5_MAX_SPREAD approval yerine geçmez. V2 source commit/chart SHA ve candlestick pin korunur.
3. Boşluğu doğrulanmış ayrı localhost portunda production `forex.api:app` başlat. Örnek: `<deployment-venv>\Scripts\python.exe -m uvicorn forex.api:app --app-dir <immutable-release> --host 127.0.0.1 --port 18006`. Reload/fixture wrapper kullanılmaz. Bu görevde bu canlı aday başlatılmadı; yalnız terminal erişimsiz HTTP fixture çalıştırıldı.
4. Aynı fresh interpreter startup'ında exact release SHA, Python/NumPy, safe PID/start ve local loaded_fingerprint kaydet. forex.api/broker_contract/spread_policy importlarından sonra bu fingerprint üretilebilir. Başka interpreterın hash'i çalışan sürece mal edilmez; public tanılama endpoint'i açılmaz. Code-object hash'i globals/C extensions/config veya sonradan yüklenen kodun tümünü ispatlamaz.
5. Exact account identity preflight önce/sonra; gerçek balance sermaye yapılmaz. Health, dört symbols, V1/V5 schema, manuel POST, broker_contract/spread_status alanları, execution false; source mismatch ve onaysız policy retleri ayrı fixture/adaya uygulanır. XAUUSDc tarihsel kanıt eksikken INSUFFICIENT_DATA/BLOCK beklenen sonuçtur; BUY/SELL zorunlu değildir.
6. Bu kontroller ve ayrı operasyon onayı sonrasında yalnız 8006 kontrollü değiştirilir. 8005/5173/8007 kimliği ve süreçleri korunur. /engine proxy aynı localhost 8006 hedefini tutar; local ve Tailscale HTTPS schema/manual POST kabul edilir. 8005 chart ile 8006 analysis source/alias/as-of tutarlılığı ayrıca kontrol edilir.
7. Yeni 8006 başarısızsa yalnız yeni başlatılan süreç kimliğiyle kapatılır; önce saklanan eski immutable source/env/private launch config ile eski servis geri alınır. Destructive reset, global paket değişimi veya başka servis restartı yok. Git recovery ref kaynak kurtarmadır; canlı süreci tek başına geri kurmaz.

## Açık üç engel

- Dört maximum spread limiti operatörce onaylanmadı; max_allowed_price null / UNAPPROVED / BLOCK korunur.
- Exact XAUUSDc / Exness-MT5Real50 / 9 Kasım 2026 tarihsel UTC quote/trade/DST/holiday kanıtı yok. Güncel haftalık MQL5 veya genel XAUUSD çizelgesi yeterli değildir.
- Canlı yeni 8006 deployment ve PWA kabulü ayrı yetkili operasyon ve kanıt gerektirir.

Bu engelleri source promotion başarısı çözmüş saymaz. Kullanıcının minimum dış girdisi spread kuralları ve tarihsel kanıttır; güvenli ret veren sürüme geçiş için dahi ayrı runtime operasyon yetkisi gerekir.

Son eşzamanlı olay: 16:54:50 İstanbul gözleminde 8005 PID 2840 yerine 9880 (listen 16:54:34) oldu; aynı manuel PowerShell parent 12164. Bu görev bridge'i yönetmedi. Bir sonraki operasyonda eski PID sabit kabul edilmemeli; 8005/8006 kaynak/account guard uyumu read-only olarak tekrar doğrulanmalı. 8006 PID 7532 ve diğer süreçler bu gözlemde değişmedi.
