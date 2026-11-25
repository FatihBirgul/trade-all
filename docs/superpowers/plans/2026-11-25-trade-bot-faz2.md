# Trade Bot Faz 2 Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Çalışma şekli (kullanıcı/kontrolcü kararı):** Görevleri sırayla, durmadan yürüt; her Task bitince `claude/trade-bot`
> dalına push et. Yalnızca 🛑 adımlarında ve spec §13'teki durumlarda sor. Kararları `trade-bot/PROGRESS.md`'ye yaz.
> VPS çıktısı gelince Faz 1 planındaki 🛑 adımlarına (Task 4 adım 4, Task 14 adım 6–7) dön.

**Goal:** Botu telefondan güvenle denetlenebilir hale getirmek (HTTPS dışa açılış + Android ekranları) ve giriş kararını
haber penceresi, güven puanı, canlı karne ve gölge moduyla sıkılaştırmak.

**Architecture:** Aynı `trade-bot` servisine eklenir. Haber penceresi ve güven puanı, V9 adayından sonra ve portföy
kapısından önce çalışan saf fonksiyonlardır; V9 raporunu okur, V9'u değiştirmez. Karne ve gölge işlemleri SQLite'tadır.
API yalnızca 127.0.0.1'i dinlemeye devam eder; Caddy `https://<IP>.sslip.io` üzerinden ters vekillik yapar. Android,
mevcut Expo uygulamasının iskeletini kullanır; kripto V2 ekranları uygulamada gizlenir.

**Tech Stack:** Python 3.12, httpx, FastAPI, SQLite; Caddy 2 (apt) + Let's Encrypt; Expo / React Native / TypeScript, Jest.

**Spec:** `docs/superpowers/specs/2026-11-25-trade-bot-design.md` (§6.2, §6.6, §7, §8). Faz 1 planı ve kararları:
`docs/superpowers/plans/2026-11-25-trade-bot.md`, `trade-bot/PROGRESS.md`.

## Global Constraints

- Faz 1 "Global Constraints" aynen geçerli: SL'siz emir yok; martingale yok; V9 kapı ve risk mantığı değiştirilmez;
  sırlar repoya/loga/uygulamaya gitmez; testler ağsız çalışır; Exness alan adları yalnızca `exness/schema.py`'de.
- Haber penceresi (spec §6.6): yüksek etkili haberden 30 dk önce ve 30 dk sonra, o para birimini içeren sembollerde yeni
  bot işlemi yok. USD haberleri BTC/ETH'yi de kapsar. Açık işlemler stoplarıyla devam eder. Takvim 6 saatte bir yenilenir;
  24 saatten uzun süre alınamazsa bot çalışmaya devam eder ve kullanıcıya uyarı gider.
- Güven puanı (spec §6.2): 0–100; puan < 40 → işlem açılmaz, "gözlem" kaydedilir; 40–60 → 0.5×, 60–80 → 0.75×,
  ≥ 80 → 1.0× işlem başı risk. §6.3 limitleri hiçbir durumda aşılmaz. Ağırlıklar ve eşikler ayarlardan değişir.
- Sert vetolar puandan bağımsızdır: ters yönlü onay, net R/R < 1.5, spread/seans (V9); haber penceresi, portföy limitleri (bot).
- Karne (spec §6.2): bir strateji ≥ 20 işlemde ortalama R < 0 ise kendiliğinden duraklatılır + bildirim; kullanıcı tekrar açabilir.
  Modül ağırlıkları otomatik değişmez. Gölge modu: 20 sanal işlem; ortalama R > 0 ise kullanıcı onayıyla canlıya alınır.
  Mevcut dört V9 stratejisi gölge modunu atlar.
- Dışa açılış (kontrolcü kararı): alan adı ve Tailscale yok. Caddy + Let's Encrypt ile `<VPS_IP>.sslip.io`; API bearer token +
  eşleştirme koduyla korunur; servis 127.0.0.1:8090'da kalır.
- Kullanıcı teknik değildir: sunucu adımları tek komut, ekran metinleri Türkçe ve açıklayıcı olmalı.
- Android: mevcut `typecheck`, `lint`, `test`, `doctor:local`, `expo export` CI adımları geçmeye devam eder.

## Review Focus

1. **Takvim alınamıyor ya da bozuk geliyor** → bot işlem açmaya devam eder (spec kararı), son geçerli takvim kullanılır,
   24 saat sonra tek uyarı gider; her taramada uyarı yağmaz. Test: Task 2 `test_stale_calendar_warns_once_and_keeps_trading`.
2. **Haber saati yerel saat/yaz saati kaymasıyla yanlış okunuyor** → olay zamanı ofsetli ISO'dan UTC'ye çevrilir; ofsetsiz
   kayıt yok sayılır. Test: Task 2 `test_event_times_are_normalised_to_utc`.
3. **Puan çarpanı lotu en küçük lotun altına düşürüyor** → işlem açılmaz, gözlem kaydedilir; lot yukarı yuvarlanmaz.
   Test: Task 3 `test_multiplier_below_min_lot_becomes_observation`.
4. **Duraklatılmış strateji sessizce işlem açmaya devam ediyor / sessizce susuyor** → duraklatma kalıcıdır (yeniden
   başlatmada korunur), tek bildirim gider, strateji gölgede izlenmeye devam eder. Test: Task 5 `test_auto_pause_persists_and_notifies_once`.
5. **API internete açıkken eşleştirme kodu deneniyor** → 5 hatalı denemede kod iptal; `/health` dışında her uç token ister;
   HTTP isteği HTTPS'e yönlenir. Test: Task 1 `test_caddyfile_proxies_only_to_loopback_and_redirects_http`, Faz 1 `test_pair_code_expires_and_locks_after_failures`.

---

### Task 1: HTTPS dışa açılış (Caddy + sslip.io) ve eşleştirme komutu

**Files:**
- Create: `trade-bot/deploy/setup-https.sh`, `trade-bot/deploy/Caddyfile.template`, `trade-bot/deploy/tradebot-pair`, `trade-bot/tests/deploy/test_https.py`
- Modify: `trade-bot/deploy/install.sh` (pair komutunu `/usr/local/bin/tradebot-pair` olarak kurar), `trade-bot/deploy/bootstrap.sh` (HTTPS adımı + uygulama adresi), `trade-bot/deploy/README.md`

**Interfaces:**
- Produces: `setup-https.sh` — `VPS_IP` (verilmezse `bootstrap.sh`'deki `public_ip` ile aynı yöntem) → `HOST=<a-b-c-d>.sslip.io`
  (noktalar tire); `apt-get install -y caddy`; `/etc/caddy/Caddyfile`'ı şablondan yazar; `ufw` etkinse 80/443 açar;
  `systemctl enable --now caddy` + `reload`; sonunda `https://HOST` yazar. `CADDY_DRY=1` ile yalnızca Caddyfile'ı
  `CADDYFILE` yoluna üretir (test). `tradebot-pair`: env dosyasını yükleyip `python -m tradebot pair` çalıştırır,
  kodu ve uygulama adresini yazar.
- Caddyfile: tek site `HOST`; `reverse_proxy 127.0.0.1:8090`; `encode zstd gzip`; `request_body { max_size 64KB }`;
  `header` ile `Strict-Transport-Security "max-age=31536000"`, `X-Content-Type-Options nosniff`, `-Server`; erişim logu yok
  (token sorgu parametresi loga düşmesin).

- [ ] **Step 1: Failing tests** — `test_host_from_ip` (`203.0.113.7` → `203-0-113-7.sslip.io`), `test_caddyfile_proxies_only_to_loopback_and_redirects_http`
  (üretilen dosyada `reverse_proxy 127.0.0.1:8090`, başka upstream yok, `http://` sitesi/`auto_https off` yok, `log` yönergesi yok,
  HSTS var), `test_invalid_ip_rejected` (`VPS_IP=evil.com` → çıkış kodu ≠ 0), `test_pair_wrapper_never_echoes_env`.
- [ ] **Step 2:** FAIL → **Step 3:** uygula; `shellcheck` temiz → **Step 4:** PASS.
- [ ] **Step 5:** `bootstrap.sh`: keşiften önce `setup-https.sh` çağrılır; "Bitti" bölümüne "Uygulama adresi: https://HOST" ve
  "Eşleştirme kodu için: `tradebot-pair`" eklenir. Mevcut bootstrap testleri `BOOTSTRAP_DRY` ile geçmeye devam eder.
- [ ] **Step 6:** Commit `feat(deploy): caddy https on sslip.io and pairing command`, push.

### Task 2: Haber takvimi ve haber penceresi

**Files:**
- Create: `trade-bot/tradebot/news/{__init__,calendar,gate}.py`, `trade-bot/tests/news/{test_calendar,test_gate}.py`, `trade-bot/tests/news/fixtures/ff_calendar_thisweek.json`
- Modify: `trade-bot/tradebot/config.py` (`NewsSettings`), `trade-bot/tradebot/app.py` (tarama + kalp atışı), `trade-bot/tradebot/api/routes.py` (`GET /news`), `trade-bot/tradebot/runtime.py`

**Interfaces:**
- Produces: `NewsSettings(enabled: bool = True, window_minutes: int = 30 ∈ [5, 120])`, `BotSettings.news`.
  `NewsEvent(currency: str, title: str, at: float, impact: Literal['high','medium','low','holiday'])`.
  `parse_calendar(raw: list) -> list[NewsEvent]` (alanlar: `country` → para birimi, `date` ofsetli ISO → UTC epoch, `impact`;
  bozuk kayıt atlanır). `NewsCalendar(repo, *, transport=None, clock, url=FF_URL)` — `async refresh() -> bool`
  (başarılıysa SQLite `settings['news_calendar'] = {fetched_at, events}`), `events() -> list[NewsEvent]`, `age() -> float | None`,
  `REFRESH_SECONDS = 6*3600`, `STALE_SECONDS = 24*3600`. `FF_URL = 'https://nfs.faireconomy.media/ff_calendar_thisweek.json'`.
  `blocking_event(instrument: Instrument, events, *, now: float, window_minutes: int) -> NewsEvent | None` — yalnızca `impact == 'high'`;
  sembolün `currency_base`/`currency_profit` kümesiyle eşleşir (BTCUSD → {BTC, USD}; XAUUSD → {XAU, USD}); `|at − now| ≤ window`.
- Bot: tarama sırasında haber penceresindeki sembol analiz edilmeden atlanır, `ScanSummary.news_blocked` artar (bildirim yok).
  `heartbeat`: takvim `REFRESH_SECONDS`'tan eskiyse yeniler; `STALE_SECONDS`'tan eskiyse günde bir kez `news_unavailable`
  uyarısı + bildirim. Not: V9'un `information_provider` yolu kullanılmaz; V9 `MacroEvent` yalnızca USD/EUR/GBP/JPY kabul eder
  ve V9 değiştirilemez. Veto bot katmanında tüm para birimleri için uygulanır (PROGRESS'e yaz).

- [ ] **Step 1: Failing tests** — `test_parse_keeps_valid_and_skips_malformed`, `test_event_times_are_normalised_to_utc`
  (`2026-11-27T08:30:00-05:00` → 13:30 UTC), `test_only_high_impact_blocks`, `test_window_is_symmetric_30_minutes`
  (29:59 önce/sonra engeller, 30:01 engellemez), `test_usd_news_blocks_btc_eth_and_gold_not_eurgbp`,
  `test_refresh_caches_and_survives_restart`, `test_failed_refresh_keeps_last_good_calendar`,
  `test_stale_calendar_warns_once_and_keeps_trading`, `test_scan_skips_symbol_in_news_window_without_notification`,
  `test_disabled_news_filter_blocks_nothing`, `test_open_positions_still_managed_during_news`.
- [ ] **Step 2–4:** FAIL → uygula → PASS.
- [ ] **Step 5:** Commit `feat(news): economic calendar and news window veto`, push.

### Task 3: Güven puanı ve risk çarpanı

**Files:**
- Create: `trade-bot/tradebot/signals/fusion.py`, `trade-bot/tests/signals/test_fusion.py`
- Modify: `trade-bot/tradebot/config.py` (`FusionSettings`), `trade-bot/tradebot/signals/adapter.py` (`Evaluation.report`), `trade-bot/tradebot/app.py` (`_consider`), `trade-bot/tradebot/store/{schema.sql,db.py,repo.py}` (`trades.votes_json`, `score` doldurulur)

**Interfaces:**
- Produces: `Vote(module: str, value: Literal[1, 0, -1], detail: str)` (1 destek, −1 karşı, 0 çekimser).
  `collect_votes(report, side, *, now, kind) -> list[Vote]` — modüller ve kaynakları: `mtf` (`report.mtf.source_context.higher_timeframe_alignment`:
  yön aynı ve `agreement_ratio ≥ 0.5` → 1; ters → −1), `regime` (`report.regime.direction`), `candle_pattern` (son 5 mumda onaylı,
  aynı yönlü formasyon → 1; ters → −1), `chart_pattern` (`chart_patterns.patterns` yönü), `structure`
  (`market_structure.v5_pivots.trend` / `break_of_structure`), `momentum` (`rsi14_wilder` ve `macd_histogram` yönle uyumlu),
  `confluence` (`bullish_strength` vs `bearish_strength`), `other_strategies` (tetikleyen dışında aynı yönde CONFIRMED),
  `session` (forex/metal: Londra/NY/overlap → 1, Asya → 0, seans dışı → −1; kripto → 0).
  `FusionSettings(enabled=True, min_score=40 ∈[0,100], weights: dict[str, float] (varsayılan hepsi 1.0; mtf ve regime 2.0),
  tiers=((40, 0.5), (60, 0.75), (80, 1.0)))`. `score(votes, weights) -> float` =
  `100 × Σ wᵢ·sᵢ / Σ wᵢ`, `sᵢ = {1: 1.0, 0: 0.5, −1: 0.0}`; ağırlığı 0 olan modül sayılmaz; hiç modül yoksa 50.
  `risk_multiplier(score, settings) -> float | None` (eşik altı → None). `scale_lots(lots, multiplier, instrument) -> float | None`
  (adıma aşağı yuvarla; `volume_min` altı → None).
- `_consider`: aday → oylar → puan → `None` ise `signal_observed` olayı + gölge kaydı (Task 4), emir yok; değilse lot ve
  `risk_amount` çarpanla ölçeklenir. `Trade.score` ve `votes_json` dolum sırasında emir kaydından yazılır.

- [ ] **Step 1: Failing tests** — `test_all_support_is_100_all_against_is_0_all_abstain_is_50`, `test_weights_shift_score`,
  `test_zero_weight_module_ignored`, `test_tiers` (39.9 → None; 40 → 0.5; 59.9 → 0.5; 60 → 0.75; 80 → 1.0),
  `test_multiplier_below_min_lot_becomes_observation`, `test_scaled_lots_round_down_to_step`,
  `test_votes_from_buy_fixture_report` (V9 BUY fixture: `mtf`, `regime`, `momentum` = 1), `test_sell_fixture_mirrors`,
  `test_low_score_records_observation_and_sends_no_order` (uçtan uca, `min_score=101` benzeri ayarla),
  `test_filled_trade_stores_score_and_votes`, `test_fusion_disabled_uses_full_risk`.
- [ ] **Step 2–4:** FAIL → uygula → PASS. **Step 5:** Commit `feat(signals): confidence score and risk multiplier`, push.

### Task 4: Strateji kipleri, tüm CONFIRMED stratejiler ve gölge işlemleri

**Files:**
- Create: `trade-bot/tradebot/signals/shadow.py`, `trade-bot/tests/signals/test_shadow.py`
- Modify: `trade-bot/tradebot/config.py` (`BotSettings.strategy_modes`), `trade-bot/tradebot/signals/adapter.py` (`evaluate_all`), `trade-bot/tradebot/app.py`, `trade-bot/tradebot/store/{schema.sql,repo.py}` (`shadow_trades`)

**Interfaces:**
- Produces: `BotSettings.strategy_modes: dict[str, Literal['live','shadow','off']]` (eksik strateji = `live`; `enabled_strategies`
  alanı geriye uyum için kalır: listede olmayan strateji `off` sayılır). `evaluate_all(provider, symbol, *, modes, ...) -> list[Evaluation]`:
  önce `off` olmayan tüm stratejilerle analiz; yönlendirilen strateji aday verdiyse o; vermediyse ve raporda başka CONFIRMED
  strateji varsa her biri için `enabled_strategies=[o]` ile yeniden analiz (en çok 3 ek çağrı). Her `Evaluation` adayının
  stratejisinin kipini taşır (`mode`).
- `shadow_trades(id, symbol, side, strategy_id, setup_id UNIQUE, reason CHECK IN ('shadow','low_score','paused'), entry, sl, tp,
  score, opened_at, closed_at, result_r)`. `ShadowBook(repo)` — `open(candidate, reason, score, now) -> bool` (aynı setup bir kez),
  `resolve(symbol, bars: list[dict], now) -> list[closed]`: açılıştan sonraki kapanmış M15 mumlarında önce SL (`low ≤ sl` / `high ≥ sl`)
  → −1R; değilse TP → `+|tp−entry|/|entry−sl|` R; aynı mumda ikisi de → SL (temkinli); 96 mum (24 saat) dolarsa son kapanışa
  göre R. `stats(strategy_id) -> dict(trades, avg_r, win_rate)`.
- Bot: kipi `shadow` olan stratejinin adayı ve puanı eşik altı kalan aday emir açmaz, `ShadowBook.open` ile kaydedilir;
  her taramada o sembolün mumlarıyla `resolve` çalışır.

- [ ] **Step 1: Failing tests** — `test_modes_default_live_and_off_excluded`, `test_second_confirmed_strategy_tried_when_first_fails_gate`,
  `test_shadow_strategy_never_sends_order`, `test_shadow_stop_first_on_ambiguous_bar`, `test_shadow_tp_gives_positive_r`,
  `test_shadow_expires_after_96_bars_at_market`, `test_shadow_setup_recorded_once`, `test_shadow_stats`.
- [ ] **Step 2–4:** FAIL → uygula → PASS. **Step 5:** Commit `feat(signals): strategy modes and shadow trades`, push.

### Task 5: Canlı karne, otomatik duraklatma ve API

**Files:**
- Create: `trade-bot/tradebot/signals/scorecard.py`, `trade-bot/tests/signals/test_scorecard.py`
- Modify: `trade-bot/tradebot/config.py` (`FusionSettings.pause_min_trades=20`, `pause_avg_r=0.0`), `trade-bot/tradebot/app.py` (işlem kapanınca denetim), `trade-bot/tradebot/api/routes.py` (`GET /scorecard`, `POST /strategies/{id}/mode`), `trade-bot/tests/api/test_api.py`

**Interfaces:**
- Produces: `trade_r(trade) -> float | None` = `pnl / risk_amount` (risk bilinmiyorsa None). `scorecard(repo) -> dict`:
  `strategies: {id: {mode, live: {trades, wins, win_rate, avg_r, profit_factor}, shadow: {trades, avg_r, win_rate}}}`,
  `modules: {module: {support: {trades, avg_r}, against: {trades, avg_r}}}` (kapalı bot işlemlerinin `votes_json`'undan).
  `strategies_to_pause(repo, settings) -> list[str]` (kip `live`, `trades ≥ pause_min_trades`, `avg_r < pause_avg_r`).
- Bot: her `trade_closed` sonrası ve kalp atışında denetler; duraklatılan stratejinin kipi `shadow` yapılır (izlenmeye devam eder),
  `strategy_paused` hata olayı + bildirim bir kez gider. Kullanıcı `POST /strategies/{id}/mode {mode}` ile geri açar; gölgedeki
  bir stratejiyi `live` yapmak için gövdede `confirm: true` gerekir (bilinçli onay). `GET /scorecard` karneyi döndürür.

- [ ] **Step 1: Failing tests** — `test_trade_r`, `test_scorecard_groups_by_strategy_and_module`, `test_profit_factor_and_win_rate`,
  `test_auto_pause_needs_20_trades_and_negative_avg_r`, `test_auto_pause_persists_and_notifies_once`,
  `test_paused_strategy_continues_in_shadow`, `test_mode_endpoint_requires_token_and_confirm_for_live`, `test_scorecard_endpoint`.
- [ ] **Step 2–4:** FAIL → uygula → PASS. **Step 5:** Commit `feat(signals): live scorecard and auto-pause`, push.

---

## Android (`trade-ai-android/`)

Mevcut uygulama Expo SDK 58 / expo-router, durum için React Context (`src/state.tsx`), veri için enjekte edilebilir
`transport: typeof fetch` kullanan `src/api/client.ts`. Bu istemci `/api/v2` önekini ve V2 OpenAPI doğrulamasını zorunlu
kıldığı için **bot API'si ayrı bir istemciyle** (`src/bot/`) konuşur; eski kripto kodu ve testleri yerinde kalır, ekranları
sekmelerden gizlenir (spec §8). Ortak parçalar yeniden kullanılır: `src/ui.tsx`, `src/theme.tsx`, `src/resource.ts`,
`gatewayOrigin` ve `money` (`src/domain/safety.ts`), `ApiError`. Test kalıbı: `__tests__/*.test.ts(x)`, `transport` olarak
`jest.fn()`, `expo-secure-store` dosya başında mock'lanır, ekran testlerinde `ThemeProvider` sarmalı ve Türkçe metin doğrulaması.

### Task 6: Bot API istemcisi ve bağlantı durumu

**Files:**
- Create: `src/bot/{types.ts,client.ts,storage.ts,state.tsx}`, `__tests__/botClient.test.ts`, `__tests__/botState.test.tsx`
- Modify: `app/_layout.tsx` (`BotProvider`, `AppProvider`'ın içine)

**Interfaces:**
- Produces: `BotConfig = { origin: string; token: string; pairedAt: number }` (SecureStore anahtarı `trade_bot`).
  `BotError extends ApiError` + `detail?: string` (sunucunun Türkçe `detail` metni). `pairBot(origin, code, transport?) -> Promise<BotConfig>`
  (`origin` `gatewayOrigin` ile doğrulanır: yalnızca `https:`; kod `/^[0-9]{6}$/`; `POST {origin}/pair`).
  `createBotApi(config: BotConfig | null, transport = fetch, onUnauthorized?)` → `health()`, `status()`, `positions()`,
  `patchPosition(id, { sl?, tp?, manage? })`, `closePosition(id, volume?)`, `stop()`, `resume(confirmHalt?: boolean)`,
  `closeAll()` (gövde `{ confirm: "CLOSE-ALL" }`), `events(after?: number)`, `registerDevice(expoToken)`. Kurallar: `Authorization: Bearer`,
  15 sn zaman aşımı, `redirect: "error"`, değişiklik yapan istekler asla yeniden denenmez (ağ hatası → `NETWORK`, `uncertain = true`),
  401 → `UNAUTHORIZED` + `onUnauthorized`, 409/422 → `BotError(detail)`.
  Tipler (`types.ts`) bot API yanıtlarının birebir karşılığı: `BotStatus`, `BotPosition`, `BotEvent`, `BotHealth`.
- `BotProvider` / `useBot()` → `{ phase: "unconfigured" | "checking" | "ready" | "offline" | "revoked"; config; status; positions; events;
  error; heartbeatStale: boolean; api; pair(origin, code); disconnect(); refresh() }`. Uygulama öndeyken durum + pozisyonlar 5 sn'de,
  olaylar 15 sn'de bir yenilenir (`AppState` arka planda durur). `heartbeatStale` = `status.heartbeat_at` 5 dakikadan eski ya da
  5 dakikadır yanıt alınamıyor (spec §7). 401 → `revoked`, yapılandırma silinir.

- [ ] **Step 1: Failing tests** — `pairs with code and stores token`, `rejects http and malformed code without network`,
  `sends bearer token and parses status`, `mutation network error is uncertain and not retried`, `401 calls onUnauthorized`,
  `409 carries server detail`, `closeAll sends exact confirm phrase`; durum: `starts unconfigured`, `becomes ready after pair`,
  `marks heartbeat stale after 5 minutes`, `goes revoked on 401 and clears storage`, `stops polling in background`.
- [ ] **Step 2–4:** FAIL → uygula → `npm run typecheck && npm run lint && npm test` PASS. **Step 5:** Commit `feat(android): trade bot api client and state`, push.

### Task 7: Sekmeler, Bağlantı ekranı ve eski ekranların gizlenmesi

**Files:**
- Create: `app/(tabs)/connection.tsx`, `__tests__/botConnection.test.tsx`
- Rename: `app/(tabs)/index.tsx` → `app/(tabs)/legacy.tsx` (eski kripto ana sayfası; içerik değişmez)
- Modify: `app/(tabs)/_layout.tsx`, `__tests__/{tabNavigation,dashboard,demoFlow}.test.tsx` (içe aktarma yolu ve sekme beklentileri),
  `package.json` + `app.json` + `package-lock.json` (sürüm `0.8.0`, `versionCode` 17), `app.json` (`name`: `Trade Bot`)

**Interfaces:**
- Sekmeler (görünür): `index` "Panel", `positions` "Pozisyonlar", `events` "Bildirimler", `connection` "Bağlantı".
  Gizli (`href: null`): `legacy`, `analysis`, `portfolios`, `scanner`, `settings`. Yığın ekranları (`detail`, `result`, …) dokunulmaz.
- `connection.tsx`: sunucu adresi (`https://…sslip.io`), 6 haneli eşleştirme kodu, "Bağlan"; bağlıyken adres + "Bağlantıyı sil" + tema düğmesi.
  Kodun sunucuda `tradebot-pair` ile üretildiğini anlatan kısa yardım metni. Hata metinleri `BotError.detail` ya da `ApiError` mesajı.

- [ ] **Step 1: Failing tests** — `tabs show bot screens and hide legacy ones`, `connection screen pairs and shows connected state`,
  `connection screen shows server error text`, `disconnect clears config`. Eski testler yeni dosya yoluyla geçmeye devam eder.
- [ ] **Step 2–4:** FAIL → uygula → typecheck/lint/test + `npm run doctor:local` PASS. **Step 5:** Commit `feat(android): bot tabs and connection screen`, push.

### Task 8: Panel ve Durdur / Devam / Hepsini kapat

**Files:**
- Create: `app/(tabs)/index.tsx`, `src/bot/presentation.ts`, `__tests__/botPanel.test.tsx`, `__tests__/botPresentation.test.ts`

**Interfaces:**
- `presentation.ts` (saf): `botStateText(status) -> { label: string; tone: "ok" | "warn" | "bad" }` — öncelik sırası: `halted`
  ("Durdu: toplam kayıp sınırı"), `stopped` ("Durduruldu"), `!stream_connected` ("Exness bağlantısı yok"), `dry_run`
  ("Deneme modu: emir gönderilmiyor"), aksi halde "Çalışıyor". `pnlText(value, currency)`, `agoText(epochSeconds, now)`.
- Panel: bakiye, equity, bugünkü kâr/zarar (bot / elle / toplam), açık işlem sayıları, bot durumu, son tarama, kalp atışı uyarı kartı
  (`heartbeatStale`: "Bottan 5 dakikadır haber yok"). Düğmeler: "Durdur" (onay), "Devam" (`halted` ise ikinci, açık uyarılı onay →
  `resume(true)`), "Hepsini kapat" (yıkıcı onay → `closeAll()`). Onaylar `Alert.alert` ile. Bağlı değilken Bağlantı sekmesine yönlendiren boş durum.

- [ ] **Step 1: Failing tests** — `state text priority`, `shows balance equity and pnl split`, `stop asks for confirmation then calls api`,
  `resume after halt requires explicit confirmation and sends confirm_halt`, `close all requires confirmation`,
  `stale heartbeat card is shown`, `unconfigured shows link to connection`.
- [ ] **Step 2–4:** FAIL → uygula → PASS. **Step 5:** Commit `feat(android): panel with stop/resume`, push.

### Task 9: Pozisyonlar

**Files:**
- Create: `app/(tabs)/positions.tsx`, `src/bot/PositionCard.tsx`, `__tests__/botPositions.test.tsx`

**Interfaces:**
- Her pozisyon kartı: sembol, yön, lot, giriş, anlık fiyat, SL, TP, kâr/zarar, R katı, köken etiketi ("Bot" / "Elle"), "SL kullanıcı tarafından
  ayarlandı" notu. İşlemler: "Kapat" (onay → `closePosition(id)`), "SL/TP düzenle" (iki sayı girişi; boş alan gönderilmez; pozitif sayı
  doğrulaması istemcide, kalan doğrulama sunucuda), "Kademeli stop" anahtarı (`patchPosition(id, { manage })`). 409 → sunucu metni gösterilir.

- [ ] **Step 1: Failing tests** — `lists positions with pnl and r multiple`, `close asks for confirmation`, `edit sends only changed fields`,
  `rejects non-positive stop before network`, `manage toggle patches position`, `conflict shows server message`, `empty state`.
- [ ] **Step 2–4:** FAIL → uygula → PASS. **Step 5:** Commit `feat(android): positions screen`, push.

### Task 10: Bildirimler (olay akışı, yerel bildirim, push kaydı)

**Files:**
- Create: `app/(tabs)/events.tsx`, `src/bot/notifications.ts`, `__tests__/botEvents.test.tsx`, `__tests__/botNotifications.test.ts`
- Modify: `package.json` / `package-lock.json` / `app.json` (`expo-notifications`, `npx expo install` ile SDK 58 uyumlu sürüm; eklenti ve
  `POST_NOTIFICATIONS` izni), `src/bot/state.tsx`

**Interfaces:**
- `events.tsx`: `/events` akışı, en yeni üstte; tür etiketi ve renk (`error` kırmızı, `warning` altın), Türkçe zaman.
- `notifications.ts`: `importantKinds` = `trade_opened, trade_closed, sl_breakeven, sl_missing, tp_lost, daily_limit, bot_halted,
  connection_lost, order_rejected, auth_error, news_unavailable, strategy_paused`. `notifyNewEvents(events, lastSeenId, schedule)` →
  uygulama açıkken gelen önemli olaylar için yerel bildirim; `notifyHeartbeatLost(schedule)` kalp atışı 5 dakikayı aşınca bir kez.
  `registerPush(api, getToken)` — Expo push token alınabiliyorsa `POST /devices`; alınamıyorsa (FCM yapılandırılmamış) sessizce `false`.
- 🛑 **Uzak (uygulama kapalıyken) push** FCM gerektirir: kullanıcıdan Firebase projesi `google-services.json` ve Expo proje kimliği istenir.
  Gelene kadar uygulama açıkken yerel bildirim + olay akışı çalışır; sunucu tarafı (Faz 1 `ExpoNotifier`) hazırdır.

- [ ] **Step 1: Failing tests** — `lists events newest first with turkish labels`, `only important kinds notify`, `does not renotify seen events`,
  `heartbeat loss notifies once until recovered`, `registerPush posts token when available and returns false otherwise`.
- [ ] **Step 2–4:** FAIL → uygula → typecheck/lint/test, `doctor:local`, `expo export` PASS. **Step 5:** Commit `feat(android): events and notifications`, push.

### Task 11: Faz sonu

- [ ] **Step 1:** Tüm paketler: `pytest trade-bot`, V9 `check_sources` + `run_suite engine`, Android `typecheck/lint/test/doctor/export`.
- [ ] **Step 2:** `requesting-code-review` ile bağımsız inceleme (Faz 2 commit aralığı); Kritik ve Önemli bulguları düzelt, gerileme testleri ekle.
- [ ] **Step 3:** `PROGRESS.md` güncelle; `[apk]` içeren commit ile iç test APK'sını derlet (Actions → `trade-ai-internal-apk`).
- [ ] **Step 4:** PR aç; 🛑 `main`'e birleştirme için kontrolcü onayı.
