# Bakım onayı taslağı — henüz uygulanabilir değildir

Bu metin bir onay talebi veya alınmış onay değildir. Paket BLOCKED'dır. İş akışı koordinasyonu, taze operator binding/controller ve izole A/failback QA tamamlandıktan sonra boş alanları doldurularak tek onay için sunulacaktır.

> Bakım süresince 5173/8005/8006/8007/8008'i veya ilgili kaynak/başlatıcıları değiştirebilen diğer iş akışlarının duraklatıldığını teyit ediyorum. Tek operatör kimliği [PID + creation time + exe], operasyon kimliği [ID], gözden geçirilmiş paket SHA-256 [HASH] ve taze baseline SHA-256 [HASH] kapsamındaki iki aşamalı bakıma izin veriyorum.
>
> A: Yalnız bu baseline'daki 8008 süreç kimliğinin kontrollü değiştirilmesi; sabit 56cbd7e kaynaklı attested launcher, startup-frozen fingerprint ve salt-okunur kabul. A başarısızsa yalnız operasyonun başlattığı süreçler üzerinde, doğrulanmış pinli failback planına izin veriyorum. Yabancı port sahibine müdahale edilmez. Failback başarılı olsa bile PWA aşamasına geçilmez.
>
> B: Yalnız A primary kabulünün tamamı PASS olursa ve post-A process/startup receipt'i aynı operasyon paketindeki dönüşüm kurallarıyla yeni PWA manifestine bağlanırsa, hash'leri onaylı dokuz PWA kaynak dosyasının 5173'ün orijinal kaynak dizinine aktarımına, bunun Vite HMR/cache etkilerine, doğrulanmış yedek ve receipt tabanlı frontend geri almaya izin veriyorum. Taze hedef guardlarından biri başarısızsa hiçbir frontend dosyası yazılmaz.
>
> 8005/8006/8007, proxy/Tailscale, main backend kaynakları, global Python/NumPy ve MT5 oturumları değiştirilemez. Gerçek/demo emir, order_check/order_send ve otomatik tarama yetkisi vermiyorum. Spread ve tarihsel kanıt engelleri kaldırılmaz. Paket/baseline/payload değişirse bu onay geçersizdir; yeniden inceleme gerekir.

İlk cümledeki koordinasyon teyidi bir dosya kilidinden çıkarılamaz. Advisory lease diğer ajanları, manuel PowerShell'i veya Task Scheduler'ı durdurmaz. Başka bir actor servis değiştirirse işlem guard ile durmalıdır.
