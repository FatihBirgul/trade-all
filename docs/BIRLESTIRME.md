# 24 Kasım 2026 birleştirme kaydı

GitHub'daki yedi kaynak repo incelendi. Altı repoda toplam 50 dal vardı. 42 ek Git referansının uç commit'leri de kaynak dalların geçmişindeydi. Yedinci repo olan `trade-ai-pwa` boştu. Dal adları ve tam commit kimlikleri [kaynak envanterinde](sources.json) bulunur.

| Kaynak | Alınan sürüm | Birleştirme kararı |
|---|---|---|
| `trade-ai-unified` | `46723e3` | V6 dal adı altında geliştirilmiş V9 sürüm adayı. V6–V8 araştırma ve doğrulama kayıtları ile sabitlenmiş V2/V5 kaynakları birlikte alındı. |
| `trade-ai` | `cb3eaa1` | Sanal işlem bütünlüğü, defter denetimi, olay günlüğü, tarayıcı, bildirimler ve mobil kabul çalışmalarını içeren dal seçildi. Ayrı Bionic dalındaki sabit HTTP yanıt açıklamaları son OpenAPI sözleşmesinin metinleriyle birleştirildi. Windows SQLite kapatma düzeltmesi bu sürümde zaten bulunuyordu. |
| `trade-ai-android` | `4ff3486` | Uygulama sürümü 0.7.7. Önceki Android dalları bu commit'in geçmişinde. |
| `trade-ai-gateway` | `d1c0e4d` | Tarayıcı yetenekleri ve cihaz oturumları dahil son Gateway dalı. |
| `day-trader-skill` | GitHub `fdcdd41`, yerel `56cbd7e` | GitHub sürümünün devamı olan yerel V3/V5 kodu, seans kanıtı içe aktarma, broker kontrolleri ve önceki beceriler alındı. |
| `Trade` | `ac09f6f` | Ayrı geçmişi olan ilk uygulama `legacy/trade` altında saklandı. |
| Yerel dört sembollü PWA | `e9dc135` ve çalışma kopyası | Analiz istemcisi, sözleşme testleri, kontrollü geçiş araçları ve son iki yerel denetimin kodu ve testleri alındı. |

## Bilgisayardaki ek geliştirmeler

- **19 sembollü Forex çalışması.** Yerel `trade-ai-v3-19-symbols` değişiklikleri V5'e uygulandı. MT5 ve haber/takvim köprüleri ile güncel PWA, `trade-ai-forex-web` altında bulunur. Dört sembollü entegrasyon PWA'sı ayrı çalıştırılabilir. Önceki masaüstü web kopyası ve yedekler sürüm karşılaştırmasında kullanıldı.
- **V1 ve V2 analizleri.** Masaüstü V1 kopyasındaki senaryo üretimi ve eksik AI alanlarını tamamlama, V1 sunucusuna taşındı. Yerel Antigravity dalından eksik RSI/nötr MACD kontrolü, kırılım aralığı düzeltmesi, pivot zamanlaması, MTF ve RSI/ATR referans testleri eklendi. V2 backend bağımsız olarak başlatılabilir.
- **Grafik detektörünün kaynak kimliği.** Forex köprüsünün beklediği iki özgün dosya `trade-ai-v2-antigravity` altında tutulur. Grafik köprüsü sabit SHA-256 değerini doğrulamaya devam eder. Böylece güncel V2'deki kırılım düzeltmesi eski detektörün kimliğini değiştirmez.
- **Windows araçları ve devir notları.** Masaüstü ve indirme arşivlerindeki aynı başlatıcı tek kopyaya indirildi. Proje yolları bu klona, analiz portu web vekilinin kullandığı 8008'e uyarlandı. Ayrı GPT bağlantı deneyinin kaynakları, DevKit lisansı ve devir belgeleri korundu.

## Yayın kapsamı

Bu repo çalıştırılabilir kaynak kopyalarını ve kaynak commit kimliklerini içerir. Eski özel Git geçmişleri özgün repolarda durur. Kişisel hesap ve işlem veritabanları, terminal oturumları, şifrelenmiş anahtar depoları, canlı servis günlükleri, bağımlılık klasörleri ve eski APK çıktıları yayın kapsamının dışındadır. Kaynak kodla birlikte gelen sabit test verileri ve örnek ortam dosyaları korunur.

Bileşenlerin altındaki eski teslim belgeleri, sürüm numaraları, yayın arşivleri ve operasyon onayları kendi tarihsel bağlamlarında okunmalıdır. Özellikle PWA geçiş araçları özgün commit ve arşiv özetlerine bağlıdır. Bu deponun oluşturulması canlı süreç değişimi veya broker kabulü gerçekleştirmez.
