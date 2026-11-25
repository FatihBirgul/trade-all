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
