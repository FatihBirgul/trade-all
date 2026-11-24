# Pinli V2 chart pattern doğrulaması

## Güven sınırı

Adaptör `V2_CHART_GIT_ROOT` ile seçilen `trade-ai-v2-antigravity` Git kökünü gerçek yola çözer. Yalnız `c80c97f227a2c233a610df669919ba2f464e4f9f:backend/market_ai/engines/chart_patterns.py` blob'unu `git show` ile okur; beklenen SHA-256 `af69112c91938c4bd6fea3d16f43a333f63c35ea3715ed082069868e1018f1ba`. Çalışma ağacındaki kirli kaynak dosya okunmaz. İzinli importlar `__future__`, `typing`, `numpy`; NumPy 2.2.6 şarttır. Kaynak kodun kendisi SHA ile pinlenmiştir; NumPy için sürüm pini vardır, wheel byte hash'i veya ayrı tedarik zinciri denetimi yapılmadı.

Kaynak `_detect()` 40'tan az mumda boş liste üretir. V5 `capture` 200–256 kapanmış, kimliği ve seansı doğrulanmış mumu sağlar. Adaptör ayrıca 40–256 aralığını, `is_final`, ortak karar cutoff'unu ve sonuç boyutunu kontrol eder. Kaynak `detect()` içindeki geniş exception yakalaması kullanılmaz. Git okumasında 5 saniye süreç sınırı; çıktı için 65 KiB sınırı; formasyon listesinde 6 öğe sınırı vardır. Algoritma çalışması için ayrıca süreç sonlandırma sınırı yoktur; 220 mum fixture'ında 2 saniye kabul testi geçer. Bu sınır üretim ortamı için mutlak gecikme garantisi değildir.

## Bilgi zamanı ve durum

Şimdilik yalnız `Double Top` ve `Double Bottom` döndürülür. Formasyonun ikinci pivotu 212. muma denk geldiğinde kaynak sağdaki üç mumu ister; ilk bilinebilir an 215. mumun kapanışıdır. Adaptör tüm 40..N önekleri yeniden çalıştırıp `first_known_utc` ve `confirmation_utc` belirler. `formed_at_utc` geometrik pivot kapanışıdır, bilgi zamanı değildir. 40. mumda ilk kez görülen sonuç `LEFT_CENSORED` işaretlenir ve mutlak ilk bilgi zamanı iddia edilmez.

20 mumdan eski çıktı `EXPIRED` etiketlenir. Kaynak açık invalidation modeli vermediğinden `invalidation_state=NOT_MODELED` kullanılır; geçersizleşen örnekte kaynak artık formasyonu döndürmez. `STRUCTURAL_CONFIRMED` yalnız pivotun sağ mumlarla geometrik teyididir; broker yönü, fiyat hedefi veya işlem onayı değildir. Kaynak breakout `confirmed` mantığı ve range self-reference nedeniyle aktarılmaz.

Her öğede kaynak SHA, Git commit, sembol/broker sembolü, provider, TF, yön etiketi, formasyon ID, oluşum/ilk bilgi/teyit zamanı, yaş, durum ve `DESCRIPTIVE_ONLY` bulunur. Formasyon ID, pinli kaynak + market kimliği + pivot kapanışı ile belirlenir. İlgili testler çift tepe/dip pozitif fixture, bir mum öncesi negatif önek, M15/H1/H4, yaş aşımı, son fiyat kırılması, farklı kaynak, eksik/gelecek mum ve seans kapısını kapsar. Diğer chart aileleri ayrı family oracle'ları tamamlanana kadar gizlidir.

## Sınırlamalar

Fixture'lar sentetiktir; XAUUSD/XAUUSDc gerçek piyasa başarısı veya tahmin gücü ölçülmedi. Kaynak heuristiği yüzde 2 pivot yakınlığı kullanır; spread, pip/point ve rejim farklılıkları kalibrasyon gerektirir. Formasyonlar confluence oyu, strategy candidate, Entry, SL, TP veya lot hesabı üretmez.
