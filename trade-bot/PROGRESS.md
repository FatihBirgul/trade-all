# Trade Bot — ilerleme kaydi

Uygulayicinin kendi verdigi kararlar ve kesif bulgulari, tarih sirasiyla tek satir.

## 2026-11-25
- `executing-plans` skill'i oturumda yoktu; plan ayni duzenle (test → kod → commit) dogrudan yurutuldu.
- Gelistirme ortami Python 3.12 venv (`trade-bot/.venv`), VPS ile ayni surum. V9 testleri CI'da 3.11'de kalir.
- Exness dokumanlari okunabildi (OpenAPI 1.0.2, `www.exness-api.com`); asagidaki "API bulgulari" buna dayanir, canli kesifle dogrulanacak.
- Imza: payload `json.dumps(separators=(',',':'))`, alan sirasi `api_key, idempotency_key, timestamp, sign_version, method, path, body_hash`. Resmi Python ornegi ve dokumandaki test vektoru ile birebir dogrulandi (`tests/exness/test_signing.py::test_official_test_vector`); canli kesifte yalnizca anahtar yukleme dogrulanacak.
- Ozel anahtar: Exness'in urettigi 128 hex (tohum + acik anahtar) ve PKCS#8 PEM desteklenir; 64 hex / base64 32 bayt da kabul edilir.
- Host: `EXNESS_AP_HOST` verilmisse o kullanilir; yoksa Gateway'de `GET /v1/trading/access-point?account_id=` ile kesfedilir ve onbellege alinir.
- Hata kodlari sayisaldir (1001 = AUTH_INVALID_SIGNATURE, 3015 = REQUEST_RATE_LIMIT). Istemci hicbir istegi kendiliginden tekrarlamaz.
- `RateLimiter.acquire(method, path)`: plan `acquire(operation)` diyordu; `/limits` yaniti her operasyon icin metod + yol sablonu verdigi icin eslestirme sablondan yapilir, operasyon adi koda gomulmez.
- Dagitim: plan `appleboy/ssh-action` diyordu; SSH ozel anahtarini ucuncu taraf bir action'a vermemek icin runner'daki duz `ssh` kullanildi. Ek istege bagli secret'lar: `VPS_KNOWN_HOSTS` (onerilir), `VPS_PORT`.
- Sunucuda iki kullanici: `deploy` (kodu ceker, venv'i gunceller, yalnizca `systemctl restart tradebot` icin sudo) ve `tradebot` (servis; yalnizca `/var/lib/tradebot`'a yazar).
- Kesif ciktisi `var/discovery/` yerine `<db klasoru>/discovery/<ts>/` altina yazilir (servis kullanicisinin yazabildigi tek yer).

### API bulgulari (OpenAPI 1.0.2; canli kesifle dogrulanacak)
- Pozisyonda SL/TP alani yok: SL/TP, pozisyona bagli ayri bir `sltp` emridir. Acilista `stop_loss_price`/`take_profit_price` verilir; sonradan degisiklik `PATCH orders/{sltp_emir_id}`, hic yoksa `POST orders {type: sltp}`. `schema.parse_snapshot` ikisini birlestirir.
- Kismi kapama govde degil sorgu parametresidir: `DELETE positions/{id}?volume=`. Bu yuzden plan'daki `close_position_body` yerine `close_position_path` var; `open_position_body` → `open_position_request` (yol + govde), `modify_sltp_body` → `sltp_create_request` / `sltp_modify_request`.
- Enstruman kosullarinda `tick_value` ve `stops_level` yok. `tick_size = 10^-point_digits`; tick degeri yerelde `contract_size × tick_size × (kote → hesap para birimi kuru)` ile hesaplanir (Task 7). `stops_level = 0`; asiri yakin stop broker tarafinda `TRADING_RULE_INVALID_PRICE_LEVELS` ile reddedilir.
- Enstruman listesi yalnizca ad dondurur; kosullar enstruman basina ayri istektir. Katalog acilista hepsini limitlere uyarak ceker.
- Tur (forex/metal/crypto/other) `category` + para birimi yapisindan cikarilir; gercek `category` degerleri kesifte gorulecek (`summary.json` → `categories`).
- Cent hesapta enstruman adlarinin sonek tasimasi beklenir (or. `EURUSDc`). `Instrument.symbol` kanonik ad (EURUSD), `broker_symbol` API adi. Bot ici her yer kanonik adi kullanir.
- Islem saatleri `trade_sessions` (UTC, "Mon, 00:00:00") alanindan V9 haftalik pencere bicimine cevrilir. Alan yoksa saatler bilinmiyor sayilir ve V9 islem acmaz (fail-closed).
- Mum: `time` ISO acilis zamani, `volume` → `tick_volume`. `from` dahil, `to` haric. Zaman dilimi adlari V9 ile ayni (M15/H1/H4).
- Pozisyon basina kar/zarar API'de yok; yerelde hesaplanir. Hesap bakiyesi/equity `snapshot.account_state` ve `account_state_event` ile gelir (2 sn'de bir).
- Emir sonucu: `transaction_event.status` success/rejected/failed; operasyon durumu pending/confirmed/rejected/failed, 24 saat saklanir. Idempotency key 5..128 karakter, `[A-Za-z0-9._~-]`.
- 429 (`REQUEST_RATE_LIMIT`, 3015) dokumanda "otomatik tekrar edilemez" olarak tanimli; istemci tekrar denemez.
- Tarihler URL'de `2026-03-16T12:00:00Z` biciminde gonderilir (kacis gerektirmez); istemci imzalanan yol ile gonderilen yol farkliysa istegi gondermeden reddeder.
- Task 6: V9'da `is_supported_symbol` (`[A-Z0-9]{3,12}`) eklendi; `capture` ve `analyze` beyaz liste yerine bunu kullaniyor. `SYMBOLS` aynen duruyor. Hicbir eski test kirilmadi (V5 423, V2 152, engine 132 gecti). `docs/source_manifest.json` `refresh_manifest.py` ile yenilendi.
- Task 7: Tick degeri `contract_size × tick_size × kur` ile hesaplanir; kur Exness donusum kurallariyla (dogrudan, ters, USD uzerinden) bulunur. Zarar yuksek kurla, kar dusuk kurla cevrilir (temkinli). Cent hesap: `USC = USD × 100`.
- **Canliya gecmeden dogrulanacak:** cent hesapta `contract_size` degerinin lot basina gercek carpan oldugu (kesif ciktisi + dry-run'da hesaplanan risk tutari ile).
- V9'a `enabled_strategies` sirali liste olarak verilir (V9 parametreleri JSON'a cevirir). Bilinmeyen strateji adlari sessizce elenir; hic etkin strateji kalmazsa aday uretilmez.
- `evaluate()` karar ve nedenleri de dondurur (dry-run ozeti icin); `evaluate_symbol()` plandaki imzayla ayni.
