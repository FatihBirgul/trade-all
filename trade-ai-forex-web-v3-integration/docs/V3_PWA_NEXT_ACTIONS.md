# Sonraki PWA adımları

1. RC teslimi V3_PWA_RC_AUDIT_TR.md; son kalite sonuçları V3_PWA_RELEASE_ACCEPTANCE.md. Önceki belgelerdeki full lint 4 hata bilgisi bu RC'de giderildi.
2. release/rc manifest/payload ve checksum'ları incele; `node tools/promotion-dry-run.mjs` ile güncel hedefi salt okunur doğrula. Hash/guard/envanter drift'inde BLOCK; zorla geçme.
3. Canlı yazma/HMR bakım operasyonu için ayrı açık yetki ve doğrulanmış backup/restore hazırlığı gerekir. APPLY bu görevde yapılmadı, dry-run aracında desteklenmez. Ayrıntı V3_PWA_PROMOTION_PACKAGE.md.
4. BACKEND_RUNTIME_OLD sürüyor. Ayrı runtime cutover ve loaded-build kanıtı olmadan yeni broker/spread özelliklerinin canlı kabulünü verme.
5. Dört broker sembolüne özel spread maksimum/birim/geçerlilik/provenance/onayı ve exact XAUUSDc seans kanıtını bekle. Gözlenen spreadden limit türetme; onaysız BLOCK.
6. Ayrı geçiş sonrası gerçek Android standalone PWA, Tailscale HTTPS, SW/asset sürümü ve safe refusal smoke kabulü yap. İzole 390×844 ve fixture testleri gerçek telefon kabulü değildir.

Orijinal PWA ve backend read-only kaldı; 5173 yeni UI'yi kullanmıyor. Push/merge/emir/hesap değişimi yapılmadı.
