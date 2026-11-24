# Trade All

Trade AI'nin Forex, kripto, Android ve web geliştirmeleri bu depoda toplanır. Tek klonla V9 analiz motoruna, önceki V2 ve V5 servislerine, istemcilere ve bunların testlerine erişebilirsiniz. Her bileşen kendi bağımlılıklarını kullanır.

| Başlamak istediğiniz yer | Klasör | İçerik |
|---|---|---|
| Birleşik Forex motoru | [trade-ai-unified](trade-ai-unified/) | V9 sürüm adayı, Forex/XAUUSD analizi, geçmiş veri araştırması, risk ve API sözleşmeleri |
| Forex web uygulaması | [trade-ai-forex-web-v3-integration](trade-ai-forex-web-v3-integration/) | 19 sembol için grafik seçimi, dört sembol için V5 manuel analiz paneli, durum göstergeleri ve tarayıcı testleri |
| Web köprüleri ve önceki arayüz | [trade-ai-forex-web](trade-ai-forex-web/) | MT5 fiyat ve risk köprüsü, haber ve takvim servisi, yerel PWA sürümü |
| Forex V5 ve Day Trader | [day-trader-skill](day-trader-skill/) | PWA'ların kullandığı Forex API'si, broker seansları, veri kontrolleri ve 11 Day Trader becerisi |
| Trade AI V2 | [trade-ai](trade-ai/) | Kripto analizi, tarayıcı ve bildirimler, sanal portföy, olay günlüğü, yeniden oynatma ve araştırma. V1 uyumluluk sunucusu ve Expo arayüzü de burada. |
| Android uygulaması | [trade-ai-android](trade-ai-android/) | Expo / React Native 0.7.7 uygulama sürümü, grafikler, portföy ve cihaz eşleştirme |
| Mobil ağ geçidi | [trade-ai-gateway](trade-ai-gateway/) | Android oturumları, yetkilendirme ve V2 API bağlantısı |
| İlk Trade uygulaması | [legacy/trade](legacy/trade/) | Ayrı `Trade` reposundaki ilk backend ve Expo uygulaması |

## V9'u yerelde açma

Aşağıdaki PowerShell komutları klonun kökünden çalışır. V9, Python 3.11 ile ayrı bir sanal ortama kurulur.

```powershell
cd trade-ai-unified
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m unified_forex
```

API belgeleri [127.0.0.1:8006/docs](http://127.0.0.1:8006/docs) adresinde açılır. V9, sürüm numarasından bağımsız olarak `/api/v6` sözleşmesini kullanır. Piyasa verisi sağlayıcısı ve broker tanımları eksikse ilgili analiz uçları bunu yanıtta bildirir. [V9 kullanım kılavuzu](trade-ai-unified/README.md)

## Uygulamalar nasıl bağlanır?

- 19 sembollü web uygulaması fiyat ve mumlar için MT5 köprüsünü (8005), haber ve takvim için haber köprüsünü (8007), analiz için V5'i (8008) kullanır. 19 sembol teknik gözlem kapsamındadır. V5'in ayrıntılı analiz sözleşmesi XAUUSD, EURUSD, GBPUSD ve USDJPY ile sınırlıdır. [Web kurulumu](trade-ai-forex-web/README.md)
- Dört sembollü PWA aynı V5 servis ailesini kullanır. Bu sürümün manuel analiz sözleşmesi ve kabul testleri kendi klasöründedir. [PWA sözleşmesi](trade-ai-forex-web-v3-integration/docs/V3_PWA_API_CONTRACT.md)
- Android, Gateway üzerinden V2 backend'e bağlanır. Yerel varsayılanlar Gateway için 8787, V2 için 8002'dir. Telefon bağlantısı ve eşleştirme için Gateway kurulumunu izleyin. [Gateway kurulumu](trade-ai-gateway/README.md) · [Android belgeleri](trade-ai-android/README.md)

## Kaynaklar ve doğrulama

[Birleştirme kaydı](docs/BIRLESTIRME.md) kaynak seçimlerini ve yerel eklemeleri açıklar. [Dal ve commit envanteri](docs/sources.json) önceki sürümlerin izini tutar. [GitHub Actions](../../actions) backend, Gateway, Android ve web kontrollerini çalıştırır. Android APK derlemesi Actions içinden ayrıca başlatılabilir.

Özgün lisanslar bileşenlerin yanında korunur. Day Trader kodu MIT lisanslıdır. Bağımsız [GPT bağlantı deneyi](tools/gpt-connection/) kendi DevKit lisansını içerir. Depodaki eski teslim raporlarının tarihler ve kabul sonuçları, ilgili kaynak sürümüne aittir.
