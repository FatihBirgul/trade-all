# USC finansal doğrulama

USC, USD olarak yeniden etiketlenmez. V5 çıktısı artık `account_currency` ve `spread` alanlarını açık taşır. Lot hesabı broker volume grid'inde aşağı yuvarlanır; minimum lot bütçeyi aşıyorsa bloklanır. BUY ask, SELL bid giriş davranışı; stop yönü, tick grid, spread, stop level ve risk/ödül kontrolleri korunur.

Broker `order_calc_profit` salt okunur örnek zararı, `tick_value_loss` varsa onunla, yoksa `tick_value` ile hesaplanan kayıpla karşılaştırılır. Tick değeri hesap para biriminde beyan edilmişse yüzde 1 veya 0.01 hesap birimi toleransını aşan uyuşmazlık bloklanır. Gerçek profit/konversiyon dinamiği bu toleransı aşarsa güvenli ret beklenir; broker verisi ayrıca incelenmelidir. Son lot broker zararı ve risk cap kontrolü korunur.

XAUUSDc/EURUSDc/GBPUSDc/USDJPYc BUY/SELL, USC kimliği, USD karışıklığı, minimum lot ve broker/tick uyuşmazlığı sentetik terminalle test edildi. Kullanıcının daha önce gözlemlediği XAUUSDc kontrat 1/tick 0.001/değer 0.1 USC ile EURUSDc kontrat 1000/tick 0.00001/değer 1 USC genel sabit kabul edilmedi. Gerçek Exness tick profit/loss, fiyat grid'i, swap, margin ve dönüşüm doğrulanmadı.
