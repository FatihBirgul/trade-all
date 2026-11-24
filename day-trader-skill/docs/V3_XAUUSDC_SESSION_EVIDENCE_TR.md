# XAUUSDc seans kanıtı ve manuel analiz güvenliği

10 Kasım 2026. Branch: `codex/v3-real-readonly-analysis`. Başlangıç: `a065f09`, temiz çalışma ağacı. Başlangıç testleri: 458 başarılı.

## Gözlenen zamanlar ve çıkarım sınırı

9 Kasım 2026 için iletilen XAUUSDc kayıtlarında son M1 mumunun açılışı 21:57 UTC, sonraki M1 mumunun açılışı 23:00 UTC'dir. Mum açılışları arasında 63 dakika, son M1 mumunun nominal 21:58 kapanışı ile sonraki açılış arasında 62 dakika vardır. Tick zamanları 23:00:30.141, 23:01:00.199 ve 23:02:00.115 UTC'dir. 23:00 başlangıçlı M15 mumu bu tick'lerin hiçbirinde kapanmış değildir; 23:15'e kadar analiz mumu olarak kullanılamaz. Bu zamanlar regresyon sabiti olarak kullanıldı; bu turda terminalden yeni kayıt alınmadı.

Bu gözlemler 21:58–23:00 aralığının tamamının broker tarafından kapalı olduğunu, haftalık/tatil/DST takvimini veya yeni pozisyon iznini tek başına kanıtlamaz. XAUUSD için belirtilen 23:00:30–23:02 `CLOSE_ONLY` dönemi XAUUSDc'ye taşınmadı. XAUUSDc'nin o anda gerçek `trade_mode` değeri için zaman damgalı bağımsız kanıt yoktur.

## Kod davranışı

`MT5Provider.metadata()` saat beyanını yalnız tam MT5 `broker_symbol` eşleşirse bağlar; `XAUUSD` beyanı `XAUUSDc` için kullanılamaz. REAL salt-okunur modda bu beyan doğru sembole ait olsa da `broker_hours` olarak yayımlanmaz: kaynak yalnız operatör yapılandırmasıdır ve gerçek seans bağımsız olarak doğrulanmamıştır. Bu durumda eksik M15 mumu `forex.contracts._bars()` tarafından reddedilir. DEMO/fixture politikasındaki tam sembol eşlemesi ve mevcut kapalı aralık denetimi korunur.

Quote erişimi ile yeni pozisyon uygunluğu ayrıdır. Sentetik `trade_mode=3` (`CLOSE_ONLY`) durumunda üç gözlenen tick zamanı taze quote olarak okunabilirken `allowed_directions=[]`, `trade_allowed=False` ve seans durumu `DISABLED` kalır. Bu sentetik test gerçek XAUUSDc'nin `CLOSE_ONLY` olduğunu ileri sürmez. REAL modda işlem yürütme izni yine yoktur; emir fonksiyonu eklenmedi veya çağrılmadı.

## Testler ve kalan doğrulama

`tests/test_xauusdc_session_evidence.py` dört test ekler: M1/M15/tick zaman çizelgesi ve doğrulanmamış boşluk reddi; 23:00 M15 mumunun tick anlarında tamamlanmamış olması; broker sembolü kimliği ile REAL saat beyanının reddi; sentetik `CLOSE_ONLY` sırasında quote ve yeni pozisyon izninin ayrılması. M1, V3'ün desteklenen analiz zaman dilimleri arasında değildir; M1 kayıtları yalnız gözlem zaman çizelgesi için kullanıldı.

Tam yerel paket: 462 test, 0 hata/başarısız/atlanan. `compileall` ve `git diff --check` temiz. Gerçek XAUUSDc broker takvimi, gerçek `trade_mode` zaman geçmişi, holiday/DST ve 23:00:30–23:02 döneminin uygulanabilirliği doğrulanmadı. Bunlar doğrulanana kadar REAL eksik mumlar kabul edilmez ve bu verilerle BUY/SELL planı verilmez. Sonraki güvenli adım, hesap gizliliğini koruyan salt-okunur broker seans kanıtını broker sembolü ve sunucu kimliğiyle eşleştirip sürümlü bir doğrulama sözleşmesi oluşturmaktır.
