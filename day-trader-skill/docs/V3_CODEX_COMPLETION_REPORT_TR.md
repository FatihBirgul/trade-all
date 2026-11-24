# Codex 1 DEMO kabul hazırlığı

Başlangıç V3 `codex/v3-exness-session-integration` / `55a0b9d` temiz; V2 `antigravity/v2-analysis-research` / `c80c97f` kirli çalışma ağacı korunarak salt okunur incelendi. PWA dosyaları salt okunur incelendi. Yeni `codex/v3-demo-acceptance` dalında DEMO account preflight ve bakiye provenance geliştirildi. Pinli V2 bridge, G-001/G-002/G-003/G-004 ve broker session/USC kontrolleri korundu.

Varsayılan MT5 terminalinin salt okunur hesap türü kontrolü REAL döndü. Bu nedenle canlı DEMO sembol/fiyat/mum/profit testi yapılmadı. 8005/8006/5173 dinliyor, fakat servis kaynak eşitliği doğrulanmadı. PWA yalnız XAUUSD/EURUSD çağırıyor, bakiyeyi 10.000 gönderiyor ve USC/kaynak gösterimini yapmıyor. Backend DEMO preflight başarılıysa bu istek bakiyesini yok sayıp terminal bakiyesini kullanır. Emir, push, merge, Actions, PWA/V2/bridge kaynak yazması yok.

Test sonuçları ve kalan engeller [V3_LOCAL_TEST_RESULTS.md](V3_LOCAL_TEST_RESULTS.md) ve [V3_DEMO_ACCEPTANCE_MATRIX.md](V3_DEMO_ACCEPTANCE_MATRIX.md) içinde kayıtlıdır. İlk dış adım ayrı bir DEMO terminalinin açıkça seçilmesi ve exact server/currency beklentisinin sağlanmasıdır; hesap değiştirme otomatik yapılmaz.

10 Kasım 2026 politika güncellemesi: Kullanıcı REAL hesabı yalnız salt okunur piyasa veri kaynağı olarak yetkilendirdi. `codex/v3-real-readonly-analysis` dalında DEMO_ONLY korunup explicit REAL_READONLY_DATA eklendi; gerçek hesap bakiyesi kullanılmaz, eski sabit 10.000 yok sayılır. Canlı salt okunur metadata ve dört sembol güvenli seans ret sonucu `V3_REAL_DATA_MANUAL_ANALYSIS_TESTS.md` içindedir. Bu ek, önceki DEMO-only kabul durumunu tarihsel kayıt olarak bırakır; güncel kabul `V3_ACCEPTANCE_STATUS.md` içindedir.
