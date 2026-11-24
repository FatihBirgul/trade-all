# İlk manuel DEMO kabul durumu

| Kriter | Durum |
|---|---|
| Manuel `POST /api/v5/analysis`, tipli V5 sözleşmesi | PASS, yerel TestClient ve 8006 OpenAPI yolu |
| V2 pinli mum formasyonu bağlamı | PASS, fixture ve önceki gerçek V2 yerel kaynak smoke |
| Kapalı mum/MTF/quote/QC/seans veto | PASS, sentetik regresyon |
| 22:40/22:50 OPENING_SOON kapalı boşluk | PASS, sentetik seans |
| USC ve dört Exness alias | PASS, sentetik terminal; canlı doğrulama UNVERIFIED |
| Exness gerçek M15/H4, DST, tatil ve server UTC | BLOCKED, güvenilir broker kanıtı eksik |
| Gerçek MT5 demo hesabında salt okunur uçtan uca analiz | NOT RUN; çalışan servis hesabı doğrulanmadı |
| PWA XAUUSD/EURUSD manuel yol | Kısmi: PWA kodu endpoint'i çağırıyor; gerçek API yanıtı ve deployment uyumu doğrulanmadı |
| PWA GBPUSD/USDJPY | BLOCKED: `AnalysisPanel.tsx` yalnız XAUUSD/EURUSD için butonu etkinleştiriyor; dosya değiştirilmedi |
| PWA bakiye/para birimi doğruluğu | BLOCKED: istek 10000 ve yüzde 1 sabit varsayım kullanıyor; gerçek USC bakiye/para birimi UI'da gösterilmiyor |

Bu sürüm ilk güvenilir canlı DEMO kabulünü henüz karşılamıyor. Emre giden yol yoktur.
