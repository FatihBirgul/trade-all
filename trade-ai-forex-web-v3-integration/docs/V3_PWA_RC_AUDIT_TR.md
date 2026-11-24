# PWA RC denetimi — 2026-11-11

A. İzole root %USERPROFILE%/trade-ai-forex-web-v3-integration, branch codex/pwa-v3-manual-analysis, başlangıç HEAD db838abeff69c1baf934a1a42f405dd85762bb90, başlangıç clean. Son yerel commit final teslimde ve git log'da; paket manifest source_head alanında bulunur. Node 24.19.0/npm 11.17.0; npm lock ve kurulu Edge/Playwright ile test edildi.

B. Orijinal %USERPROFILE%/trade-ai-forex-web Git repository değildir. Git init yapılmadı. Aktif src/public/config ağacı incelendi; mtime sahiplik kanıtı sayılmadı. 38 önceki fingerprint dosyası aynı. 5173 PID10320 command line doğrudan bu orijinal node_modules/vite kaynağını gösterir.

C. BASE 01c96bb950804ed11fdb512937a81b554ddd669c, commit zamanı 2026-11-11T17:09:06+03:00. Kopyalanmış snapshot'ın kapsamı Git ağacından doğrulandı; orijinalin Git geçmişi gibi gösterilmedi. CRLF ve LF için canonical hash ayrı, disk hashleri ayrı. Runtime payload'da çözümsüz conflict 0; canlı Python bridge dosyaları BASE kapsamı dışıdır. Ayrıntı V3_PWA_ORIGINAL_DIFF_MATRIX.md ve paket manifestindedir.

D. Güncel NewsPanel BASE ile aynı; payload dışı ve guard altında. MarketChart güncel BASE davranışını korur, yalnız lazy Date.now başlatması değişti. Yeni canlı drift otomatik kopyalanmaz.

E–H. Dört sembollü manuel analiz korunur. Açık teknik BUY/SELL ve WAIT/ret durumları, descriptively-only V2 pattern listesi, source SHA/first_known, boş liste ve USC varsayımsal sermaye sözleşmesi korunur. Teknik aday emir izni değildir; plan alanları broker/spread/session/risk kapıları olmadan açılmaz. Gerçek bakiye kullanılmaz.

I. Yeni kaynak backend 3c8adb810058b4738640f46bde84de8ec12205ad read-only. Yeni şema Python fixture-only HTTP üzerinden izole proxyde test edildi. Eski/opsiyonel alan eksik V5 yanıtı güvenli ret. Bugünkü yerel8006 ve Tailscale /engine/openapi.json HTTP200, aynı SHA bd970625cc25d5f1381cc928ca59b3409e7a19d507669ee57188e98dc53927ce; broker_contract/spread_status yok. BACKEND_RUNTIME_OLD; yeni broker kabulü iddiası yok.

J–L. Tam lint PASS; typecheck/build PASS; 42 API + 34 browser + 3 preview + 12 promotion testi PASS. Önceki 33 browser'a risk reset testi eklendi; preview mobil testine SW/cache kabulü eklendi. İlk başarısız denemeler ve düzeltmeleri release acceptance/eslint audit belgelerinde saklıdır.

M. 390×844 taşmasız izole fixture ekranı; fiziksel telefon testi yok. allowedHosts pc.example.ts.net; aynı-origin /engine→8006, /mt5→8005, /news→8007 korunur. HTTPS şema GET read-only çalıştı. Service-worker autoUpdate eski cihaz cache'ini tek başına kabul ettirmez; geçiş planı ayrı belgededir.

N–P. File-level paket, dokuz dosyalı payload, tam hash matrisi, hedef guardları ve sıfır yazmalı dry-run hazır. APPLY uygulanmadı; yardımcı araç APPLY kabul etmez. Backuplar ve restore bakım planı V3_PWA_PROMOTION_PACKAGE.md içinde. Orijinalde hiçbir dosya yazılmadığı için canlı HMR tetiklenmedi.

Q–R. Bu RC dört kaynak lint düzeltmesi, eslint QA kökü/üretilen çıktı ayrımı, risk browser regresyonu, cache preview kabulü, dry-run/paket araçları/testleri ve belgeleri ekler. package/lock bu RC'de değiştirilmedi. Yerel commit yalnız izole depodadır; payload hashleri nihai kodu tanımlar.

S–T. Push/merge/Actions/remote işlem yok. 5173 PID10320,8005 PID9880,8006 PID7532,8007 PID12152 aynı. Yalnız testlerin kendi rastgele port süreçleri kapandı; loglar bunu doğrular. Backend 234 fingerprint aynı. MT5 login/logout, hesap değişimi, emir veya order_check/order_send yok.

U–V. Ayrı backend runtime loaded-build kabulü; XAUUSDc exact seans kanıtı; XAUUSDc/EURUSDc/GBPUSDc/USDJPYc maksimum spread değeri, birimi, geçerlilik tarihi ve operatör/provenance onayı bekleniyor. Bu görev yeni spread gözlemi toplamamıştır; fixture spread'i gerçek gözlem değildir. Onaysız durum BLOCK kalır.

W. Operatör paketi inceleyip canlı dosya/HMR bakım operasyonuna ayrıca yetki vermeli; hemen önce dry-run ve hashler yeniden kontrol edilmeli, backup doğrulanmalı, tek kontrollü aktarım ve smoke yapılmalı. Kaynak drift'i olursa paket yeniden uzlaştırılmalı. Backend güncellemesi ve gerçek Android/Tailscale kabulü ayrıca yapılmalı.
