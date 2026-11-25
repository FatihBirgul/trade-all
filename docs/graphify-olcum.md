# graphify ölçümü (2026-11-25)

Paket: PyPI `graphifyy` 0.9.120. Kip: `GRAPHIFY_BACKEND=none` (yalnızca tree-sitter ile yerel kod analizi).

## Kurulumun yazdıkları
`graphify install --project --platform claude` şunları yazar: `.claude/skills/graphify/` (beceri + başvuru
belgeleri), `.claude/CLAUDE.md`, kök `CLAUDE.md` bölümü ve `.claude/settings.json` içine üç Claude Code hook'u
(`PreToolUse` Bash|Grep ve Read|Glob, `SessionStart` compact → `graphify hook-guard …`). **Git hook'u yazmaz**
(o ayrı komut: `graphify hook install`; çalıştırılmadı) ve git ayarlarına dokunmaz.

Hook'lar okundu: yalnızca tavsiye metni ekler, hata olursa sessizce geçer, grafik yoksa hiçbir şey yapmaz. Yine de
**kaldırıldı**, iki nedenle: (1) `graphify` komutu kurulu olmayan her oturumda (bulut oturumları her seferinde temiz
başlar) her araç çağrısında "komut bulunamadı" hatası üretir; (2) aşağıdaki ölçüme göre yönlendirdiği serbest metin
sorgusu bu depoda token kazandırmıyor.

## Grafik
- Tüm depo: 1208 dosya, 21 sn, 12 584 düğüm / 32 395 kenar, çıktı 44 MB (eski projeler dahil).
- Yalnızca `trade-bot/`: 1 801 düğüm / 5 488 kenar, birkaç saniye.

## Tipik sorularda karşılaştırma (karakter; ~4 karakter ≈ 1 token)

| Soru | graphify | grep | Sonuç |
|---|---|---|---|
| Günlük kayıp sınırı nerede denetleniyor? (`query`, serbest metin) | 5 162 | — | **Yanıtı bulamadı** (`_check_limits` ilk 60 düğümde yok; tüm depo grafiğinde ilgisiz dosyalar) |
| `_check_limits` nerede, kim çağırıyor? (`explain`) | 893 | 340 | grep daha ucuz; grafik ek olarak bağlantı türlerini veriyor |
| Elle işlem API'den aracıya nasıl gidiyor? (`path`) | 245 | 1 196 | Grafik daha kısa, ama yol `INFERRED` bağlantı içeriyor (gerçek çağrı zinciri değil) |
| `decide()` değişirse ne etkilenir? (`affected`) | 2 110 | 403 | Grafik daha uzun ama testleri ve dolaylı kullanıcıları tek listede veriyor |
| `backup_database`'i kim çağırıyor? (`explain`) | 1 308 | 1 031 | Yaklaşık aynı |

Her iki yolda da asıl maliyet aynı: bulunan işlevin gövdesini okumak (ör. `_check_limits` 25 satır ≈ 1 400
karakter). Grafik bunu azaltmıyor; `grep -n` de aynı satır numarasını veriyor.

`graphify benchmark` bu grafik için "73 kat daha az token" diyor. Bu, her soruda **tüm kodu** (120 bin token)
okumaya göre bir üst sınırdır; gerçekte kimse öyle çalışmadığı için karşılaştırma yanıltıcı.

## Değerlendirme
Bu depoda graphify, hedefli aramalarda grep'e göre **ölçülebilir bir token tasarrufu sağlamadı**. Yararlı olduğu
yer yapısal sorular (`affected`, `path`) ve tanımadık bir alt projede ilk yön bulma. Bu yüzden beceri ve kullanım
kuralları eklendi, otomatik hook'lar eklenmedi.
