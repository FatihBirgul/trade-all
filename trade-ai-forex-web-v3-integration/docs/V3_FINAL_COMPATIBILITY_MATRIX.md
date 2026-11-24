# Son mühürleme engeli: dış proxy değişikliği

11 Kasım 2026 21:55:25 İstanbul: orijinal PWA vite.config.ts dışarıdan /engine hedefini 8006 -> 8008 değiştirdi. 8008 PID 13988 yeni historical alanlı schema sunuyor; 5173 proxy artık bu schema'yı veriyor. 8006 PID 8284 aynı ve exact loaded sürümü VERSION_UNVERIFIED. Görev bu değişikliği yapmadı veya geri almadı. Son preflight BLOCKED; paket yalnız inceleme içindir (deployable=false). Aşağıdaki 8006 operasyon sırası uygulanamaz: önce yetkili backend/proxy hedefi uzlaştırılmalı, sonra manifest/backup ve uçtan uca kabul yeniden mühürlenmelidir. Yeni canlı operasyon onayı bu aşamada istenmiyor. Önceki başarılı kabul sonuçları test edilmiş adayın kanıtıdır; değişmiş canlı routing kabulü değildir.

# Güncel API / PWA uyumluluk matrisi

Backend `56cbd7e`; UI source RC `34c6ec2`. src/public/package/Vite kodu bu
uzlaştırmada değiştirilmedi. Backend request `forex-analysis-5` şeması korunur;
historical_session_evidence additive response alanıdır.

| Senaryo | Beklenen client/UI davranışı | Kabul kaynağı |
| --- | --- | --- |
| Eski response, historical alan yok | Mevcut guard'lar ve legacy sürüm uyarıları; eksik güven alanı onay sayılmaz | 42 client ve ek gerçek-response parser testi |
| Yeni response, historical alan var | Parser additive alanı tolere eder; server decision_reasons/güvenli ret korunur | Ek parser testi + 14 historical HTTP |
| Dört canonical sembol | Exact broker alias backend'de; client alias uydurmaz, yalnız manuel POST | Client/browser/gerçek aday |
| BUY/SELL/WAIT | Geometri ve mevcut mali/session kapıları; NO_TRADE/INSUFFICIENT_DATA ayrı | 600 backend + 42 client + browser |
| Null Entry/SL/TP/lot | İşlem planı uydurulmaz | Client/browser/gerçek aday |
| USC hypothetical capital | Gerçek bakiye risk sermayesi değildir; NOT_EVALUATED açık varsayımsal bağlam | Client/browser/gerçek aday |
| Double Top/Bottom + candlesticks | DESCRIPTIVE_ONLY; empty/unavailable ve source pin ayrımı | Backend/browser |
| Spread UNAPPROVED | Maksimum null, BLOCK; gözlenen spread limit sayılmaz | Backend/aday/live acceptance gate |
| Quote historical evidence missing | SOURCE_NOT_SUPPLIED, historical_gap_authorized=false; eksik mum ret | 81 historical test ve gerçek aday |
| Weekly/operator/yanlış Cent kapsamı | Geçmiş boşluklara yetki vermez | Historical tests/HTTP |
| CLOSE_ONLY / trade kapalı | Quote-closed diye türetilmez; yeni pozisyon engelli | Historical suite |
| Local/proxy/Tailscale | Same-origin /engine; mevcut proxy config değişmez | Schema GET, browser allowed-host |
| SW/offline | API POST cache'lenmez; yalnız shell/assets | Production preview/cache |

Yeni PWA paneli ayrı historical audit nesnesini özel bir UI kartı olarak çizmez;
mevcut veri reddi/seans güveni ve decision_reasons akışını kullanır. Bu hazırlık
yeni ekran geliştirmez. Geçerli veri otomatik BUY/SELL uygunluğu sağlamaz.

Gerçek 6-11 Kasım XAUUSDc/EURUSDc broker belgesi yoktur; üretim review listesi
boş kalır. Genel XAUUSD/EURUSD saatleri Cent sembollerine aktarılmaz. Aynı anda
çalışan 8006'nın exact loaded sürümü VERSION_UNVERIFIED; yeni release diskiyle
eşit source SHA iddia edilmez.
