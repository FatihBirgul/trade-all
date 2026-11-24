# REAL veri / manuel simülasyon kabul durumu

| Kriter | Durum | Kanıt / kalan sınır |
|---|---|---|
| DEMO_ONLY geriye uyumluluk | PASS | Fixture preflight ve eski 503 durumu |
| REAL_READONLY_DATA explicit preflight | PASS | Fixture + gerçek ayrı MT5 bağlantısı REAL/Exness-MT5Real50/USC |
| No order / no symbol_select REAL | PASS | AST güvenlik ve mutasyon yakalayan fixture |
| Dört alias ve gerçek contract/quote/bar | PASS (anlık) | REAL terminal salt okunur; kaynak servis eşitliği UNVERIFIED |
| USC/USDC/USD ayrımı | PASS | Gerçek `account_info.currency=USC`, exact eşleme testleri |
| Gerçek bakiye gizliliği | PASS | REAL preflight balance property okumayan test; API'ye verilmez |
| Hipotetik sermaye/lot | PASS (fixture) | Explicit sermaye ve USC gerekir; NOT_EVALUATED, execution false |
| Seans/UTC/DST | PASS (sentetik), BLOCKED (Exness doğrulaması) | Gerçek boşluk gözlendi; yetkili çizelge yok |
| Gerçek veriyle güvenli karar | PASS (ret) | Dört sembol INSUFFICIENT_DATA, lot null |
| Gerçek veriyle BUY/SELL ve seviyeler | BLOCKED | Broker seans kaynağı ve canlı uçtan uca değerlendirme yok |
| V2 candle context canlı | BLOCKED | Snapshot QC seans boşluğunda duruyor; pinli offline köprü korunuyor |
| 8005/8006/5173 aynı kaynak ve yeni sürüm | UNVERIFIED | Portlar mevcut, servisler yeniden başlatılmadı |
| PWA dört sembol, currency ve risk kaynağı | BLOCKED | PWA yalnız XAU/EUR; yeni alanlar gösterilmiyor |

Genel durum **PARTIAL**. Güvenli read-only altyapı ve ret davranışı çalışıyor; broker seansı ve PWA handoff tamamlanmadan ilk kullanılabilir uçtan uca sürüm PASS değildir.
