# Tasarım yönleri (seçim bekliyor)

Panel ve Pozisyonlar ekranı için üç farklı görsel yön. Görüntüler bu projenin web derlemesinden alınmıştır
(`npm run export:web && node tools/screenshots.cjs design ...`); veri **örnektir** (`fixtures/design_sample`).
Eski uygulamanın koyu-altın kart teması hiçbirinde kullanılmadı.

| Yön | Panel | Pozisyonlar | Karakter |
|---|---|---|---|
| **A — Açık ve sakin** | `yon-a-panel.png` | `yon-a-pozisyonlar.png` | Açık zemin, beyaz kartlar, tek mavi vurgu; en okunaklı ve en "banka uygulaması" gibi olan. |
| **B — Terminal** | `yon-b-panel.png` | `yon-b-pozisyonlar.png` | Koyu, yoğun, tablo düzeni, eş aralıklı rakamlar; bir ekrana en çok bilgi sığan. |
| **C — Canlı** | `yon-c-panel.png` | `yon-c-pozisyonlar.png` | Renkli üst alan, yuvarlak kartlar, ikonlu durumlar; en modern ve en az "finans terminali" gibi olan. |

Üçünde de aynı bilgiler var: varlık/bakiye, bugün-hafta-ay kâr/zarar, bot durumu ve son tarama, Durdur ve
Hepsini kapat, "son 24 saatte bot ne yaptı"; pozisyonlarda giriş/şimdi/stop/hedef, kademeli stop aşaması,
SL-TP düzenle ve Kapat. Seçilen yönde bütün ekranlar (Elle işlem, Raporlar, Bildirimler, Ayarlar, Bağlantı)
yazılacak; diğer ikisi silinecek.
