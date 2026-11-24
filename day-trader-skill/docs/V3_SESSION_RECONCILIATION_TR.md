# 9 Kasım XAUUSDc mum ve tick uzlaştırması

İletilen gözlemler UTC: son M1 açılışı 21:57, sonraki M1 açılışı 23:00; ilk tick 23:00:30.141, 23:01 ilk tick 23:01:00.199, 23:02 ilk tick 23:02:00.115; M15 açılışı 23:00. M1 açılışları arasında 63 dakika vardır. Gözlenmeyen M1 bucket'ları 21:58–22:59 (62 adet), M15 bucket'ları 22:00, 22:15, 22:30, 22:45'tir. 21:45 M15 bucket'ı 21:57 M1'i içerir; seans 21:58'de kapanmışsa kısmi piyasa seansı barı olabilir. Bu koşul XAUUSDc için kanıtlanmış broker saati sayılmaz.

23:00 M15 bucket'ı `[23:00,23:15)` aralığıdır. 23:00:30.141 ilk tick'i bu bucket'tadır; bar open ile first tick'in aynı saniyede olması gerekmez. M15 barı 23:15 öncesinde analize kapalıdır. Birkaç saniye tick olmaması quote seansının kapalı olduğunu, bir tick olması bütün beklenen mumların tam olduğunu kanıtlamaz.

`forex.contracts._bars()` boşluğu yalnız quote saatleriyle bütünüyle kapalıysa kabul eder. Boşluktan sonraki barın başlangıcı quote açılışından önce olabilir; bucket içinde doğrulanmış quote penceresi ve **pozitif tick volume taşıyan gerçek provider mumu** varsa kabul edilir. Trade penceresi ayrı kalır; quote açıkken yeni pozisyon kapalı olabilir. Mevcut `MT5Provider` REAL modda doğrulanmış tarihsel `quote_hours` sağlamaz, dolayısıyla bu mantık 9 Kasım XAUUSDc boşluğunu bugün açmaz.

Exness'in [3 Kasım DST duyurusu](https://get.exness.help/hc/en-us/articles/31342732737180-Trading-Hours-Update-End-of-US-Daylight-Saving-Time-01-Nov-2026) XAUUSD için 21:58–23:00:30 kapalı ve 23:00:30–23:02 close-only gösterir. XAUUSDc açıkça listelenmediğinden bu çizelge ona uygulanmadı. Mevcut tick kayıtları bu çizelgeyle uyumlu görünebilir; uyum, sembol-spesifik resmî kanıt değildir. Güncel haftalık MQL5 çıktısı da tarihsel tatil/DST ve close-only durumunu çözmez.
