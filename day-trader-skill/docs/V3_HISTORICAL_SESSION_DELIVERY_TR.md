# Tarihsel seans kanıtı teslim raporu

11 Kasım 2026, Europe/Istanbul. Kod paketi izole yerel Git deposunda tamamlandı.
Gerçek XAUUSDc/EURUSDc 6-11 Kasım takvimi **BLOCKED_BY_EXTERNAL_EVIDENCE**.
Bu belge gerçek broker kabulü veya canlı runtime geçişi iddiası değildir.

| Madde | Sonuç |
| --- | --- |
| A. Klasör / branch / HEAD | `%USERPROFILE%\trade-ai-v3-historical-sessions`, `codex/v3-historical-session-evidence`. Başlangıç `3c8adb810058b4738640f46bde84de8ec12205ad`. Üretim kodu checkpoint'i `848d2a3`; son test fixture düzeltmesi ve bu rapor son teslim commit'indedir. Nihai HEAD için `git rev-parse HEAD`; terminal teslim yanıtında da verilir. |
| B. Ana V3 korunması | Kaynak ana branch/HEAD doğrulandı, staged/unstaged/untracked durum temizdi. Bağımsız `git clone --no-hardlinks --no-checkout` ile doğrulanmış commit'ten branch açıldı; ana Git metadata'sı paylaşılmadı. Ana branch değiştirilmedi. |
| C. Mevcut mimari | MT5 -> snapshot/candle QC -> quote-gap validation -> trade session / market trust -> V4/V5 -> risk/final karar. `bound_hours=None`, weekly false, eksik mum INSUFFICIENT_DATA/DATA_UNAVAILABLE kod ve testlerden doğrulandı. Ayrıntı: V3_HISTORICAL_SESSION_ARCHITECTURE.md. |
| D. Yeni sözleşme | `broker-historical-sessions-1`; tarihli exact identity, source/original hash, publication/acquisition, effective envelope, coverage, zone/DST, quote/trade/close-only, calendar completeness ve conflict/review alanları. Ayrıntı: V3_HISTORICAL_EVIDENCE_CONTRACT.md. |
| E. Provenance | Format/hash kaynak kimliği sayılmaz. Bağımsız SourceReview tam JSON ve orijinal belge hash'ini, review zamanını ve review reference'ını bağlar. Production listesi boş; JSON onayı yetki değildir. |
| F. Symbol identity | XAUUSDc ve EURUSDc exact eşleşir; XAUUSD/EURUSD broker sembolleri yerine kullanılamaz. GBPUSDc/USDJPYc sentetik testleri de desteklenir; gerçek kanıt yoktur. |
| G. Quote / trade / close-only | Ayrı interval setleri; trade-only quote closure üretemez. Trade completeness eksikken yeni pozisyon UNKNOWN. Close-only quote-closed sayılmaz ve yeni pozisyon DISABLED. Tam quote/trade iddiasında trade-open, kanıtlı quote-open içinde olmalıdır. |
| H. UTC / DST | `[start,end)` saniye hassasiyetli UTC; IANA zone, dated offset regime, ambiguous fold ve nonexistent yerel saat denetimi; midnight/weekend/holiday/exceptional testleri. Kapsam dışı veya gelecek interval kabul edilmez. |
| I. Weekly sınırı | Eski export parser değiştirilmedi. Hem eski weekly import testleri hem yeni provider/API senaryoları geçmiş yetkinin false kaldığını doğrular. |
| J. Importer | Allowlisted operator-owned root, strict JSON, bounded file/interval/record, original hash, traversal/ADS/reparse/hardlink retleri. Read-only CLI validate/reconcile/report sağlar. Ayrıntı: V3_HISTORICAL_EVIDENCE_SECURITY.md. |
| K. Provider / contracts | MT5Provider opsiyonel file store veya Python DI alır. `bind_historical` identity ve as-of bağlar. REAL metadata boolean/schedule yetki vermez. Eski REAL dışı declared-hours yolu boş store'da korunur. API request değişmedi; additive audit response eklendi. |
| L. M5 / M15 | Bütün eksik aralık quote-closed ve coverage içinde olmalı. Kısmen açık missing bucket ret; gerçek pozitif tick bulunan 23:00 bucket ancak tamamlandığında geçerli. Mum ekleme/interpolasyon yok. |
| M. 6-11 Kasım | Her iki exact sembol için broker source verification NO. V3_EXNESS_HISTORICAL_GAP_MATRIX.md gözlemi kanıttan ayırır. |
| N. Spread / finans | `spread_policy.py`, `broker_contract.py`, risk/lot/PnL kapıları değiştirilmedi. UNAPPROVED spread ve CONFLICTING broker contract, geçerli sentetik tarihsel kanıtta da BLOCKED. |
| O. V2 | CandlestickBridge / Double Top-Bottom DESCRIPTIVE_ONLY değişmedi. Pattern/BUY bağlamı eksik veriyi veya finans kapısını aşamaz; mevcut BUY/SELL/WAIT regresyonları korunur. |
| P. REAL / no-order | REAL_READONLY_DATA, execution_permission=false; gerçek/demo emir veya order-check çağrısı, hesap/balance okuma yetkisini genişletme, login/logout veya otomasyon eklenmedi. |
| Q. Python 3.11 | Tam paket, hedef tarihsel testler, HTTP ve compile gerçek sonuçları V3_HISTORICAL_SESSION_TEST_RESULTS.md içinde. Mevcut izole 3.11.9 / NumPy 2.2.6 interpreter okuma amaçlı kullanıldı; paketleri değiştirilmedi. |
| R. Python 3.13 | 3.11 tam koşusundan sonra 3.13.15 / NumPy 2.2.6 ile tam regresyon. Sonuçlar aynı test belgesinde. Global NumPy 2.4.6 korundu. |
| S. HTTP / diğer kabul | TestClient senaryoları yeni unit paketinde; gerçek loopback ayrı fixture listener ile, mevcut HTTP 63 ve PWA 9 sözleşme kontrolleri ayrıca çalıştırıldı. Canlı PWA veya gerçek broker kabulü sayılmaz. |
| T. Failed / skipped | İlk QA klasörü root manifest testini bozdu; günlükler depo dışına taşındı. DST mesaj maskelemesi düzeltildi. Draft API fixture bid kimliği ve yeni trade/quote consistency'ye uymayan iki sentetik test verisi düzeltildi. Eski 519 test değiştirilmedi, test atlanmadı. Son durum test raporunda. |
| U. Üretim dosyaları | Yeni `forex/historical_sessions.py`; değişen `forex/contracts.py`, `forex/providers.py`, `forex/sessions.py`, `forex/unified.py`. Yeni tests/fixtures ve `tools/runtime_acceptance/historical.py`. Eski session_evidence/api/spread/risk/V2 kaynakları değiştirilmedi. |
| V. Yerel commitler | `86f6ea4`: entegrasyon + test + mimari/operatör belgeleri. `6b60518`: Windows'ta hash'li fixture byte'larını koruyan attributes + test. `848d2a3`: çelişkili complete quote/trade ret kontrolü. Son teslim commit'i test fixture uyumu ve doğrulanmış test/teslim raporunu içerir. |
| W. Push / merge | Push, GitHub Actions, remote merge, force push, stash veya reset yapılmadı. Commitler yalnız bağımsız yerel clone'dadır. |
| X. Korunan kaynak / servisler | Ana V3, V2, PWA, bridge ve news kaynakları yazılmadı. Başlangıç listener'ları 5173=10320, 8005=9880, 8006=8284, 8007=12152; teslim öncesi aynı PID'ler gözlendi. Yalnız QA'nın kendi process/listener'ları başlatılıp kapatıldı. |
| Y. Broker kanıtı gelince | Orijinali sakla -> bağımsız kimlik/Cent scope -> hash -> dated UTC quote/trade/calendar -> conflict review -> SourceReview code review -> CLI scoped gap -> full regression -> izole API. Promotion ve runtime cutover ayrı yetki ister. |
| Z. Dış engel / minimum adım | Kullanıcı yalnız orijinal exact broker tarihsel belgeyi sağlamalı. Hazır destek mesajı ve tek komut V3_EXNESS_EVIDENCE_OPERATOR_HANDOFF_TR.md içinde. Gerçek belge ve spread onayı olmadan uygulanabilir BUY/SELL açılmaz. |

## Beş net cevap

1. Tarihsel kanıt sözleşmesi ve importer hazır mı? **YES**.
2. Güncel haftalık MT5 seansları geçmiş boşlukları otomatik kabul ettirebilir mi? **NO**.
3. Güvenilir sentetik DI ile M5/M15 doğru sınıflanıyor mu? **YES**.
4. Gerçek XAUUSDc/EURUSDc 6-11 Kasım broker kaynağıyla doğrulandı mı? **NO**.
5. Ana V3'e güvenli aktarım için hazır mı? **PARTIAL**: kod/test paketi incelemeye
   hazır; ayrı yetkili promotion yapılmadı. Gerçek evidence activation ve canlı
   runtime kabulü dış kanıt, ayrı review ve cutover gerektirir.

Git son HEAD'i çalışma dalında `git rev-parse HEAD` ile elde edilir; bir commit
kendi SHA'sını kendi içerik dosyasına koyamaz. Nihai commit kimliği kullanıcıya
teslim yanıtında açıkça verilir.
