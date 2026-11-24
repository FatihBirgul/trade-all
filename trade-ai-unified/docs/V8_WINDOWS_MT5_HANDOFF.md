# Windows MT5 salt okunur pilot — Türkçe

Gerçek Windows terminali bu ortamda çalıştırılmadı. Sonuç UNVERIFIED kalır.
Aşağıdaki paket yalnız broker metadata, kotasyon ve hesaplama kanıtı toplar.
Gerçek/demo emir, order_send/order_check veya pozisyon işlemi yapmaz.

1. Private depoyu Windows'ta aynı feature branch ile açın. Python3.11/3.12 kullanın.
   `python -m pip install -r requirements-lock.txt`; MetaTrader5 binding'i Windows'a
   ayrıca kurun. Terminali kendiniz açıp broker hesabınıza yerel olarak bağlanın.
   Login/password/account-number bilgilerini komutlara, Git'e veya rapora yazmayın.
2. `.env.example` alanlarını shell'de açıkça yükleyin; otomatik .env okuma yoktur.
   Exact aliases için MT5_SYMBOL_MAP kullanın. Market/contract type belirsizken
   tahminle beyan eklemeyin. Saat kaynağı ve DECLARED opt-in olmadan plan üretilmez.
3. PowerShell'de yeni, benzersiz çıktı dosyası üretin:

```powershell
$pilotStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
python scripts/windows_pilot.py | Out-File -Encoding utf8 "mt5-pilot-$pilotStamp.json"
```

4. Raporu paylaşmadan önce açıp kontrol edin. Paket whitelist export kullanır:
   account number/login/username/password/token/terminal path ve margin_free yoktur.
   Exception ayrıntıları generic hata olur. Broker/server alias, currency, tick/grid/
   contract/stops/directions, tick age/bid/ask, read-only min-lot profit/margin ve
   code/evidence hash vardır. Kaynak saatleri authenticated sayılmaz; holiday/DST
   bilgisi MT5'in vermediği durumda kendiliğinden doğrulanmaz.
5. Eksik konfigurasyon ve recommended_next_test alanlarını izleyin. Kâr hesabında
   stop sonucu negatif olmalı; margin estimate mevcut pozisyonları hesaba katmayan
   salt-okunur bir örnektir. Tarihsel margin/swap/fee doğrulaması değildir.
6. Beklenen kontrat alanlarını sembol→alan sözlüğü olarak yerel JSON'a koyup farkları
   okuyun: `python scripts/reconcile_pilot.py --reference expected.json --evidence mt5-pilot-....json`.
   Her dosya256KB ile sınırlıdır; rapor yalnız izinli kontrat alanlarını karşılaştırır.

Linux smoke run DATA_UNAVAILABLE/UNVERIFIED döndü, fixture'a geçmedi. Mock testleri
margin/profit sign, sensitivity filtering, reconciliation ve yasak SDK operasyonunu
SDK dispatch öncesi reddetmeyi doğrular. Kaynak depolar veya yerel PWA/Android/Gateway
projelerinde değişiklik yapılmamıştır. Gerçek pilot sonrası yeni kanıt incelenmelidir.
