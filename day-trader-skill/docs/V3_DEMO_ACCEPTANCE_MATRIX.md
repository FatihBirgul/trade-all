# Manuel DEMO kabul matrisi

| Kriter | Sonuç | Kanıt/sınır |
|---|---|---|
| V3 kod/test baseline | PASS | 444/444, `55a0b9d` |
| REAL hesapta analiz durması | PASS (fixture), BLOCKED (canlı servis) | API 503 testi; varsayılan terminal salt okunur preflight REAL |
| DEMO account preflight | PASS (fixture), BLOCKED (canlı) | Enum/server/currency/login/balance ve değişim testleri; DEMO yok |
| Dört sembol/USC kontrat | PASS (fixture), UNVERIFIED (DEMO) | Önceki sentetik Exness testleri; DEMO metadata okunmadı |
| Session/UTC/DST/OPENING_SOON | PASS (fixture), UNVERIFIED (DEMO) | Önceki gap testleri; broker çizelgesi arşivi yok |
| V2 pinli candle context | PASS (offline) | Descriptive-only köprü ve hash/first-known testleri |
| Varsayımsal 10.000 bakiyenin ayrılması | PASS (fixture) | V5 MT5 route DEMO broker bakiyesini kullanır |
| BUY/SELL/WAIT ve risk planı | PASS (offline), UNVERIFIED (DEMO) | V3 regresyonları; gerçek terminal analizi yapılmadı |
| PWA dört sembol ve USC görünümü | BLOCKED | Yalnız XAU/EUR etkin; kaynak/birim görünümü yok |
| 8005/8006 aynı DEMO source | UNVERIFIED | Port/OpenAPI gözlemi kaynak kimliğini doğrulamaz |
| Emir yürütmeme | PASS | Mevcut no-order güvenlik testi |

Genel kabul: **BLOCKED**. Gerçek DEMO oturumu ve PWA risk birimi doğrulanmadan kullanılabilir canlı DEMO sürüm ilan edilmez.
