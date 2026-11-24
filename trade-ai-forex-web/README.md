# Trade AI Forex Web

React ve Vite tabanlı bu PWA grafikleri, teknik önizlemeyi, risk hesaplayıcısını, haberleri ve ekonomik takvimi bir araya getirir.

Önceki web arayüzünü bu klasörde Node.js 24 ile çalıştırabilirsiniz.

```powershell
npm ci
npm run dev
```

Vite yerel geliştirme sunucusu 5173 portunu kullanır. Üretim paketini oluşturmak için `npm run build` çalıştırın. Tailscale üzerinden erişirken `TRADE_TAILSCALE_HOST` ortam değişkenine kendi cihazınızın tam ana makine adını verin.

| Vite yolu | Yerel hedef | Servis |
|---|---|---|
| `/mt5` | 127.0.0.1:8005 | Bu klasördeki `mt5_bridge:app` |
| `/news` | 127.0.0.1:8007 | Bu klasördeki `news_bridge:app` |
| `/engine` | 127.0.0.1:8008 | `../day-trader-skill` altında `forex.api:app` |

Windows başlatıcısı üç API'yi ve güncel manuel analiz arayüzünü açar. Bu klasörden `npm --prefix ../trade-ai-forex-web-v3-integration ci` çalıştırın. Başlatıcının kullandığı Python 3.11 ortamına `py -3.11 -m pip install -r ../day-trader-skill/requirements-test-py311.txt MetaTrader5` ile bağımlılıkları kurun. Windows'ta MT5 terminalinizi ve hesabınızı yapılandırın. Ardından [Windows başlatıcısını](../scripts/start-forex-windows.cmd) açabilirsiniz. Başlatıcı bilgisayarda Tailscale'i ve MT5'i açmayı dener. Başka bir süreç bir portu dinliyorsa o servisi atlar.

PWA'nın önceki 19 sembollü yapılandırması Exness cent sembol adlarını kullanır. Veri köprüsü ve V5 teknik önizlemesi beklenen broker kimliğini denetler. Dört sembollü manuel analiz uygulamasının testleri [kardeş klasördedir](../trade-ai-forex-web-v3-integration/).
