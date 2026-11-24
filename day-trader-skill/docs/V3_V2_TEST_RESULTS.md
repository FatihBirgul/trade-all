# V3/V2 yerel test kaydı

7 Kasım 2026, Windows / Python yerel ortamı. Başlangıç V3 `d9e79b3` üzerinde `python -m unittest discover -s tests -q`: **425 çalıştı, 425 geçti, 0 başarısız, 0 yükleme hatası**. Geliştirme dalında aynı komut: **430 çalıştı, 430 geçti, 0 başarısız, 0 yükleme hatası**. Yeni `test_v3_v2_integration.py`: **5/5 geçti**. `python -m compileall -q forex` ve `git diff --check` ayrıca çalıştırıldı.

| Zorunlu senaryo | V3 yerel kanıt |
|---|---|
| Eksik RSI, BUY/SELL/WAIT ve plansız sonuç | `test_v3_v2_integration.test_missing_rsi_cannot_confirm_a_direction`; `test_unified` BUY/SELL/WAIT durumları |
| Sıfır MACD histogramı | `test_v3_v2_integration.test_zero_macd_histogram_does_not_confirm_momentum` |
| Gelecek H4, as-of/look-ahead | `test_v3_v2_integration.test_future_higher_candle_does_not_change_decision_snapshot`; `test_unified_contract.test_higher_asof_and_invalid_identity`; `test_research` prefix/fold |
| Gecikmiş H4, bitmemiş mum | `test_v3_v2_integration.test_stale_higher_and_unfinished_primary_fail_closed` |
| Yanlış provider, yanlış market kimliği | `test_v3_v2_integration.test_quote_provider_market_identity_and_volume_capability`; `test_unified_contract.test_mixed_candle_identity_is_not_discarded` |
| Forex hacim capability | Aynı yeni test ve `test_unified.test_tick_volume_has_no_vwap_or_order_flow` |
| Tekrarlanan kanıt, çelişen sinyal | `test_unified_contract.test_same_event_and_correlation_do_not_add_votes`; `test_unified.test_strategy_conflict_veto`, `test_opposing_private_price_context_vetoes_public_buy` |
| Broker seans/risk vetosu | `test_unified.test_closed_unknown_spread_and_risk_veto`; `test_sessions`; `test_policy` |
| API uyumu, eski Forex regresyonu | `test_unified.test_v5_response_and_legacy_paths`; tam 430 test kapısı |

V2 handoff ayrı kanıt bildirir: hedefli API/motor **74/74**, RSI/ATR **39/39**; iki grup örtüşebilir ve V3 sayısına eklenmedi. V2 çevrimdışı runner sonucu **559 çalıştırıldı, 558 geçti, 1 yükleme hatası** olarak kaydedildi; V2 testleri bu V3 çalışmasında yeniden çalıştırılmadı. Hata `backend/tests/test_v2_chart_pivot_causality.py` içindeki `from backend.market_ai.engines import chart_patterns` satırından gelir. Runner `backend/` dizinini `sys.path` başına ekler; aynı dizin çalışma kökü olduğunda `backend` üst paketini bulamaz. Salt-okunur `python -B -c` tanısı: V2 depo kökünden `find_spec('backend')` bulundu, `backend/` içinden bulunmadı. Bu import-root uyumsuzluğu kaynak dosyası değiştirilmeden saptandı; test silinmedi veya skip edilmedi.

Sentetik/fixture sonuçları piyasa kârlılığı, canlı MT5 doğrulaması veya özel strateji Forex uygunluğu kanıtı değildir.
