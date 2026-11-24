# Trade AI V2 — Windows ve özel ağ hazırlığı

Bu belge talimattır; bu çalışma sırasında gerçek Windows/ağ ayarı, servis veya
port yönlendirmesi değiştirilmedi. Kullanıcı PC'sinde kurulum/telefon testi yapılmadı.
Hedef: i3-3240 / 8 GB / SSD; tek Uvicorn process, tek isteğe bağlı scanner thread.

## 1. Ayrı V2 kurulumu

`trade-ai-v2` dalını kullan. Python 3.11 x64 kurulu olmalı (CI referansı).
PowerShell'de `backend` klasöründe:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-v2.txt
```

Private rastgele token'ı bir parola yöneticisinde oluştur/sakla. En az 24 karakter;
gerçek token'ı sohbete, GitHub'a, frontend'e veya Task Scheduler komutuna koyma.
Geçerli PowerShell sürecine güvenli giriş:

```powershell
$Secret = Read-Host 'V2 private bearer token' -AsSecureString
$Ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secret)
try { $env:V2_API_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Ptr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Ptr) }
.\.venv\Scripts\python.exe start_v2.py --database ..\local_data\v2-live.sqlite --mode live
```

Token süreç belleğinde bulunur; bu bir Windows secret-store entegrasyonu değildir.
`start_v2_windows.ps1` aynı başlatmayı yapar, `-Scanner` opsiyoneldir. Sistem script
policy'si çalıştırmayı engellerse policy değiştirmeden yukarıdaki Python komutunu
kullan. `v2-env.example.txt` yalnız açıklamadır; otomatik yüklenmez.
Fixture denemesi için **başka dosya** ve `--mode fixture` kullan. DB modunu değiştirme.

## 2. Health ve güvenli durdurma

```powershell
$Headers = @{ Authorization = "Bearer $env:V2_API_TOKEN" }
Invoke-RestMethod http://127.0.0.1:8002/api/v2/health -Headers $Headers
```

Health 200, `real_execution=false`, doğru `data_mode` ve storage kontrolünü doğrula.
`provider_status=not_probed` canlı kaynağın doğrulandığı anlamına gelmez; ilk analiz
veya poll sonucu ayrıca kontrol edilir. Ctrl+C normal kapanıştır. `--scanner`
worker'ı kapanırken kalıcı pause yapar. Yeniden başlatınca scanner'ı ve iki hesabı
GET ile kontrol et; recovery tamamlanmadan yeni risk alma.
`local_data/v2-runtime.log` 2 MB, üç yedekle döner. Log rotation retention yerine
geçmez; DB analiz/event/journal/outbox geçmişi otomatik temizlenmez.

## 3. SQLite backup ve restore

Yalnız **V2 product DB** için, backend klasöründe:

```powershell
.\.venv\Scripts\python.exe scripts\backup_v2.py ..\local_data\v2-live.sqlite ..\local_data\backups\v2-2026-10-21.sqlite
```

SQLite backup API tutarlı snapshot alır; açık DB'yi Explorer ile kopyalamaya gerek
yoktur. Kaynak read-only açılır; integrity_check, product mode, JSON projection
checksum ve decision record hash kontrolü yapılır. Mevcut hedefin üzerine yazılmaz.

Restore öncesi server'ı durdur. **Yeni hedefe** doğrulanmış kopya oluştur:

```powershell
.\.venv\Scripts\python.exe scripts\backup_v2.py ..\local_data\backups\v2-2026-10-21.sqlite ..\local_data\v2-restored.sqlite
.\.venv\Scripts\python.exe start_v2.py --database ..\local_data\v2-restored.sqlite --mode live
```

Orijinal dosyayı silme/değiştirme; iki sunucuyu aynı hesap yedeğiyle paralel kullanma.
Restore sonrası scanner'ı ve hesapları pause et, GET ile bakiyeyi/geçmişi doğrula,
`POST /paper/poll` ile eksiksiz kapalı barları toparla. `PAPER_RECOVERY_IN_PROGRESS`
ilerlemenin kaydedildiği, yeni riskin beklemesi gerektiği durumdur. Sayfa başına
300 dakika; gerektiği kadar kontrollü poll. Kaynak eksikse işlem bekler, fiyat
uydurulmaz. Kullanıcı kontrolünden sonra hesap/scanner resume edilir.
Yedekler hesap/geçmiş içerir; özel tut ve başka cihazda da koru.

## 4. Telefon erişimi — tasarım, kurulum yapılmadı

Backend `127.0.0.1:8002` üzerinde kalır. Emergent'tan yerelde çalıştırılabilir UI
ve aynı origin'de server-side API proxy/BFF istenir. Proxy hedefi sabit loopback
olmalı; backend token yalnız server-side environment'da kalmalıdır. Tarayıcı için
ayrı oturum kimlik doğrulaması ve cookie/CSRF koruması UI tesliminin parçasıdır.
Bu proxy/oturum katmanı henüz backend içinde uygulanmadı.

PC ve telefon aynı özel Tailscale ağına alınır; yalnız kullanıcı cihazlarına
izin veren erişim kuralları kurulur. Tailscale **Serve**, yerel UI/BFF'yi tailnet
üzerinden HTTPS ile sunabilir. Funnel/public paylaşım ve modem port forwarding
kullanılmaz. 8002'yi `0.0.0.0`'a açma, Windows firewall'ı kapatma.
Emergent'ın internetteki preview sunucusu kendi `localhost`'u üzerinden kullanıcının
PC'sine erişemez; uzaktaki preview'yi canlı backend'e bağlı diye gösterme.

Resmî kaynaklar (2026-10-21 kontrolü):
- https://tailscale.com/docs/features/tailscale-serve
- https://tailscale.com/docs/reference/tailscale-cli/serve

## 5. Otomatik başlatma hazırlığı

Henüz Windows service/Task Scheduler işi oluşturulmadı veya doğrulanmadı.
Önce manuel başlatma, health, backup/restore, 12 saat recovery ve telefon erişimi
kullanıcının PC'sinde test edilmeli. Sonra kullanıcı hesabı altında sınırlı yetkiyle,
mutlak çalışma dizini ve venv Python yolu ile Task Scheduler tasarlanabilir.
Token komut satırına yazılmamalı; güvenli OS secret kaynağı entegrasyonu gerekir.
BIOS elektrik sonrası açılma ve oturum açılmadan çalışma bu teslimde yoktur.

