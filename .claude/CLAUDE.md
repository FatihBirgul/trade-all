# graphify
- **graphify** (`.claude/skills/graphify/SKILL.md`) - any input to knowledge graph. Trigger: `/graphify`
When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

## Bu depoya özel kurallar (becerinin varsayılanlarının önüne geçer)
- Yalnızca kod: `graphify extract <klasör> --code-only`. Anlamsal çıkarım (belgelerin, PDF'lerin, görsellerin bir
  modele okutulması) **yapılmaz**; `GEMINI_API_KEY`/`GOOGLE_API_KEY` istenmez ve önerilmez.
- `GRAPHIFY_BACKEND=none` ve `GRAPHIFY_QUERY_LOG_DISABLE=1` değiştirilmez.
- `graphify install`, `graphify claude install`, `graphify hook install` yeniden çalıştırılmaz (hook yazarlar).
- Graphify Cloud önerilmez; hiçbir dosya dışarı yüklenmez.
- `graphify-out/` depoya eklenmez (depo herkese açık).
- Ne zaman kullanılacağı: kök `CLAUDE.md` içindeki "graphify" bölümü.
