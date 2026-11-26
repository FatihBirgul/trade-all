# Trade Bot (telefon uygulaması)

Sunucudaki trade botu izlemek ve yönetmek için Android uygulaması. Eski `trade-ai-android` projesinden ayrı,
temiz bir Expo projesidir; aynı Android paket adını (`com.fatihbirgul.tradeai`) ve imzayı kullanır, bu yüzden
eski uygulamanın **üstüne kurulur** (telefondaki eşleşme korunur).

## Ekranlar
| Ekran | Dosya | Ne gösterir / ne yapar |
|---|---|---|
| Panel | `app/(tabs)/index.tsx` | Varlık, bakiye, bugün/hafta/ay kâr-zarar, bot durumu, Durdur/Devam, Hepsini kapat, deneme ↔ canlı (canlıya geçiş iki onay), son 24 saatte botun yaptıkları |
| Pozisyonlar | `app/(tabs)/positions.tsx` | Açık pozisyonlar; stop/hedef düzenleme, kademeli stop aç/kapa, kapatma |
| Elle işlem | `app/manual-trade.tsx` | Sembol seçimi, önizleme, onay; stopsuz emir gönderilmez |
| Raporlar | `app/(tabs)/reports.tsx` | Gün/hafta/ay kapanan işlemler, strateji ve sembol kırılımı, sanal (gölge) karne |
| Bildirimler | `app/(tabs)/events.tsx` | Önemli olaylar / tüm kayıtlar |
| Ayarlar | `app/(tabs)/settings.tsx` | Risk sınırları, korumalar ve stop aşamaları, semboller, strateji kipleri |
| Bağlantı | `app/connection.tsx` | Eşleştirme; eşleşince Panel'e döner |
| Tanı | `app/diagnostics.tsx` | Uygulamanın sunucuya yaptığı son istekler (yol, yanıt kodu, süre, hata) |

Her veri ekranında üç durum ayrı çizilir: **yükleniyor**, **hata + yeniden dene**, **boş**. Onaylar uygulamanın
kendi penceresiyle sorulur (`src/ui/confirm.tsx`).

## Yapı
- `src/bot/`: sunucu istemcisi, durum yönetimi, doğrulama kuralları (ekrandan bağımsız; birim testleri `__tests__/`).
- `src/ui/`: görsel bileşenler ve renkler (`theme.ts`).
- `fixtures/`: **gerçek sunucu kodunun** ürettiği yanıtlar (borsa ve hesap sahte). Yeniden üretmek için:
  `cd ../trade-bot && .venv/bin/python tools/capture_app_fixtures.py ../trade-bot-app/fixtures`
- `e2e/`: her ekranın bu yanıtlarla veri gösterdiğini kanıtlayan tarayıcı testleri; görüntüler `screenshots/`.

## Simge ve açılış ekranı
Çizim `tools/brand.cjs` içinde tanımlıdır (nabız çizgisi yükselen bir eğilime dönüşür, yeşil noktada biter).
`node tools/brand.cjs` şunları üretir: `assets/icon.png`, adaptive simgenin ön / arka / tek renk katmanları,
açılış logosu ve önizlemeler (`screenshots/00-logo.png`, `00b-acilis-ekrani.png`). Android'in yoğunluk
dosyalarını (mdpi…xxxhdpi) `expo prebuild` bu kaynaklardan üretir.

## Komutlar
```bash
npm ci
```
```bash
npm run typecheck && npm run lint && npm test
```
```bash
npm run screens
```
`npm run screens` web derlemesini alır, 22 ekran testini çalıştırır ve `screenshots/` klasörünü yeniler.

## APK
`.github/workflows/trade-bot-app.yml`: her itmede denetimler; commit mesajında `[apk]` varsa (ya da elle
çalıştırılırsa) APK derlenir. Kalıcı imza anahtarı tanımlı değilse APK, React Native şablonunun herkesçe bilinen
test anahtarıyla imzalanır (eski uygulamayla aynı; yalnızca deneme içindir).

## Bilinen sınırlar
- Ekran testleri tarayıcıda (Expo web) çalışır; gerçek telefonda ayrıca denenmelidir.
- Anlık bildirim (Firebase) kurulu değil: uygulama kapalıyken bildirim gelmez.
