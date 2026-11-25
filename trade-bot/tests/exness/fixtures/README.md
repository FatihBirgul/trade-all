Bu klasordeki JSON'lar Exness OpenAPI 1.0.2 dokumanindaki orneklerden turetilmistir
(`cent_*` ve `instrument_*` dosyalarindaki bazi degerler semaya gore elle kurulmustur).

`real/` klasoru VPS'te `python -m tradebot.discover` ile alinan GERCEK yanitlardir
(2026-11-25, cent hesap, USC). Hesap numarasi ve hesap adi maskelenmistir; baska degisiklik yoktur.
`tests/exness/test_real_discovery.py` ayristiricilari bu yanitlara karsi dogrular.

Gercek ornegi henuz olmayan yanitlar (hesap bos ve akislar kurulamadigi icin): pozisyon, emir, islem
(deal), tick, WebSocket olaylari, emir ACK ve operasyon durumu. Bunlar hala dokuman orneklerine dayanir
ve ilk canli asgari lot isleminde dogrulanacaktir (PROGRESS.md).
