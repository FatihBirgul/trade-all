# Onaylı spread politikası

11 Kasım 2026. Kullanıcı dört sembol için kesin maksimum limit onaylamadığını açıkça belirtti. Hiçbir canlı limit atanmadı veya gözlemden türetilmedi.

## Kök neden ve üç ayrı kavram

Önceki `MT5Provider` yalnız `MT5_MAX_SPREAD` JSON sözlüğündeki canonical sembol anahtarını `.get(symbol)` ile okur. Eşleşen değer yoksa/null ise `max_spread=None`; ask-bid veya MT5 symbol_info.spread bu alanı doldurmaz. Mevcut 8006'da uygulanabilir değer yok. Sürecin özel env içeriği okunup kaydedilmedi; eksikliğin env'in tamamen boşluğu mu yanlış anahtar/null mu olduğu varsayılmadı.

1. OBSERVED_SPREAD: aynı quote'un ask-bid fiyat farkı. Decimal fiyat girdileriyle bağımsız boundary hesabı yapılır. Negatif/sıfır/inverted, eksik ask ve stale/future quote reddedilir.
2. SYMBOL_SPREAD: MT5 metadata'nın point cinsinden bildirdiği anlık değer. Quote ile farklı anda okunabilir; aynı değerde olmak zorunda değildir.
3. MAX_ALLOWED_SPREAD: operatörün belirli broker/sembol/birim/tarih/timeframe için onayladığı risk limiti. Diğer iki değerden otomatik üretilemez.

## Dar konfigürasyon

Yeni ortam değişkeni `MT5_SPREAD_POLICY_FILE`; dosya servisin başlangıcında yüklenir. Mevcut 8006 ortamına uygulanmadı. Şema `forex-spread-policy-1`, policy version `exness-cent-manual-spread-1`. En çok dört benzersiz canonical sembol; exact broker alias/server/USC, maximum, PRICE veya POINTS, UTC effective_from/effective_to, açık timeframe listesi, approval_status ve provenance zorunlu yapıdadır. Pip desteklenmez. Tarih aralığı [from,to), null to süresiz; from onaylı kuralda zorunludur.

Hazır dosya: `docs/examples/exness_cent_spread_policy.unapproved.json`. Dört maximum/from/to null; approval_status UNAPPROVED. Bu geçerli taslak yüklenebilir ama dört sembolde de BLOCK verir. Dosya hiçbir canlı sürece bağlanmadı.

OPERATOR_APPROVED için pozitif finite maximum, başlangıç tarihi ve boş olmayan provenance reference gerekir. Onay yalnız yerel yetkili operatör konfigürasyon beyanıdır; kriptografik imza, broker onayı veya dış kanıt değildir. Dosyayı yazabilen süreç bu beyanı değiştirebilir; deployment dosyasının erişimini operatör kontrol etmelidir. Bu görev onay etiketini otomatik değiştirmez.

JSON 64 KiB ile sınırlı; duplicate/unknown alan, desteklenmeyen sürüm, yanlış birim, broker kimliği, tarih, timeframe ve eksik onay reddedilir. Hatalı dosya generic güvenli hata verir; dosya yolu public hataya çıkmaz. Provenance reference içeriği API'ye taşınmaz, yalnız SHA256 verilir. Env'den seçilen dosya local güven sınırıdır; internetten gelen belge otomatik policy yapılamaz.

REAL modda eski çıplak MT5_MAX_SPREAD değeri operatör onayı yerine geçmez. Legacy fixture/DEMO açık price limitleri geriye uyumluluk için korunur. REAL metadata'daki eski max_spread null kalabilir: timeframe/tarih değerlendirmesi yapılmadan tek scalar onay verilmiyor. Yeni V5 `spread_status.max_allowed_price` bağlama göre çözülmüş limittir; eksik/onaysız kuralda null ve decision BLOCK. Bu null güvenli/amaçlıdır; sıfır/sonsuz varsayımı değildir.

POINTS -> PRICE çarpanı yalnız point/digits tutarlıysa kullanılır. PRICE ve point birimleri sembol bazındadır. Eşit boundary kabul edilir; üstü bloke edilir. V5, risk calculate ve risk policy yolları aynı onaylı limiti uygular; çağrının daha yüksek çıplak max_spread değeri bunu gevşetmez. REAL finansal endpoint'lerde account preflight da zorunludur. Risk calculate isteğine yalnız opsiyonel timeframe eklendi, varsayılan M15; eski istek şekli korunur.

## Gözlemler ve onay bekleyen alanlar

11 Kasım 2026 16:20:32 İstanbul, tek manuel snapshot. Bunlar önerilen veya izin verilen maksimumlar değildir.

| Broker symbol | Bid | Ask | Fiyat farkı | Point sayısı | MT5 symbol spread | Onay |
|---|---:|---:|---:|---:|---:|---|
| XAUUSDc | 4042.560 | 4042.800 | 0.240 | 240 | 240 | UNAPPROVED / BLOCK |
| EURUSDc | 1.11204 | 1.11212 | 0.00008 | 8 | 8 | UNAPPROVED / BLOCK |
| GBPUSDc | 1.32996 | 1.33006 | 0.00010 | 10 | 10 | UNAPPROVED / BLOCK |
| USDJPYc | 159.355 | 159.365 | 0.010 | 10 | 10 | UNAPPROVED / BLOCK |

Her sembol için bekleyenler: maximum, açık birim seçimi, effective_from/to, timeframe kapsamı, policy provenance/reference ve operatör onayı. Uygun limit kararı için yetkili tarihsel bid/ask dağılımı; normal likidite, seans açılışı/kapanışı, rollover ve haber dönemleri; percentil/spike süreleri; broker point/kontrat, strateji stop mesafesi ve maliyet sonrası R:R birlikte incelenmeli. Bu görev otomatik tarama/ölçüm scheduler'ı eklemedi; tek gözlem bu dağılımı temsil etmez.
