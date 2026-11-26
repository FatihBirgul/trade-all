import pytest

from tradebot.exness.schema import Tick
from tradebot.market.quotes import QuoteBook


def feed(book, n, spread, start=1000.0, symbol="EURUSD", bid=1.1, step=1.0):
    for i in range(n):
        book.on_tick(Tick(symbol, bid, bid + spread, start + i * step))


def test_quote_returns_latest():
    book = QuoteBook(clock=lambda: 2000.0)
    assert book.quote("EURUSD") is None
    book.on_tick(Tick("EURUSD", 1.1000, 1.1002, 1999.0))
    quote = book.quote("EURUSD")
    assert quote == {"bid": 1.1, "ask": 1.1002, "spread": pytest.approx(0.0002), "time": 1999.0}


def test_max_spread_none_until_100_ticks():
    book = QuoteBook(clock=lambda: 1100.0)
    feed(book, 99, 0.0002)
    assert book.max_spread("EURUSD") is None
    feed(book, 1, 0.0002, start=1099.0)
    assert book.max_spread("EURUSD") == pytest.approx(0.0006)


def test_max_spread_is_3x_median():
    book = QuoteBook(clock=lambda: 1200.0)
    feed(book, 60, 0.0001)
    feed(book, 41, 0.0003, start=1060.0)
    feed(book, 20, 0.0050, start=1101.0)  # haber aninda acilan spread medyani tasimaz
    assert book.max_spread("EURUSD") == pytest.approx(0.0009)


def test_max_spread_uses_only_last_30_minutes():
    now = {"t": 1000.0}
    book = QuoteBook(clock=lambda: now["t"])
    feed(book, 150, 0.0002, start=0.0)
    now["t"] = 150.0
    assert book.max_spread("EURUSD") is not None
    now["t"] = 149.0 + 1800.0 - 50  # eski tick'lerin cogu pencere disinda
    assert book.max_spread("EURUSD") is None


def test_invalid_ticks_are_ignored_and_symbols_are_independent():
    book = QuoteBook(clock=lambda: 1000.0)
    book.on_tick(Tick("EURUSD", 1.2, 1.1, 999.0))  # ask < bid
    book.on_tick(Tick("EURUSD", 0.0, 1.1, 999.0))
    assert book.quote("EURUSD") is None
    feed(book, 100, 0.5, symbol="XAUUSD", bid=2000.0, start=900.0)
    assert book.max_spread("XAUUSD") == pytest.approx(1.5)
    assert book.max_spread("EURUSD") is None


def test_snapshot_and_restore_keep_the_rule_unchanged():
    """Yeniden baslatmada isinma beklenmez, ama kural gevsemez: en az 100 ornek, yalnizca son 30 dakika."""
    now = {"t": 5000.0}
    book = QuoteBook(clock=lambda: now["t"])
    feed(book, 3000, 0.0002, start=2001.0, symbol="EURUSD")  # yogun sembol: 2001..5000
    feed(book, 99, 0.0004, start=4000.0, symbol="USDHKD")  # henuz 100 ornegi yok
    feed(book, 150, 0.0010, start=4800.0, symbol="GBPCHF")
    saved = book.snapshot()
    assert len(saved["EURUSD"]) == 200 and len(saved["USDHKD"]) == 99 and len(saved["GBPCHF"]) == 150
    assert saved["EURUSD"][0][0] < 3210.0 and saved["EURUSD"][-1][0] > 4980.0  # 30 dk pencereye yayilmis
    assert sum(w for _, _, w in saved["EURUSD"]) == 1801  # ozet, penceredeki butun tick'lerin agirligini tasir
    assert all(w == 1 for _, _, w in saved["GBPCHF"])

    fresh = QuoteBook(clock=lambda: now["t"])
    assert fresh.restore(saved) == 449
    assert fresh.max_spread("EURUSD") == pytest.approx(book.max_spread("EURUSD"))
    assert fresh.max_spread("GBPCHF") == pytest.approx(0.0030)
    assert fresh.max_spread("USDHKD") is None  # 99 ornek: kural ayni
    assert fresh.quote("EURUSD") is None  # son fiyat geri yuklenmez: taze tick gelmeden degerlendirme yok
    fresh.on_tick(Tick("USDHKD", 7.8, 7.8004, 5000.0))  # yuzuncu ornek yeni tickle gelir
    assert fresh.max_spread("USDHKD") == pytest.approx(0.0012)
    # Iki kez geri yukleme ornekleri cogaltamaz (99 ornekli sembol 198 ornekli gibi gorunemez).
    again = QuoteBook(clock=lambda: now["t"])
    assert again.restore(saved) == 449 and again.restore(saved) == 0
    assert again.max_spread("USDHKD") is None


def test_restored_history_keeps_its_weight_against_new_ticks():
    """Inceleme B-I2: yogun sembolde gecmis 200 ornege inince, yeniden baslatmadan hemen sonra genisleyen spread
    siniri hic durmamis bottan cok daha hizli yukseltiyordu. Ozet, tick agirligini tasir: iki bot ayni davranir."""
    now = {"t": 10_000.0}
    running = QuoteBook(clock=lambda: now["t"])
    feed(running, 5400, 0.0002, start=8200.5, symbol="EURUSD", step=1 / 3)  # 30 dk boyunca saniyede 3 tick
    restarted = QuoteBook(clock=lambda: now["t"])
    restarted.restore(running.snapshot())
    assert restarted.max_spread("EURUSD") == pytest.approx(running.max_spread("EURUSD"))

    # Yeniden baslatmadan sonra spread 4 katina cikar; 5 dakika boyunca ayni hizda tick gelir.
    for i in range(900):
        tick = Tick("EURUSD", 1.1, 1.1008, 10_000.0 + i / 3)
        running.on_tick(tick)
        restarted.on_tick(tick)
    now["t"] = 10_300.0
    assert running.max_spread("EURUSD") == pytest.approx(0.0006)  # medyan hala eski spread
    assert restarted.max_spread("EURUSD") == pytest.approx(0.0006)  # yeniden baslatilmis bot da ayni


def test_bucket_summary_does_not_flip_a_two_level_distribution():
    """Esit aralikli tek ornek almak, iki duzeyli (yarisi dar, yarisi 3 kat genis) dagilimda medyani ters cevirebilir."""
    now = {"t": 10_000.0}
    book = QuoteBook(clock=lambda: now["t"])
    for i in range(6000):  # %55 dar, %45 genis; karisik sirada
        wide = (i * 7919) % 100 < 45
        book.on_tick(Tick("EURUSD", 1.1, 1.1 + (0.0006 if wide else 0.0002), 8300.0 + i * 0.28))
    restored = QuoteBook(clock=lambda: now["t"])
    restored.restore(book.snapshot())
    assert restored.max_spread("EURUSD") == pytest.approx(book.max_spread("EURUSD")) == pytest.approx(0.0006)


def test_restore_ignores_stale_future_and_invalid_samples():
    now = {"t": 10_000.0}
    book = QuoteBook(clock=lambda: now["t"])
    stale = [(10_000.0 - 1801 - i, 0.0002, 1.0) for i in range(300)]  # pencereden eski
    future = [(10_001.0 + i, 0.0002, 1.0) for i in range(300)]  # gelecekten
    bad = [(9_990.0, -1.0, 1.0), (9_991.0, 0.0002, 0.0)]
    assert book.restore({"EURUSD": stale + future + bad}) == 0
    assert book.max_spread("EURUSD") is None
    # Geri yuklenen ornekler de zamanla eskir: 30 dakika sonra artik sayilmaz.
    assert book.restore({"EURUSD": [(9_000.0 + i, 0.0002, 1.0) for i in range(200)]}) == 200
    assert book.max_spread("EURUSD") == pytest.approx(0.0006)
    now["t"] += 1800 + 200
    assert book.max_spread("EURUSD") is None
