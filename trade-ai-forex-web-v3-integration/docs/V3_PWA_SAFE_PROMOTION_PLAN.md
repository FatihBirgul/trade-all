# İzole PWA'nın ana klasöre güvenli aktarımı

Bu görev ana PWA'ya yazım/merge/cutover yapmadı. Kaynak `%USERPROFILE%\trade-ai-forex-web` Git deposu değildir; branch/HEAD raporlanamaz. İzole `codex/pwa-v3-manual-analysis` geçmişi yeni snapshot'tır, ana geçmiş değildir. Mevcut 5173 Vite bu asıl klasörü izlediği için kaynak dosyası değişimi HMR doğurabilir. Ayrı açık yetkili frontend operasyon gerekir; çalışan servisleri şimdi restart etme.

## Hazır karşılaştırma

İzole baseline commit `01c96bb950804ed11fdb512937a81b554ddd669c`. `.artifacts/source-fingerprints.json` o andaki ana aktif src/config/service dosyalarını hash olarak kaydeder; raw gizli ayar kopyası değildir. MarketChart/NewsPanel/AnalysisNewsRisk/CalendarPanel/RiskCalculator izole dosyaları byte-identical korundu. Backend tracked fingerprintleri ve HEAD 3c8adb8 değişmedi. Ana klasör source hash'leri son kontrolde değişmedi; buna rağmen promotion anında tekrar alınmalıdır. Önceki başka iş akışındaki MarketChart/news değişiklikleri snapshot'a dahil edilmiş ve ezilmemiştir.

## Ayrı yetkili aktarım adımları

1. Ana PWA'nın gerçek Git durumu tekrar kontrol edilir. Sonradan repository olmuşsa branch/HEAD/dirty envanteri alınır; yeni worktree aracılığıyla gerçek merge planı yapılır. Hâlâ Git yoksa git merge olmuş gibi işlem yapılmaz.
2. MarketChart.tsx, NewsPanel.tsx, AnalysisNewsRisk.tsx, App.tsx, AnalysisPanel.tsx ve Vite config'in güncel hash'leri baseline ile karşılaştırılır. Drift varsa mevcut kullanıcı dosyaları korunur; genel recursive copy veya force checkout yoktur.
3. Önce yalnız değişecek aktif dosyaların geri alınabilir yedekleri watcher kökü dışına güvenli saklanır. .env, sertifika, MT5/news Python dosyaları veya kişisel veriler yeni pakete taşınmaz. İki yönlü karşılaştırma bitmeden üzerine yazılmaz.
4. Yeni AnalysisPanel, AnalysisPanel.css ve src/analysis modülleri değerlendirilir. App.tsx'teki tek chartSource prop değişikliği güncel dosyaya bağlama göre uygulanır; App'in tamamı ezilmez. AnalysisNewsRisk import/render entegrasyonu korunur. Chart/news kaynaklarına bu özellik için değişiklik gerekmez.
5. package dev dependency farkı yalnız Playwright test araçlarıdır; production dependencies aynı. lock/scripts entegrasyonu review edilir. Ana çalışan node_modules üzerinde npm ci yapılmaz. Yeni build önce ayrı ortamda alınır.
6. Vite config değişikliği opsiyoneldir: V3_ANALYSIS_PROXY_TARGET test proxy hedefi, varsayılan 8006. Ana servis hedefi veya Tailscale/firewall ayarı otomatik değiştirilmez. Test env/browser portları production launch'a taşınmaz.
7. Tam ESLint'teki mevcut dört legacy hata ayrı sahiplik kapsamında giderilmeli veya release review'da açıkça kabul edilmelidir; bu görevde gizlenmedi. Yeni kapsam lint/typecheck/build/unit/browser sonuçları yeniden çalıştırılır.
8. Dosya aktarımının 5173 HMR etkisi kullanıcı tarafından ayrıca yetkilendirilen frontend operasyonunda gözlenir. Backend cutover bundan ayrıdır; 8005/8006/8007 korunur. Yeni 8006 hazırlanmadıysa UI eski schema uyum uyarısı/plan kapalı vermelidir.
9. Post-promotion: dört sembolde manuel istek, source identity, null/blocked, USC, V2 context, mobile viewport, allowed-host ve gerçek telefon/Tailscale/service-worker güncellenmesi kabul edilir. Fixture başarıları canlı kabul sayılmaz.

Rollback yalnız aktarılan dosyaların önce güvenli saklanan sürümlerinin kontrollü geri getirilmesidir; kullanıcı drift'i silinmez, destructive reset/global paket değişimi yapılmaz. Servis restartı kendiliğinden rollback aracı değildir. Bu görevde kaynak promotion uygulanmadı.

## Kalan operasyon engelleri

Mevcut 8006 yeni broker_contract/spread_status alanlarını taşımıyor; runtime geçişi ayrı onay ve kanıt gerektirir. Dört spread maximum hâlâ UNAPPROVED/null; exact XAUUSDc tarihsel quote seans belgesi yok. Frontend bunları doldurmaz. Yeni UI güvenli retleri gösterebilir fakat canlı uygulanabilir BUY/SELL planı garantilemez.
