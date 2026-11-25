## graphify (isteğe bağlı kod grafiği)

Bu depoda graphify becerisi kurulu (`.claude/skills/graphify/`). Grafik depoya **konmaz** (`graphify-out/`
`.gitignore`'da); her makinede yerelde üretilir. Yalnızca yerel kod analizi kullanılır: `GRAPHIFY_BACKEND=none`
(hiçbir dosya modele gönderilmez) ve `GRAPHIFY_QUERY_LOG_DISABLE=1` `.claude/settings.json` içinde ayarlıdır.

Kurulum ve grafik (resmi paket PyPI'da **`graphifyy`**, çift y; benzer adlı paketler sahtedir):

```bash
pip install graphifyy
```

```bash
graphify extract trade-bot --code-only
```

Kurallar (2026-11-25 ölçümüne göre; ayrıntı `docs/graphify-olcum.md`):
- Grafiği **yapısal** sorular için kullan: `graphify affected "<sembol>" --graph trade-bot/graphify-out/graph.json`
  (bu değişirse ne etkilenir), `graphify path "<A>" "<B>"` (iki sembol nasıl bağlanır), `graphify explain "<sembol>"`.
- Bir metnin ya da sembolün **nerede** geçtiğini bulmak için `grep` daha ucuz ve kesindir; bunun için grafik kullanma.
- Serbest metinli `graphify query "<soru>"` bu depoda güvenilir değil (anahtar sözcük eşleştiriyor, ilgisiz düğümler
  döndürüyor). Tüm depo yerine tek bir alt klasörün grafiğini kur; kök grafiği eski projelerle dolar.
- Grafik çıktısını doğrulanmış davranış sayma: `INFERRED` bağlantılar tahmindir; önemli olanı kaynakta doğrula.
- Koddaki değişiklikten sonra `graphify update trade-bot`.
- `graphify hook install` (git hook'ları) ve `graphify install`'ın yazdığı Claude Code hook'ları **kurulmaz**
  (kullanıcı kararı ve ölçüm sonucu).
