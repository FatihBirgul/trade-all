# Sonraki güvenli geliştirme adımları

## P1 izole worktree notu (2026-11-10)

1. `codex/v3-v2-p1-descriptive-analysis` dalındaki pinli çift tepe/dip betimleyici adaptörü ana V3'e aktarılmadan önce V2 checkout konumu, NumPy 2.2.6 dağıtımı ve gerçek servis yapılandırması bağımsız doğrulanmalı. Ana dala otomatik aktarım yapılmadı.
2. V2 head-and-shoulders, üçgen, wedge, channel ve rectangle aileleri için ayrı pozitif/negatif/prefix fixture'ları ve broker sembolü fiyat ölçeği örnekleri hazırlanmalı. `Breakout/Breakdown` pinli kaynakta aralığa mevcut mumu kattığı için bu sürümden alınmamalı.
3. V2 market structure, destek/direnç, ADX/Donchian/Bollinger bağlamı için V5 karşılığıyla tekrar kontrolü ve bağımsız sayısal oracle tamamlanmadan ek alan açılmamalı. Gerçek hacim, order book ve V2 strateji router'ı kapsam dışında kalır.
4. Gerçek XAUUSDc broker seans kanıtı ve tarihsel mum boşluğu doğrulaması P0 kapısıdır. P1 bunu gevşetmez. Üretim benzeri manuel demo kabulü için önce yetkili, lisanslı veri ve doğrulanmış broker takvimi gerekir.

## Önceki plan

1. Windows MT5 demo terminalinde yalnız salt-okunur tanı yap: sembol eşlemesi, quote/candle kaynağı, broker saatleri, kontrat/tick/lot/hesap para birimi ve `order_calc_profit` işareti. Gerçek veya demo emir açma.
2. XAUUSD ve döviz çiftleri için yetkili, lisanslı geçmiş veri ile broker tatil/DST ve CFD/spot kimliğini doğrula. Seans boşluğu kapısını takvim kanıtı olmadan gevşetme.
3. V2'den tek bir betimleyici yöntemi ancak açık algoritma sürümü, bağımsız Forex referans fixture'ı, first-known/as-of testi ve mevcut V3 göstergesiyle çakışmama kanıtı varsa özel read-only extension üzerinden dene. İlk aday ADX/DMI rejim bağlamı olabilir; yön oyu veya emir izni verilmemeli.
4. Pattern, FVG, destek/direnç ve retest/fakeout için aile bazında pozitif/negatif, bilgi zamanı ve invalidation fixture'ları tamamlanınca ayrı küçük kararlar al. Kullanıcının V2 `chart_patterns.py` değişikliğini ve takip edilmeyen testlerini koru.
5. V2 çevrimdışı runner import-root uyumsuzluğunu V2 sahibinin ayrı çalışma alanında ele al. Bu V3 dalından V2 dosyası değiştirme.
6. Forex maliyetli out-of-sample araştırma ve veri kaynağı lisansı olmadan özel strateji uygunluğunu veya kârlılık iddiasını yükseltme. PWA, MT5 arayüzü, bildirim, otomatik tarama ve emir yürütme bu iş kapsamı dışında kalır.
