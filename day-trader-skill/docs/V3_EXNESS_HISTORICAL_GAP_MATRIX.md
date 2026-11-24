# 6-11 Kasım 2026 Exness gap matrisi

Durum: **BLOCKED_BY_EXTERNAL_EVIDENCE**. Bu çalışma terminale bağlanmadı,
Exness'ten yeni belge almadı ve herhangi bir gerçek seansı VERIFIED yapmadı.
Kaynak gözlemleri önceki depo belgeleri ve kullanıcı teslimidir; bağımsız
tarihsel broker quote-closed ispatı değildir. Genel XAUUSD duyurusu XAUUSDc'ye,
genel EURUSD saatleri EURUSDc'ye uygulanmadı.

| İncelenecek dönem | XAUUSDc | EURUSDc | Gerekli ek kanıt |
| --- | --- | --- | --- |
| 6 Kasım Cuma kapanışı | UNVERIFIED | UNVERIFIED | Exact symbol, server ve kapanış UTC |
| 7-8 Kasım hafta sonu | UNVERIFIED | UNVERIFIED | Dated quote closure ve pazar açılışı |
| 8 Kasım pazar açılışı | UNVERIFIED | UNVERIFIED | Quote/trade ayrı açılışlar |
| 9 Kasım bakım arası | Gözlem var, quote kapanışı UNVERIFIED | UNVERIFIED | Tam tarihli broker maintenance |
| 9 Kasım 23:00 M15 | İlk tick gözlemi var, tarihsel schedule UNVERIFIED | UNVERIFIED | Exact quote/trade/close-only |
| 10-11 Kasım bakım | UNVERIFIED | UNVERIFIED | Günlük ayrı kapsam ve istisnalar |
| Holiday / exceptional closures | UNVERIFIED | UNVERIFIED | Kaynakta tarihli özel gün beyanı |
| DST / server UTC dönüşümü | UNVERIFIED | UNVERIFIED | Tarihli zone/offset rejimi |

9 Kasım gözlemleri: M1 açılışı 21:57, sonraki M1 23:00 UTC; açılışlar arası
63 dakika, nominal 21:58 kapanışından sonraki açılışa 62 dakika. Gözlenmeyen
M1 bucket'ları 21:58-22:59; M15 bucket'ları 22:00, 22:15, 22:30, 22:45.
21:45 M15 bucket'ı 21:57 M1'i içerir; kısmi seans barı olabilir. Gözlenen ilk
tick 23:00:30.141, sonraki dakika ilk tick'leri 23:01:00.199 ve 23:02:00.115.
23:00 M15 bucket'ı [23:00,23:15) olduğu için bu tick anlarında kapanmış değildir.

Sentetik fixture 22:00-23:00:30 bakım ve 23:00:30-23:02 close-only örneği
tanımlar. Bunlar sadece sınama değerleridir. Üretim takvimine eklenmedi.
Sentetik pozitif testlerde tam kapalı eksik M5/M15 kabul edilir; 23:00 bucket'ı
da eksikse kısmen quote-open olduğu için ret verilir. Quote'un olması new-position
eligibility sağlamaz. Gerçek gap uzlaştırması orijinal broker belgesini bekler.
