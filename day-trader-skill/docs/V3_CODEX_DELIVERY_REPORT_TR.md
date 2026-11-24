# Broker sözleşmesi / spread readiness teslimi

11 Kasım 2026. Başlangıç `09e5dab3bead337b3fab6a9267bbfe4fc16f3e7b`; yeni yerel dal `codex/v3-broker-evidence-readiness`. Başlangıç root/branch/HEAD, staged/unstaged/untracked kontrolü temizdi. Son SHA bu teslim commitidir; son kullanıcı raporunda tam verilir. Ana önceki dalın tarihi ve P1/V2 commitleri korunur; push/merge/reset/stash yok.

## Değişiklik kapsamı

- Yeni üretim modülleri: `forex/broker_contract.py` field-level current trust ve contract/PnL tutarlılığı; `forex/spread_policy.py` bounded/versioned operator policy ve spread birim/kimlik/tarih kapıları.
- Güncellenen üretim: `forex/providers.py`, `forex/core.py`, `forex/policy.py`, `forex/unified.py`, `forex/api.py`. Mevcut motor/strateji/formasyon yeniden yazılmadı. REAL explicit policy'de veri/finans okumaları preflight'a bağlanır; eksik onay/metadata/oracle dönüşümü lotu kapatır.
- API additive `broker_contract` / `spread_status`; V5 adı aynı. Risk calculate optional timeframe M15. Legacy fixture/DEMO explicit limitleri korunur; REAL eski çıplak limit güveni kaldırılır. Session importer/engine/MQL5 exporter değişmedi.
- Yeni `tests/test_broker_readiness.py`; mevcut test beklentileri değiştirilmedi. QA araçlarına opsiyonel typed HTTP matrisi ve local loaded-code fingerprint eklendi.
- Dört null/onaysız rule template'i ve hesap kimliği içermeyen güncel gözlem snapshot'ı; istenen sekiz konu belgesi, next-actions/cutover yönlendirmeleri.

## Bulgular

Dört sembol current contract metadata CURRENT_MT5_OBSERVED, eksik/conflicting alan yok; tarihsel durum UNVERIFIED. Market family current gözlemdir, legal market/contract_type unverified kalır. Güncel scalar max_spread null kök nedeni eski config sözlüğünde uygulanabilir değer bulunmaması ve onay/birim/tarih sözleşmesinin yokluğudur. Yeni altyapı hazır; kullanıcı kesin limit olmadığını açıkça bildirdiği için dört policy UNAPPROVED/BLOCK, maximum null kalır. Canlı 8006'ya bu kod yüklenmedi.

16:20:32 İstanbul tek spread gözlemi: XAUUSDc 0.240/240 point; EURUSDc 0.00008/8 point; GBPUSDc 0.00010/10 point; USDJPYc 0.010/10 point. Bunlar limit önerisi değildir. Her sembol için maximum/unit/effective interval/timeframe/provenance/onay beklenir; uygun karar için likidite/rollover/haber ve maliyetli R:R kapsamlı yetkili bid/ask dağılımı gerekir. Otomatik ölçüm/tarama eklenmedi.

Salt okunur 1-lot/10-tick BUY/SELL PnL örnekleri güncel contract/currency hesabıyla uyumlu; gerçek balance kullanılmadı. USC ayrımı, minimum lot, rounding, stop, net risk ve broker-loss kontrolleri korunur. XAUUSDc 9 Kasım tarihsel session kanıtı BLOCKED_BY_EXTERNAL_EVIDENCE. Pattern descriptive-only ve source SHA/first-known/prefix kapıları korunur.

## Test sonuçları

| Grup | Python 3.11.9 / NumPy 2.2.6 | Python 3.13.15 / NumPy 2.2.6 |
|---|---|---|
| Başlangıç regression | 487 PASS, 92.631 s | 487 PASS, 86.412 s |
| İlk yeni 30 test dahil regression | 517 PASS, 76.500 s | 517 PASS, 71.256 s |
| Nihai regression (32 yeni test) | 519/519 PASS, 57.823 s | 519/519 PASS, 53.207 s |
| Önceki HTTP kontrolleri | 56/56 PASS | 56/56 PASS |
| Typed broker HTTP dahil | 63/63 PASS | 63/63 PASS |
| PWA pure guard/source | Ortak Node koşusu 9/9 PASS | Aynı kaynak |

Grup toplamları benzersiz test sayısı diye toplanmaz: 63, önceki 56'yı ve 7 yeni HTTP assertion'ı kapsar; PWA/HTTP/unit kapsamları örtüşür. Full suite 487 mevcut + 32 yeni unittest'tir. Fixture sözleşmeleri canlı broker onayı değildir. Yeni testler independent literal aritmetik, yanlış birim/point/currency/contract/tick, minimum risk, source/privacy, approval/date/version, per-symbol session ve memory-code fingerprint kapsar. İlk geliştirme denemelerinde draft effective end/start tutarsızlığı ve fixture risk-route saat beklentisi düzeltildi; mevcut üretim test beklentileri değiştirilmedi. Nihai tam koşularda 0 failure, 0 error, 0 skipped; HTTP/PWA kontrolleri başarılıdır. Derleme, pip check ve diff kontrolleri başarılıdır.

## Runtime ve sonraki adım

8006 PID 7532 korunuyor. Yeni trust/spread alanları çalışan şemada yok: broker-readiness sürümüne göre OLD_VERSION; exact P1 loaded checkpoint VERSION_UNVERIFIED. Yeni startup fingerprint sadece fresh own interpreter için local code-object hash'idir; disk eşitliği veya public endpoint üzerinden sürüm iddiası değildir. Kendi izole test süreçleri kapatıldı. Local/Tailscale eski schema erişimi başarılı; tam frontend feature kabulü PARTIAL.

İstenen asgari dış girdiler: her sembol için operatörce onaylı spread kuralı ve exact tarihli XAUUSDc session kanıtı. Bunları kullanıcı şimdi sağlamadığı için diğer geliştirmeler durdurulmadı. Sonra ayrı yetkili runtime cutover ve frontend değişikliği yapılır; bu görev servis restart yetkisi kullanmaz. Uygulanabilir plan `V3_RUNTIME_CUTOVER_READINESS.md`; frontend `V3_PWA_FINAL_HANDOFF.md`.

Global Python/NumPy değişmedi; global Python 3.11 NumPy 2.4.6 tekrar doğrulandı. İzole pip check/compile/diff kontrolleri başarılı. PWA/V2/MT5 bridge/haber kaynaklarına bu görev yazmadı. Son karşılaştırmada dış eşzamanlı PWA değişikliği görüldü: AnalysisPanel.tsx değişti; AnalysisNewsRisk.tsx ve bir AnalysisPanel yedeği eklendi. Güncel panel salt okunur yeniden incelendi ve 9/9 guard kontrolü tekrar geçti; buradaki analiz/spread handoff bulguları değişmedi. NewsPanel/news_bridge/mt5_bridge ve diğer başlangıç dosyaları aynı hash'te kaldı. Dört servis PID/listen zamanı aynı: 5173/10320, 8005/2840, 8006/7532, 8007/12152. Bu görev bunları restart/kill etmedi. V2'nin önceki kirli chart ve takip edilmeyen araştırma dosyaları korundu; P1 753ed59 temiz kaldı. Ham loglar `%TEMP%\trade-ai-broker-readiness-20261111` altında; temp kalıcı arşiv garantisi değildir. Kalıcı kritik gözlem `docs/evidence/broker_current_observation_20261111.json` içinde.
