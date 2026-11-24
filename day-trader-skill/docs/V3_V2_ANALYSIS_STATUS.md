# V2 manuel analiz durumu

Pinlenmiş `forex/v2_bridge.py` ve V2 `c80c97f` mum formasyonu dedektörü korunuyor. Yalnız manuel V5 isteğinde çalışır. Formasyonlar descriptive-only ve first-known kapanış zamanı ile döner; yön puanı veya işlem izni vermez. V3 EMA/Wilder RSI/SMA ATR/MACD, yapı, MTF, confluence veto, fiyatlama ve risk kapıları korunur. G-001 eksik RSI, G-002 MACD sıfır, G-003 MTF future/stale ve G-004 metod varyantları önceki regresyonlarda testlidir.

Yeni V2 strateji motoru, kripto spot sağlayıcısı, gerçek hacim isteyen metotlar ve ek Skill bağlanmadı. Gerçek Forex verisiyle pattern/strategy kalibrasyonu ve özel V2 kaynak lisansı açık konudur.
