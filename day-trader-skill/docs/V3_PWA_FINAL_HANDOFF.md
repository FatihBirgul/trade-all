# Güncel PWA broker/spread handoff

11 Kasım 2026. Salt okunur aktif PWA incelemesi; React, NewsPanel, MT5 bridge ve haber servisine yazılmadı. Sabit 10.000 sermaye varsayımı kullanılmadı: aktif AnalysisPanel kullanıcıdan hypothetical USC sermayesi/risk alıyor. 9 saf guard/source kontrolü geçer. Local ve Tailscale /engine schema HTTP 200; mevcut runtime yeni güven alanlarını henüz taşımıyor.

Eşzamanlı dış değişiklik notu: AnalysisPanel.tsx başka iş akışında değişmiş, AnalysisNewsRisk.tsx eklenmiştir. Bu görev bunlara müdahale etmedi. Son aktif panel tekrar salt okunur incelenip 9/9 kontrol tekrar geçti. Aşağıdaki analiz kapıları/formasyon/spread eksikleri hâlâ geçerlidir; haber bileşeni ayrı kapsamda kalır.

Backend V5 şema adı değişmedi. Yalnız `broker_contract` ve `spread_status` iki additive response alanıdır; analysis_mode, execution_permission ve mevcut finans alanları korunur. Risk calculate isteğinde optional timeframe varsayılan M15 eklenmiştir. Eski yanıtları ve source unavailable/null durumlarını frontend toleranslı ele almalı.

Tabloda exact kök `%USERPROFILE%\trade-ai-forex-web`; bu görev bu işleri frontend'e uygulamadı.

| Exact file / component | API alanı | UI davranışı | Test | Güvenlik etkisi |
|---|---|---|---|---|
| src/AnalysisPanel.tsx / supported + button | symbol/timeframe | GBPUSD ve USDJPY manual analizini destekle; otomatik istek/tarama ekleme | Dört sembolde tek POST; symbol değişince eski sonuç iptal | Yanlış sembol planı yok |
| src/AnalysisPanel.tsx / Analysis type, pattern context | chart_patterns, candlestick_patterns | Double Top/Bottom ve candlestick etiketleri DESCRIPTIVE_ONLY; timeframe/source/first-known/confirmation | BUY ile bearish Top birlikte; Bottom, empty/null/unavailable/expired | Pattern karar/finans kapılarını aşmaz |
| src/AnalysisPanel.tsx / trust context | broker_contract.status/fields/missing_fields/conflicting_fields/historical_status | CURRENT_MT5_OBSERVED ile tarihsel/operatör onayını ayır | Bir alan eksik, diğerleri current; conflict; eski yanıt alanı yok | Current contract geçmiş seans onayı sayılmaz |
| src/AnalysisPanel.tsx / spread context | spread_status.observed, policy_status, max_allowed_price, decision/reasons | Ask-bid fiyat farkı, point, MT5 symbol spread ve izin limiti ayrı; onaysız maximum tire + BLOCK nedeni | Boundary/above, PRICE/POINTS, UNAPPROVED, missing/stale quote | Gözlenen spread otomatik limit/renkli onay olmaz |
| src/AnalysisPanel.tsx / risk and account labels | account_currency, risk_balance_source, market_data_account_mode | USC ve HYPOTHETICAL_CAPITAL açık göster; sabit bakiye ekleme | USC/USD/USDC ret, null lot, current REAL kaynak | Gerçek balance/uygulanabilir lot izlenimi yok |
| src/AnalysisPanel.tsx / approved and plan display | NOT_EVALUATED, final_decision, null levels, execution_permission | NOT_EVALUATED geçerli varsayımsal aday planı, broker işlem uygunluğundan ayrı gösterebilir. BLOCKED/null/stale retlerde plan gösterme | BUY/SELL hypothetical etiketli; INSUFFICIENT_DATA/WAIT/spread BLOCK null; execution false | NOT_EVALUATED'ı ELIGIBLE'a çevirmek yok; emir UI'si yok |
| src/AnalysisPanel.tsx / fixed MANUEL DEMO label and digits | market_data_account_mode; metadata digits/tick | REAL salt okunur kaynak modu doğru; instrument precision | XAUUSDc ve USDJPYc 0.001 tick; sembol değişiminde stale meta yok | Fiyat yuvarlama ve DEMO/REAL karışıklığı yok |
| src/AnalysisPanel.tsx / fetch error and reasons | HTTP 503 + DATA_UNAVAILABLE/ACCOUNT_PREFLIGHT_BLOCKED; decision_reasons | Teknik kaynak retleri ve spread/session nedenlerini güvenli göster | Bozuk source, onaysız spread, UNKNOWN broker; manuel retry | Gizli yol/env/account bilgisi gösterilmez |
| src/App.tsx + src/MarketChart.tsx / selected source context | broker_symbol/provider/as_of/closed time | Chart ile analiz alias/provider/zaman tutarlılığı | Gecikmiş quote/başka source; dört sembol | Aynı alias tek başına hesap eşitliği kanıtı değil |
| vite.config.ts / /engine proxy + allowedHosts | /engine/api/v5/analysis | Aynı origin localhost 8006; production proxy ve Tailscale ayrı kabul | Local/HTTPS schema + manual 200/503; Android/service-worker | Host/CORS kapıları korunur |

Mevcut approved fonksiyonu ELIGIBLE istemesi nedeniyle REAL hypothetical NOT_EVALUATED planını gizliyor. Bu sınırlama backend uygunluk etiketini gevşeterek çözülmemeli. Frontend düzeltmesi ayrıca yetkilendirilecek; NewsPanel.tsx kapsam dışıdır. Tam önceki transport bulguları `V3_PWA_INTEGRATION_HANDOFF.md` içinde; bu belge yeni broker/spread alanları için esas handoff'tur.
