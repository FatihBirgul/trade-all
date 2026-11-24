# Exness REAL Cent para birimi ve metadata

10 Kasım 2026 salt okunur MT5 hesabı `currency=USC` döndürdü; **USDC veya USD değil**. Bu üç kod birbirine dönüştürülmez. Broker server `Exness-MT5Real50` ve dört explicit alias doğrulandı. Aşağıdaki değerler bu terminalin anlık gözlemidir; evrensel broker sabiti değildir.

| Canonical / alias | Profit currency | Contract | Tick size | Tick value (USC) | Tick loss (USC) | Point / digits | Volume min/max/step |
|---|---|---:|---:|---:|---:|---|---|
| XAUUSD / XAUUSDc | USD | 1 | 0.001 | 0.1 | 0.1 | 0.001 / 3 | 0.01 / 200 / 0.01 |
| EURUSD / EURUSDc | USD | 1000 | 0.00001 | 1 | 1 | 0.00001 / 5 | 0.01 / 200 / 0.01 |
| GBPUSD / GBPUSDc | USD | 1000 | 0.00001 | 1 | 1 | 0.00001 / 5 | 0.01 / 200 / 0.01 |
| USDJPY / USDJPYc | JPY | 1000 | 0.001 | yaklaşık 0.631971 | yaklaşık 0.632011 | 0.001 / 3 | 0.01 / 200 / 0.01 |

Stop/freeze level dört sembolde 0 görüldü; bu gelecekte sabit kalacak anlamına gelmez. Tick profit/loss USDJPY'de farklıdır. 1 lot ve 10 tick ters hareket için salt okunur broker zararları XAU 1 USC, EUR/GBP 10 USC, JPY 6.32 USC; tick modeliyle cent yuvarlaması içinde uyumludur. Minimum 0.01 lot örneğinde XAU zararı 0.00 ve JPY 0.06 USC'ye yuvarlandı. Bu yüzden risk oracle örnek lotu grid üzerinde mümkünse 1 lota yükseltildi; son lotun broker sonucu ve risk cap yine doğrulanır. Gerçek hesap bakiyesi okunmadı veya simülasyon sermayesine çevrilmedi.
