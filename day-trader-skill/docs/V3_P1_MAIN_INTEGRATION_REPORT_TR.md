# P1 ana V3 yerel entegrasyon raporu

Tarih: 11 Kasım 2026, Europe/Istanbul. Bu rapor kaynak entegrasyonunu ve çevrimdışı kabulü belgeler; çalışan PWA için canlı kabul değildir.

## Git recovery ve entegrasyon

- Hedef kök: `%USERPROFILE%\trade-ai-v3-core`, dal `codex/v3-real-readonly-analysis`.
- Başlangıç: `f78b638cd9ca6b9c30279c4139cb5ba04f302dba`; hedef ve kaynak başlangıçta temizdi; staged, unstaged ve untracked değişiklik yoktu.
- P1 kök: `%USERPROFILE%\trade-ai-v3-v2-p1`, dal `codex/v3-v2-p1-descriptive-analysis`, HEAD `753ed59269c36d3d6d0da561924cd5c144b20ea0`.
- Sıralı P1 commitleri: `a91ef37`, `8fbf1b7`, `753ed59`. Merge-base tam başlangıç commitidir; `merge-base --is-ancestor` başarılıdır.
- Her iki Python ortamındaki izole P1 kabulünden sonra, ana dal/HEAD/temizlik ve P1 dal/HEAD/temizlik yeniden doğrulandı.
- Recovery ref: `refs/recovery/p1-main-20261111-3107aacf306d`, başlangıç commitini gösterir.
- `git merge --ff-only 753ed59269c36d3d6d0da561924cd5c144b20ea0` başarılı: `f78b638 -> 753ed59`. Merge commit, cherry-pick, rebase, reset veya stash yoktur. Sonraki yerel commit yalnız bu kabul belgelerini içerir.

## P1 değişiklik denetimi

| Sınıf | Dosyalar ve sonuç |
|---|---|
| Üretim | `forex/v2_chart_bridge.py` yeni; `forex/v2_bridge.py` mevcut candlestick ile opsiyonel composite yapılandırması. |
| Test | `tests/test_v2_chart_bridge.py`: 12 yeni kabul testi. `tests/test_repo.py`: yalnız `.venv` dışlama ve requirements dosyası envanteri. Test silme/skip yok. |
| Bağımlılık | `requirements-test-py311.txt`: tam sürüm pinleri; NumPy 2.2.6. Mevcut API requirements değişmedi. |
| Dokümantasyon | `V3_PY311_DEPENDENCY_AUDIT`, `V3_V2_ADVANCED_INTEGRATION_MATRIX`, `V3_V2_CHART_PATTERN_VALIDATION`, `V3_V2_NEXT_ACTIONS`, `V3_V2_P1_API_CONTRACT`, `V3_V2_P1_DELIVERY_REPORT_TR`, `V3_V2_P1_TEST_RESULTS` adlı yedi Markdown dosyası. |
| API | Yeni endpoint yok. `/api/v5/analysis` mevcut `chart_patterns` alanına betimleyici içerik alabilir. `forex/api.py` değişmedi. |
| Kritik kapsam | P1 dışında kritik üretim değişikliği yok. V5 core/unified, finans, broker/session, REAL policy kaynakları değişmedi. PWA, MT5 bridge ve haber servisi değiştirilmedi. |

Toplam P1 farkı: 12 dosya, 681 ekleme, 6 çıkarma. Bu görev ayrıca üç rapor oluşturur ve `V3_NEXT_ACTIONS.md` dosyasını günceller.

## Pinli V2 ve bağımlılık güvenliği

V2 HEAD: `c80c97f227a2c233a610df669919ba2f464e4f9f`, dal `antigravity/v2-analysis-research`. Kaynak yol: `backend/market_ai/engines/chart_patterns.py`. `git show <commit>:<path>` çıktısının doğrudan subprocess baytları SHA256 ile doğrulandı; PowerShell metin yönlendirmesi kullanılmadı:

`af69112c91938c4bd6fea3d16f43a333f63c35ea3715ed082069868e1018f1ba`

Kaynağın importları yalnız `__future__.annotations`, `typing` ve `numpy`; başka V2 modülüne transitif import yok. NumPy'nin kendi kurulu bağımlılıkları izole ortamda `pip check` ile doğrulandı. AST denetimi emir, login, ağ, dinamik import ve dosya açma çağrılarını reddeden mevcut testten geçti. Sabit içerik hash'i değişik modül baytlarını yüklemeden reddeder. Yanlış kök, olmayan kaynak, yanlış hash ve yanlış NumPy güvenli ret üretir. Yapılandırma yüklenemiyorsa API 503 `DATA_UNAVAILABLE`; evaluate/sözleşme hatasında özel extension `UNAVAILABLE` olur. Bunlar başarıyla yüklenmiş P1 analizi olarak raporlanmaz.

V2'nin önceden var olan kirli durumu korundu: chart dosyasındaki iki range düzeltmesi; üç takip edilmeyen araştırma testi ve `market_ai/__init__.py`. Adaptör bu kirli dosyadan çalışmaz; V2'ye yazılmadı.

Python 3.11.9 için mevcut P1 `.venv` kullanıldı. Python 3.13.15 için `%TEMP%\trade-ai-p1-main-qa-20261111\py313` oluşturulup aynı requirements kuruldu. İki ortam da NumPy 2.2.6 kullanır; global Python 3.11 NumPy 2.4.6 değiştirilmedi. Global Python 3.13 mevcut NumPy 2.2.6 da değiştirilmedi. Çalışan API'nin global Python ortamına kurulum yapılmadı.

## Descriptive-only ve V5 değişmezliği

Yalnız Double Top ve Double Bottom yayımlanır. Sağ pivot penceresi 3 kapanmış mumdur; her prefix yeniden değerlendirilir. Formasyon zamanı, first-known ve confirmation ayrı tutulur; 40 bar warm-up sınırındaki sol sansür ayrıca işaretlenir. Expiry etiketlenir; invalidation `NOT_MODELED` kalır. Başka formasyon ailesi, V2 hedefi/confidence veya yön oyu eklenmez.

Aynı immutable snapshot üzerinde extension açık/kapalı karşılaştırması BUY, SELL, gerçek `WAIT`, USC ve `INSUFFICIENT_DATA` durumlarında geçti. WAIT için kontrollü karşıt core strateji fixture'ı, INSUFFICIENT_DATA için kontrollü tarihsel seans eksikliği fixture'ı kullanıldı; bunlar canlı broker kanıtı değildir. Mevcut 487 test ayrıca gerçek session/candle gate fixture'larını kapsar. `final_decision`, `trading_eligibility`, `data_status`, `decision_reasons`, entry, SL, TP1/TP2, spread, account currency, lot, risk amount, risk/reward ve tüm `risk_policy` birebir eşittir. `execution_permission=false` korunur. Net maliyet/risk hesabı da aynı policy/sizing sonucu ve mevcut risk testleriyle korunur.

REAL_READONLY_DATA, USC/USD/USDC ayrımı, XAUUSDc alias/session reddi, bilinmeyen geçmiş boşluklar, candlestick regresyonları ve no-order kontrolleri tam pakette geçti. V2 betimlemesi V5 `INSUFFICIENT_DATA` sonucunu BUY/SELL'e yükseltemez. Emir veya hesap değiştirme çağrısı yapılmadı.

## Kabulün sınırı

`SOURCE_INTEGRATED=YES`, `LOCAL_TESTS_PASSED=YES`, `RUNTIME_VERSION_VERIFIED=UNVERIFIED`, `LIVE_PWA_ACCEPTED=UNVERIFIED`.

Tam sayımlar ve komutlar: `V3_P1_MAIN_TEST_RESULTS.md`. Süreç gözlemi, XAUUSDc tarihsel seans engeli ve sonraki sürüm geçişi: `V3_P1_RUNTIME_HANDOFF.md`. GitHub push, Actions veya uzak merge yapılmadı.

Son kontrol: ana kaynak `753ed59` ve bunun üzerindeki yalnız belge commitidir; P1 HEAD/dalı ve temizliği değişmedi. V2 HEAD/dalı ile yukarıda listelenen eski kirli durum değişmedi. Son port gözleminde 5173/8005/8006/8007 sırasıyla PID 10320/2840/7532/9724 olarak dinliyordu; önceki gözlemlerle aynı PID ve listen zamanları korundu. Global NumPy sürümleri tekrar kontrol edildi: Python 3.11 için 2.4.6, Python 3.13 için 2.2.6. Bu raporları içeren yerel belge commitinin tam SHA'sı son kullanıcı raporunda verilir; P1 entegrasyon commitinin SHA'sı değişmedi.
