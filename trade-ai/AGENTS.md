# Trade AI — Kalıcı Çalışma Kuralları

Bu dosya, Trade AI deposundaki doğrulanmış mimari kararlar ve kalıcı çalışma
kuralları için kaynak kayıttır. Geçici gözlemler veya doğrulanmamış varsayımlar
buraya yazılmaz.

## Kaynak ve Git güvenliği

- Başlangıç doğrulama checkpoint'i `469b27d` (`Redesign trade zone geometry and risk reward`) olmalıdır.
- Çalışmaya başlarken `git status`, `git diff`, kısa git geçmişi ve `docs/` durumunu karşılaştır.
- Kullanıcıya ait değişiklikleri, özellikle takip edilmeyen dosyaları, silme veya yeniden yazma.
- Şu yedekler korunur; değiştirilmez, taşınmaz, silinmez ve commit'e alınmaz:
  - `backend/market_ai/engines/analysis_before_zones_v2.py`
  - `backend/market_ai/engines/analysis_checkpoint_6b73ec2.py`
  - `backend/market_ai/engines/confluence_checkpoint_6b73ec2.py`
- Force push, geçmişi yeniden yazma, `main` rebase ve kullanıcı değişikliklerini silmek için `git reset --hard` yasaktır.
- Her mantıksal milestone küçük, geri alınabilir ve ilgisiz dosyalardan arındırılmış olmalıdır.

## Mimari değişmezler

- Sağlayıcılar normalize edilmiş piyasa verisi üretir; engine'ler sağlayıcıya özgü ağ kodu içermez.
- Deterministik katman yön, skor, güven temeli, karar kapısı, zone ve RR üretir. AI yalnızca açıklama/narrative üretir; deterministik kararı geçersiz kılamaz veya yeni evidence uyduramaz.
- Ağırlıklı directional composite yalnızca `trend`, `momentum`, `volume`, `structure` ve `news` kullanır.
- Pattern, Order Flow, Liquidity, Futures Positioning, Liquidation ve MTF yalnızca Confluence evidence katmanına girer; composite'te yeniden sayılmaz.
- Volatility yönsel evidence değildir; risk ve kalite bağlamıdır.
- Confidence heuristiktir; istatistiksel olarak doğrulanmış olasılık diye sunulmaz ve yapay floor/bonus eklenmez.
- Confluence evidence'ı recency/confirmation ile değerlendirir, bucket bazında tekilleştirir ve tek karar kapısı için destek/çatışma bilgisini sağlar.
- AI, sağlayıcı veya veri kalitesi eksikse uydurma canlı veri üretme. Güvenli unavailable/fallback dön ve durumu kaydet.

## Risk, zone ve veri sözleşmesi

- Zone geometrisi her zaman doğrulanır. Bullish: `invalidation < entry_low <= entry_high < target_1 < target_2`; bearish: `target_2 < target_1 < entry_low <= entry_high < invalidation`.
- Risk ve reward pozitif olmalı; zero/negative risk, yanlış taraflı hedef ve invalidation reddedilir.
- API/UI katmanına `None`, `undefined`, `NaN` veya `Infinity` ile kullanıcıya gösterilecek metin taşınmaz.
- Saklama ve piyasa timestamp'leri UTC temellidir; frontend yalnızca gösterim için yerel zaman dilimine dönüştürür.

## Test ve operasyon güvenliği

- Her değişiklik, etki alanına uygun compile, unit, regression ve güvenli integration/API smoke kontrolleri olmadan başarılı sayılmaz.
- Testler production/persistent veriyi silmemeli veya değiştirmemelidir. Uzak API kullanan mevcut testler çalıştırılmadan önce hedefin izole test ortamı olduğu doğrulanır.
- Dış API kritik değilse provider interface, unavailable fallback ve test double ile geliştirmeye devam et; sahte veriyi canlı veri gibi sunma.
- Milestone akışı: inspect → plan → implement → test → review → state/changelog/decision update → commit → push → doğrulama.
