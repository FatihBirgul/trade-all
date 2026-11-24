# Hesap oturumu güvenliği

REAL/CONTEST/UNKNOWN hesabın analiz zincirine girmesi 503 ile engellenir. `account_info().trade_mode` SDK enumuyla tam eşleşmelidir; eksik enum fail-closed. Exact beklenen server ve currency zorunludur. Preflight'tan sonra login/server/currency/trade mode değişirse sembol okumadan hata oluşur. Hesap login'i yalnız bellek içi karşılaştırmada tutulur, API yanıtına konmaz. Balance yalnız DEMO hesapta iç risk hesabına verilir. `order_send`, `order_check`, login/logout, otomatik hesap değiştirme veya işlem yolu eklenmedi.

Bu kapı yalnız bu depodaki V5 manuel MT5 route'una uygulanır. Çalışan 8005 bridge ve diğer eski API yolları ayrıca denetlenmeden DEMO güvenli ilan edilmez. İzole DEMO terminali seçimi operatörün ayrı dış adımıdır. Terminalin analiz sırasında harici uygulama tarafından değiştirilmesi tamamen atomik olarak engellenemez; her sembol okumasından önce hesap tutarlılığı yeniden kontrol edilir.
