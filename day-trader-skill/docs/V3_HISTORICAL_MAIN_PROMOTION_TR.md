# Historical Session Engine yerel ana entegrasyonu

11 Kasım 2026. Promotion **YES**; yalnız yerel Git fast-forward yapıldı.
Canlı runtime cutover, restart veya gerçek Exness evidence activation yapılmadı.

| Madde | Doğrulanan sonuç |
| --- | --- |
| A. Ana V3 | `%USERPROFILE%\trade-ai-v3-core`, `codex/v3-real-readonly-analysis`; başlangıç `3c8adb810058b4738640f46bde84de8ec12205ad`, kod kabul hedefi `24df2ed6a6c94b8eea8548ec8980ba897057e0b5`. Ardından yalnız bu promotion belgeleri için yerel commit oluşturulur; son HEAD teslim yanıtındadır. |
| B. Historical kaynak | `%USERPROFILE%\trade-ai-v3-historical-sessions`, `codex/v3-historical-session-evidence`; başlangıç ve son HEAD `24df2ed6a6c94b8eea8548ec8980ba897057e0b5`. Kaynak değiştirilmedi. |
| C. Ancestry | Merge-base ana başlangıç SHA'sıdır. Kaynak `fsck --connectivity-only` başarılı; `merge-base --is-ancestor` başarılı. Ayrı clone'dan yalnız yerel non-force fetch ile nesneler alındı, ardından `git merge --ff-only` çalıştı. Merge commit/cherry-pick/rebase yok. |
| D. Runtime watcher | 8006 PID 8284, parent 11380 (V5Runtime launcher), sonra manuel PowerShell 7028 ve Explorer 6732. Cwd ana V3. CLI reload yok, UVICORN_RELOAD/WATCHFILES_FORCE_POLLING unset, child watcher yok. İlgili process/service/task ve Vite config incelemesinde ana V3 reload bağlantısı bulunmadı. Bu gözlenen operasyonel risk denetimidir; bütün process belleğinin kriptografik ispatı değildir. |
| E. Promotion gerekçesi | İki depo temiz ve beklenen SHA'da; source tests/API/security başarılı; ancestry uygun; gözlenen auto-reload riski dışlandı. Başlangıç SHA'sı recovery ref ile korundu. FF sonrasında hedefte testler ayrıca tekrarlandı. |
| F. Değişiklikler | Kaynaktan 21 dosya, 1989 ekleme/7 silme. Yeni historical_sessions.py; contracts/providers/sessions/unified dar entegrasyonu; 81 yeni test, sentetik fixture, HTTP aracı, sekiz belge. Eski 519 test değişmedi. Bu raporlarla eklenen değişiklikler yalnız docs altındadır. |
| G. Importer | Strict JSON/unknown field/duplicate key/bütçe/hash/relative path/reparse/hardlink kontrolleri; operator-owned allowlist önkoşulu. Untrusted concurrent filesystem için sandbox iddiası yok. |
| H. Independent review | Production review listesi boş. SHA-256 tek başına broker kimliği değildir; JSON içindeki verified/APPROVED yetki vermez. Onay sadece code-owned, tam JSON ve original hash'e bağlı ayrı inceleme kaydıyla mümkündür. Synthetic approval yalnız Python test DI; normal API request ve env bunu alamaz. |
| I. Weekly-only | Eski weekly parser değiştirilmedi; historical_gap_authorized=false. Weekly ve operator source API/fixture testlerinde BLOCKED. |
| J. M5/M15 | Bütün missing interval coverage içinde ve quote-closed olmalı; kısmen açık bucket ret. 23:00 bucket'ındaki tick M15'i 23:15'ten önce kapatmaz; mum/interpolasyon eklenmez. |
| K. UTC/DST/as-of | Explicit dated UTC ve IANA offset rejimi, fold/nonexistent retleri; source acquisition/review karar anında bilinmeli. Retrospective data-quality policy live snapshot'a sokulamaz. |
| L. Karar matematiği | core.py ve strateji/Entry/SL/TP kodları kaynak diff'inde değişmedi. BUY/SELL/WAIT ve V2 descriptive-only mevcut regresyonlar korunur. |
| M. Finans | spread_policy.py, broker_contract.py ve policy.py değişmedi. UNAPPROVED spread, USC identity, minimum lot risk ve broker PnL oracle kapıları testlerde korunur. |
| N. REAL/no-order | REAL_READONLY_DATA ve execution_permission=false korunur. Emir/order-check, login/logout, hesap değiştirme veya tarama eklenmedi. Yeni canlı terminal testi yapılmadı. |
| O/P. Python | Source ve main için 3.11.9 ve 3.13.15 tam paketleri ayrı yeniden çalıştırıldı. İzole NumPy 2.2.6; sonuçlar V3_HISTORICAL_MAIN_TEST_RESULTS.md içinde. |
| Q/R. HTTP / hatalar | Her iki repo/interpreter için HTTP 63, historical HTTP 14, PWA contract 9; fixture process/listener cleanup dahil. Final failure/error/skipped sonuçları test belgesindedir; sayılar benzersiz toplam diye toplanmaz. |
| S. Recovery / commit | `refs/recovery/historical-main-20261111-39c4c1b98405` -> `3c8adb810058b4738640f46bde84de8ec12205ad`. Local object ref `refs/integration/historical-session-39c4c1b98405` -> source SHA. Kaynak dört commit'i FF ile korundu; raporlar için ayrı yerel docs commit'i vardır. |
| T. Uzak işlemler | GitHub push/Actions/remote merge/force/reset/stash yok. Kaynak nesneleri yalnız yerel dosya yolundan alındı. |
| U. Servisler | 5173=10320, 8005=9880, 8006=8284, 8007=12152 promotion öncesi/sonrası aynı. PWA/V2/bridge/news kaynakları yazılmadı. Ana backend disk kaynakları yetkili FF ile ilerledi; çalışan süreçler yönetilmedi. |
| V. Gerçek kanıt | 6-11 Kasım XAUUSDc/EURUSDc quote/trade tarihi UNVERIFIED; BLOCKED_BY_EXTERNAL_EVIDENCE. Gözlenen M1/tick çizelgesinden broker schedule üretilmedi. |
| W. Sonraki runtime | Ayrı yetkili immutable release/env/config ve loaded-code attestation ile candidate acceptance, sonra kontrollü cutover gerekir. Bu görev bunu yapmadı; V3_HISTORICAL_RUNTIME_HANDOFF.md. |

## Altı net cevap

1. Motor ana V3'e geçti mi? **YES**.
2. Ana V3 üzerinde 600 test geçti mi? **YES**, iki Python sürümünde 600/600.
3. Güncel haftalık MT5 geçmiş boşluğu otomatik kabul edebilir mi? **NO**.
4. Gerçek 6-11 Kasım XAUUSDc/EURUSDc kanıtı doğrulandı mı? **NO**.
5. Çalışan 8006 yeni modülü kullanıyor mu? **UNVERIFIED**; canlı şemada yeni alan yok,
   loaded-code attestation alınmadı ve runtime geçişi yapılmadı.
6. Broker güvenliği ve no-order korundu mu? **YES**.
