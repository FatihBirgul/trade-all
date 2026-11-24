# Main promotion sonrası PWA kabul listesi

11 Kasım 2026. PWA yalnız salt okunur incelendi. Güncel AnalysisPanel varsayımsal USC sermayesi gönderiyor; sabit 10.000 yok. GBPUSD/USDJPY chart seçimi var ama analiz destek kapısı yalnız XAUUSD/EURUSD. isAnalysis/approved temel guard'ları ek response alanlarını reddetmez; NOT_EVALUATED aday planını approved=false nedeniyle gizler. News/AnalysisNewsRisk başka iş akışıdır; bu görev müdahale etmedi. 9 source/pure-guard kontrolü canlı UI kabulü değildir.

Exact kök `%USERPROFILE%\trade-ai-forex-web`. Ayrıntılı yeni field sözleşmesi `V3_PWA_FINAL_HANDOFF.md`; aşağıdaki kayıtlar frontend uygulama/kabul sırasıdır.

| Dosya / component | API alanı | Gerekli sonuç | Kabul / güvenlik |
|---|---|---|---|
| src/AnalysisPanel.tsx / supported + manual button | symbol/timeframe | GBPUSD ve USDJPY tek manuel POST | Dört canonical sembol; symbol değişince eski yanıt iptal; tarama eklenmez |
| src/AnalysisPanel.tsx / Analysis type + pattern section | chart_patterns/candlestick_patterns | Double Top/Bottom, timeframe/source/first-known/confirmation, DESCRIPTIVE_ONLY | Empty/null/unavailable/expired/left-censored; pattern V5 kararını değiştirmez |
| src/AnalysisPanel.tsx / broker context | broker_contract status/fields/missing/conflicting/historical_status | Current teknik gözlem ile tarihsel/operatör güvenini ayır | Tek eksik alan diğerlerinin trust'ını yükseltmez; eski API alan yokluğunu tolere et |
| src/AnalysisPanel.tsx / spread context | spread_status observed/policy_status/max_allowed_price/reasons | Gözlenen fiyat/point/symbol spread ile izin limiti ayrı | UNAPPROVED/BLOCK ve null max açık; gözlem otomatik maksimum olmaz |
| src/AnalysisPanel.tsx / account/risk labels | account_currency/risk_balance_source/market_data_account_mode | USC + hypothetical kaynak görünür | USD/USDC karışmaz; gerçek balance veya execution izlenimi yok |
| src/AnalysisPanel.tsx / approved + plan | NOT_EVALUATED/final_decision/execution_permission | Geçerli varsayımsal aday açık etiketiyle gösterilebilir; ELIGIBLE'a zorla çevrilmez | BLOCKED/stale/INSUFFICIENT_DATA/null Entry/SL/TP/lotta plan yok; emir UI yok |
| src/AnalysisPanel.tsx / tag + price | REAL source; metadata digits/tick | Sabit MANUEL DEMO etiketi düzeltilir; broker precision | XAUUSDc/USDJPYc 0.001 tick; stale metadata ile yuvarlama yok |
| src/AnalysisPanel.tsx / errors/reasons | HTTP 503/DATA_UNAVAILABLE/ACCOUNT_PREFLIGHT_BLOCKED + decision_reasons | Kaynak/spread/session reddi anlaşılır | Gizli path/env/account bilgisi yok; retry manuel |
| src/App.tsx + src/MarketChart.tsx / source | provider/broker_symbol/as-of/closed time | Chart ve analysis kaynak/zaman tutarlılığı | Aynı alias tek başına hesap eşitliği kanıtı değil |
| vite.config.ts / proxy + allowedHosts | /engine -> localhost:8006 | Same-origin local/Tailscale korunur | HTTPS manual 200/503, Android/service-worker cache ve host/CORS ayrı kabul |

Mevcut local proxy ve Tailscale schema HTTP 200; promotion öncesi/sonrası aynı eski schema. Yeni source ana dalda olsa da çalışan PWA yeni broker/spread alanlarını almıyor. PWA dosyaları, NewsPanel, AnalysisNewsRisk, mt5_bridge ve news_bridge değiştirilmedi. Frontend değişikliği ve live feature kabulü ayrı adımdır.

Son eşzamanlılık notu: Yukarıdaki değiştirilmedi ifadesi bu görevin yazım kapsamıdır. `src/MarketChart.tsx` başka iş akışında değişti; salt okunur tekrar incelendi. Vite HMR bu dış değişimden etkilenebilir, dolayısıyla PID/schema eşitliğinden canlı UI değişmezliği sonucu çıkarılmadı. AnalysisPanel guard/source 9/9 tekrar geçti; chart-render/UI feature kabulü bu testin kapsamı değildir.
