# PWA / V5 manuel API sözleşmesi

Kaynak: backend 3c8adb8, forex/api.py UnifiedRequest ve forex/unified.py UnifiedAnalysis; V2 chart/candlestick adapter payload'ları. Yeni endpoint veya yeni API sürümü varsayılmadı.

Tek kullanıcı işlemi `POST /engine/api/v5/analysis` -> Vite /engine rewrite -> `/api/v5/analysis`. Body: symbol XAUUSD/EURUSD/GBPUSD/USDJPY; destekli timeframe; confirmations primary D1 ise D1, diğerlerinde H4; require_private false; kullanıcı girdisi hypothetical_capital; hypothetical_currency USC; risk_pct (0,5]. Balance/broker-verified provenance gönderilmez. D1'e H4 confirmation gönderilerek geçersiz üst-TF üretilmez.

20 saniye timeout; input/symbol/time değişimi ve unmount abort; pending ref tek request sağlar. HTTP/JSON/identity hatasında eski sonuç temizlenir. HTTP error reason içeriği UI'ye yansıtılmaz; yalnız bilinen status ve generic Türkçe hata. Büyük yanıt sınırı 2 milyon karakter; zorunlu schema/provider/symbol/time/decision/status/reasons/as-of doğrulaması. Timestamp explicit timezone ister.

## Alanlar

| Alan | Kullanım / eksiklik davranışı |
|---|---|
| schema_version | forex-analysis-5 exact; başka sürüm reddedilir |
| symbol/timeframe/provider | Seçili canonical değerler; mt5 veya açık fixture-test-only. Yanlış kimlik ret |
| final_decision | BUY_CANDIDATE, SELL_CANDIDATE, WAIT, NO_TRADE, INSUFFICIENT_DATA, MARKET_CLOSED, STALE_DATA, PROVIDER_UNAVAILABLE |
| data_status | OK dışı plan gizler; DATA_UNAVAILABLE final enum uydurulmaz, veri alanıdır |
| trading_eligibility | BLOCKED reddi; NOT_EVALUATED broker işlem onayı değildir |
| as_of_utc/snapshot_id | >120 sn veya >5 sn gelecekte eski/geçersiz kabul; 64-hex snapshot olmadan plan yok |
| market_status | Yalnız OPEN/CLOSING_SOON display gate; UNKNOWN/DISABLED/OPENING_SOON plan açmaz |
| broker_contract | CURRENT_MT5_OBSERVED + boş missing/conflicting listeleri; symbol/broker_symbol/account_currency field trust/değerleri üst alanlarla eşleşmeli |
| spread_status | OPERATOR_APPROVED + PASS + pozitif maximum ve observed price limiti aşmıyor. Yok/UNAPPROVED asla PASS olmaz |
| account_currency/risk_balance_source | USC + HYPOTHETICAL_CAPITAL gerekli; USD/USDC/broker balance yok |
| execution_permission/analysis_mode/account mode | False + MANUAL_SIMULATION + REAL. Eksik veya true planı kapatır |
| risk_policy/lot/risk/R:R | PASS ve pozitif değerler olmadan görünür tam plan yok |
| entry_zone/SL/TP | Sayısal/yön/geometri kontrolleri; null değer uydurulmaz; sağlanırsa TP2 yönü de doğrulanır |
| indicators | EMA20/50/200, RSI14, ATR14, MACD histogram doğrudan backend; yeniden hesaplanmaz |

V5 yanıtı bid/ask içermez; chartSource prop'u mevcut 8005 MarketSnapshot'tan gelir, ayrı kimlik/time olarak gösterilir. Backend digits alanı broker_contract.fields.digits.value mevcutsa kullanılır; bilinmeyen broker precision ataması yoktur.

## Betimleyici pattern payload'ları

chart_patterns: status/role/version/source_sha256/source_commit/items. Item: name, timeframe, direction, first_known_utc, confirmation_state, age_bars, source_sha256. candlestick_patterns: name/direction, known_at_utc/confirmed/age_bars. Candlestick timeframe mevcut analysis timeframe'idir. İlk bilgi eksikse pivot zamanı onun yerine kullanılmaz. Container/item hash tutarsızsa o pattern gösterilmez. Bu yalnız backend bildiriminin tutarlılık kontrolüdür; frontend V2 kaynak baytlarını doğrulamış sayılmaz. Candlestick için bildirilmeyen SHA uydurulmaz.

AVAILABLE boş liste ile unavailable farklıdır. Sadece role=DESCRIPTIVE_ONLY ve AVAILABLE bağlam listelenir. Pattern bilgisi planVisibility kararına yön oyu eklemez. Eski 8006 yanıtı new optional alanlar olmadan okunabilir, ancak güven eksikleri nedeniyle plan görünmez. Null/private-unavailable durumunda açık uyarı vardır.

İzole proxy V3_ANALYSIS_PROXY_TARGET yalnız Vite server ortamıdır; istemci bundle'ına env/credential alınmaz. Varsayılan localhost 8006 ve mevcut allowedHosts aynıdır. Üretim reverse proxy, Android service worker ve gerçek Tailscale cihaz yolu ayrı kabul gerektirir.
