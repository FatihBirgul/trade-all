# Yerel entegrasyon denetimi — 29 Ekim 2026

Başlangıç Android kaynağı 0.7.1 / versionCode 10 ve Görev 9 raporudur. Bu dal
0.7.2 / versionCode 11 adayıdır. Kontroller Windows bilgisayarda yapılmıştır;
fiziksel telefon testi değildir.

## Çalışan sistemin salt okunur gözlemi

- Backend 127.0.0.1:8002, Gateway 127.0.0.1:8787 ve Tailscale Serve 443
  dinliyordu. Serve, Gateway'e yönleniyordu.
- Backend `/api/v2/health`, Gateway `/gateway/session` ve Serve üzerinden aynı
  oturum yolu, kimlik bilgisi olmadan beklenen HTTP 401 yanıtını verdi.
- Public Binance spot ticker ucu doğrudan HTTP 200 ve geçerli fiyat/zaman
  alanları verdi. Bu, çalışan Backend'in provider isteğinin başarılı olduğunu
  kanıtlamaz. Canlı mobil oturum veya backend bearer olmadan yetkili analiz,
  quote, portföy ve takip GET'leri sorgulanmadı.
- Repo içinde servis hata logu bulunmadı. Çalışan servisler durdurulmadı veya
  yeniden başlatılmadı. Gateway'in yetkisiz GET sınırı `limits` tablosunda oran
  sayacı tuttuğundan üç sağlık denemesi bu geçici sayaçlara yazmış olabilir;
  portföy, analiz, oturum kayıtları veya migration değiştirilmedi. Bu etki
  fark edildikten sonra canlı Gateway isteği yapılmadı.

## Sözleşme ve veri akışı

| İşlev | Android çağrısı | Gateway ve Backend durumu |
| --- | --- | --- |
| Analiz/geçmiş/grafik | analyze, analyses, detail, candles | İzinli; Backend immutable snapshot ve WAIT güvenlik kapısı |
| Piyasa fiyatları | quotes | İzinli; stale/unavailable açıkça işaretlenir |
| Sanal portföy | portfolios, positions, orders, transactions, performance | GET izinli; mobil finansal POST uygulamada kapalı |
| Tarama | scanner, watchlist, jobs, pause, tick | İzin ve hesap kapsamına bağlı; auto_paper zorla false |
| Analiz takibi | analysis-tracking GET/POST | İzin ve hesap kapsamına bağlı; worker opt-in |
| Oturum | gateway/session, pair, refresh | 401 iptal/süre dolumu; 403 erişim veya kapsam reddi olabilir |

Gateway testlerinde gerçek Backend uygulaması yalnız geçici fixture SQLite
veritabanı ve ASGI transport ile kullanıldı; 42 test geçti. Bu, gerçek piyasa
ve telefon ağ testi değildir.

## Düzeltilen hata

Gateway `SCOPE_DENIED` veya `ENDPOINT_DENIED` için geçerli mobil oturuma HTTP 403
döndürür. Android 0.7.1, her 403 yanıtını `UNAUTHORIZED` sayıyor ve oturumu
iptal edilmiş gibi işaretliyordu. `gateway/session` ve `gateway/refresh` sınırında
da 403 yanlış sınıflanıyordu. Üç regresyon önce başarısız oldu. Artık yalnız
HTTP 401 oturum iptali/yeniden eşleştirme tetikler; 403 ayrı hata olarak kalır.
Yenileme isteğinin önceden kaydedilmiş pending anahtarı korunur.

## Doğrulama ve sınırlar

- Android: typecheck, lint, 137 Jest testi ve 17 yerel SDK kontrolü geçti.
- Backend: 220 çevrimdışı test geçti. Açık kalan Windows SQLite test bağlantısı
  kapatıldı; tracking OpenAPI 422 açıklaması kayıtlı sözleşmeyle sabitlendi.
- Gerçek telefonda 0.7.2 kurulumu, kayıtlı oturumun korunması, Tailscale
  bağlantısı, yetkili canlı endpoint'ler, provider kaynaklı quote ve scanner/
  takip worker çalışması hâlâ doğrulanmalıdır.
- Bu dal çalışan Backend/Gateway servislerine dağıtılmadı; eşleştirme ve ağ
  ayarları değiştirilmedi. Yukarıdaki Gateway oran sayacı etkisi hariç canlı
  veritabanlarına müdahale edilmedi.
