# Trade Bot Faz 3 — Uygulama Planı

> Kaynak: `docs/superpowers/specs/2026-11-25-trade-bot-design.md` §6.2, §6.4, §8, §10 (3. hafta).
> Yürütme: görevler sırayla, durmadan; her Task sonunda test + commit + push. Faz sonunda bağımsız inceleme.
> Bot deneme modunda kalır; canlıya geçiş yalnızca kullanıcının açık onayıyla.

**Goal:** Strateji ve oy modüllerini tek bir ortak arayüze taşımak, yeni stratejileri gölge modunda eklemek ve
Android'e Raporlar, Ayarlar ve Elle işlem ekranlarını kazandırmak; APK'yı kalıcı bir anahtarla imzalamak.

## Global Constraints
- V9'un kapı ve risk mantığı değişmez (`trade-ai-unified/` bu fazda değişmez).
- Hiçbir kod yolu SL'siz emir göndermez. Yeni stratejiler **varsayılan olarak gölgededir**; canlıya almak için
  hem kullanıcı onayı hem de karne koşulu (≥ 20 sanal işlem, ortalama R > 0) gerekir.
- Yeni strateji lotu yalnızca risk bütçesinden hesaplanır, adıma aşağı yuvarlanır; en küçük lot bütçeyi aşıyorsa aday yoktur.
- Güven puanı riski yalnızca azaltır. Portföy kapısı ve haber penceresi her aday için geçerlidir.
- Değişiklik istekleri uygulamada asla kendiliğinden yinelenmez; yıkıcı ya da gerçek para etkileyen her işlem onaylıdır.
- Sırlar repoya, loglara ve uygulamaya girmez. Testler ağ gerektirmez.

## Review Focus
1. Yeni bir strateji onaysız ya da karne koşulu sağlanmadan canlı emir gönderebilir mi?
2. Ortak arayüze taşıma, mevcut oyların sonucunu değiştirdi mi (aynı rapor → aynı puan)?
3. Yeni stratejilerde bakış-ileri (lookahead) hatası: yalnızca kapanmış mumlar; stop/hedef tick adımına yuvarlı ve doğru tarafta.
4. Elle işlem: lot önerisi gerçek equity ve risk %'siyle; SL zorunlu; çift gönderim yok (`client_id`).
5. Ayarlar: sınırlar sunucuda doğrulanıyor; uygulama bayat kopya göndermiyor; canlıya geçiş ayrı onaylı.

## Sunucu (`trade-bot/`)

### Task 1: Ortak modül arayüzü
**Files:** Create `tradebot/signals/modules/{__init__,base}.py`, `modules/votes/*.py` (her oy modülü bir dosya),
`tests/signals/test_modules.py`. Modify `tradebot/signals/fusion.py`.
- `base.py`: `Context(symbol, side, report, bars, quote, instrument, now)`, `Vote`, `Signal(side, entry, stop, target, reason)`,
  `Module` protokolü (`id`, `kind: "vote" | "strategy"`, `evaluate(context) -> Vote | Signal | None`), `register()`, `modules(kind)`.
- Mevcut oy hesapları (`mtf`, `regime`, `pattern`, `divergence`, `structure`, `session`, `strategies`) dosya başına bir modüle taşınır;
  `fusion.collect_votes` kayıt defterini dolaşır. Davranış birebir aynı kalır (altın test: taşımadan önceki/sonraki oylar eşit).
- Tests: `registry lists every fusion module once`, `votes identical to pre-refactor for BUY/SELL fixtures`,
  `module raising is an abstain, not a crash`, `adding a module is one file and one register call`.

### Task 2: Yeni stratejiler (gölge)
**Files:** Create `tradebot/signals/modules/strategies/{ema_pullback,donchian_breakout}.py`, `tradebot/signals/custom.py`,
`tests/signals/test_custom_strategies.py`. Modify `tradebot/config.py`, `tradebot/app.py`, `tradebot/api/routes.py`, `tradebot/signals/scorecard.py`.
- `tb_ema_pullback_v1`: H1 eğilimi (EMA50/EMA200) yönünde, M15'te EMA20'ye geri çekilip eğilim yönünde kapanış. SL: son salınım ∓ 0.5 ATR.
- `tb_donchian_breakout_v1`: M15 kapanışı 20 mumluk kanalın dışında, ATR genişlemiş, H1 eğilimi aynı yönde. SL: 1.5 ATR.
- `custom.evaluate(provider, symbol, …) -> list[Evaluation]`: yalnızca kapanmış mumlar; net R/R ≥ 1.5 (spread dahil) değilse aday yok;
  lot = risk bütçesi / lot başı zarar, adıma aşağı; `setup_id` = strateji + sembol + son mum zamanı.
- `strategy_mode`: V9 dışı stratejiler için varsayılan `shadow`. `POST /strategies/{id}/mode` canlıya alırken V9 dışı stratejide
  karne koşulunu da ister (≥ `pause_min_trades` gölge işlem ve ortalama R > 0), yoksa 409.
- `GET /strategies`: kimlik, kaynak (`v9`/`custom`), kip, gölge karnesi, `can_go_live`.
- Tests: sentetik mumlarla her stratejinin sinyal verdiği/vermediği durumlar, lookahead yok, stop doğru tarafta, lot bütçeyi aşmaz,
  varsayılan gölge → emir yok, karne koşulu olmadan canlıya alınamaz, V9 stratejileri etkilenmez.

### Task 3: Elle işlem önizlemesi ve rapor ayrıntısı
**Files:** Modify `tradebot/api/{routes,models}.py`; tests `tests/api/test_manual_preview.py`.
- `POST /trades/preview {symbol, side, sl_distance, tp_distance?, risk_pct?}` → önerilen lot, zarar/kâr tutarı, R/R, giriş fiyatı, uyarılar; emir göndermez.
- `GET /symbols` → evrendeki semboller (ad, tür, açık mı, lot adımı/en küçük lot, taze fiyat var mı).
- Tests: öneri risk %'sini aşmaz, en küçük lot bütçeyi aşıyorsa uyarı, kapalı piyasa/fiyat yok → 409, yetkisiz 401.

## Android (`trade-ai-android/`)

### Task 4: Raporlar
**Files:** Create `app/(tabs)/reports.tsx`, `src/bot/reports.ts`, tests. Modify `app/(tabs)/_layout.tsx`, `src/bot/{client,types}.ts`.
- Gün/hafta/ay seçimi; bot / elle / toplam K/Z, işlem sayısı, kazanma oranı, en büyük düşüş; strateji ve sembol kırılımı; karne (strateji kipi, canlı ve gölge ortalama R); son işlemler.

### Task 5: Ayarlar
**Files:** Create `app/(tabs)/settings-bot.tsx` (sekme adı "Ayarlar"), `src/bot/settingsForm.ts`, tests.
- Risk %, açık işlem sınırı, günlük/toplam kayıp %, haber penceresi, güven puanı eşikleri, kademeli stop anahtarları, semboller, strateji kipleri.
- Kaydet: ayarlar yeniden okunur, yalnızca değişen alanlar uygulanır, eski → yeni onayı; riski artıran değişiklik ayrıca uyarılır.
  Strateji canlıya alma ve canlı moda geçiş kendi onaylı uç noktalarını kullanır. Bağlantı ekranı Ayarlar'dan açılır.

### Task 6: Elle işlem
**Files:** Create `app/manual-trade.tsx`, `src/bot/manualTrade.ts`, tests.
- Sembol, yön, SL mesafesi (zorunlu), TP mesafesi, risk %; canlı önizleme (lot, zarar tutarı, R/R); lot düzenlenebilir.
- Gönder: önizleme özetiyle onay; `client_id` ile tek gönderim; ağ hatasında "sonuç belirsiz", yeniden gönderim yok.

### Task 7: İmzalı APK
**Files:** Modify `.github/workflows/android-apk.yml`, `trade-ai-android/README.md`.
- `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD` tanımlıysa kalıcı anahtarla imzalar; değilse bugünkü geçici imzayla derler ve bunu açıkça yazar.
- 🛑 Anahtar deposunu kullanıcı üretir ve Secrets'a ekler (anahtar kaybolursa uygulama güncellenemez).

### Task 8: Faz sonu
Tüm paketler; `requesting-code-review` ile bağımsız inceleme; düzeltmeler; `PROGRESS.md`; `[apk]`; PR; 🛑 `main` için onay.
