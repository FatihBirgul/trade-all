# PWA APPLY ve rollback

RC payload SHA değişmedi: manifest1035c984…; ZIPc62f6c8e…. Önceki dry-run aracı korunur. Yeni araç tools/promotion-apply.mjs varsayılanında salt okunurdur. --apply ayrı açık operasyon onayı, exact manifest hash'i ve fresh backend kabul receipt'i ister. Bir CLI bayrağı kriptografik kullanıcı onayı değildir; ajan açık kullanıcı yetkisi olmadan onu kullanamaz.

Allowlist aynı9 dosyadır. Ön kontrol: manifest/payload SHA, source-target hash,27 guard/envanter, path/junction, backup konumu, approved RC kimliği. Yedek canlı Vite ağacı dışında release/live-backups/UTC-UUID; overwrite yok. Kaynak bytes RAM'e alınır ve hashlenir; hedefler backup sonrası ve her replacement öncesi yeniden doğrulanır. fd fsync + aynı dizinde geçici dosya/rename kullanılır. Contract/client/CSS önce, panel sonra, App en son. Multi-file atomic deployment iddiası yoktur; onaylı HMR bakım penceresi gerekir.

Receipt PREPARED/APPLYING/APPLIED_SMOKE_PASS/FAILED_SAFE_STOP/ROLLING_BACK/ROLLED_BACK durumlarını, exact before/after hash ve adımları kaydeder. Receipt SHA kazara bozulma kontrolüdür, imza değildir. Elektrik kesintisi/journal iki dosyasının yazımı arasında hata recovery için manuel review gerektirebilir; yıkıcı otomatik reset yapılmaz. Geçici dosyalar hatada korunur.

Smoke veya orta aktarım hatasında otomatik rollback denenir. Tüm hedefler önce topluca doğrulanır; yalnız RC veya başlangıç hash'leri kabul edilir. Backup hash'leri doğrulanır. Önceden var dosyalar eski baytlarıyla geri koyulur; önce olmayan yeni dosyalar silinmez, retained-new-files altına taşınır. Boş yeni dizinler kalabilir. Sonradan user edit, yeni source dosyası, NewsPanel/MarketChart drift'i, backup/receipt bozulması veya junction varsa BLOCK/REVIEW; kullanıcı değişikliği ezilmez.

18 APPLY/rollback testi temp fixture hedeflerinde geçti: varsayılan0write, onaysız ret, exact manifest, backend receipt zorunluluğu, byte-level round trip, bağımlılık sırası, benzersiz backup, chart/news drift, corrupt payload, smoke/partial IO rollback, concurrent user edit stop, postapply user edit stop, backup/receipt corruption, watched-root backup reddi, yeni dosya drift ve junction.

12 canlı kabul guard testi;4 launcher guard testi ayrıca geçti. Gerçek canlı APPLY veya rollback yapılmadı. Aynı RC için eski12 dry-run testi de geçti. Yeni araçlar/evidence RC payload'a otomatik dahil değildir; ayrı cutover source paketi içindedir.
