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


def test_restore_keeps_the_rule_unchanged():
    """Yeniden baslatmada isinma beklenmez, ama kural gevsemez: en az 100 ornek, yalnizca son 30 dakika."""
    now = {"t": 5000.0}
    book = QuoteBook(clock=lambda: now["t"])
    feed(book, 3000, 0.0002, start=2001.0, symbol="EURUSD")  # yogun sembol: 2001..5000
    feed(book, 99, 0.0004, start=4000.0, symbol="USDHKD")  # henuz 100 ornegi yok
    feed(book, 150, 0.0010, start=4800.0, symbol="GBPCHF")
    saved = book.drain_new()
    assert len(saved["EURUSD"]) == 3000 and len(saved["USDHKD"]) == 99  # ozetlenmeden, tick tick
    assert book.drain_new() == {}  # ayni ornek iki kez saklanmaz

    fresh = QuoteBook(clock=lambda: now["t"])
    assert fresh.restore(saved) == 1801 + 99 + 150  # pencereden eski EURUSD ornekleri yuklenmedi
    assert fresh.max_spread("EURUSD") == book.max_spread("EURUSD")
    assert fresh.max_spread("GBPCHF") == pytest.approx(0.0030)
    assert fresh.max_spread("USDHKD") is None  # 99 ornek: kural ayni
    assert fresh.quote("EURUSD") is None  # son fiyat geri yuklenmez: taze tick gelmeden degerlendirme yok
    fresh.on_tick(Tick("USDHKD", 7.8, 7.8004, 5000.0))  # yuzuncu ornek yeni tickle gelir
    assert fresh.max_spread("USDHKD") == pytest.approx(0.0012)
    # Iki kez geri yukleme ornekleri cogaltamaz (99 ornekli sembol 198 ornekli gibi gorunemez).
    again = QuoteBook(clock=lambda: now["t"])
    assert again.restore(saved) == 2050 and again.restore(saved) == 0
    assert again.max_spread("USDHKD") is None


def test_restarted_book_matches_one_that_never_restarted():
    """Sahibin sarti: yeniden baslatilmis bot, hic durmamis bottan daha GENIS bir sinir hesaplamamali.
    Ornekler ozetlenmeden saklandigi icin ikisi her an AYNI siniri verir: rejim degistiren ve carpik
    dagilimlar, farkli tick hizlari, art arda yeniden baslatmalar ve 8000 ornek siniri dahil."""
    import random

    rng = random.Random(20261126)
    for rate in (0.2, 1.0, 3.0, 6.0):  # saniyedeki tick; 6/s'de 30 dakika 8000 ornek sinirini asar
        now = {"t": 100_000.0}
        running = QuoteBook(clock=lambda: now["t"])
        restarted = QuoteBook(clock=lambda: now["t"])
        saved: dict[str, list] = {}
        wide = False
        for second in range(4200):  # 70 dakika
            if second % rng.choice((120, 300, 600, 900)) == 0:
                wide = rng.random() < 0.5  # dar / genis rejim
            for _ in range(int(rate) + (rng.random() < rate % 1)):
                level = (0.0008 if wide else 0.0002) * rng.choice((1.0, 1.0, 1.0, 1.5, 3.0))  # saga carpik
                tick = Tick("EURUSD", 1.1, 1.1 + level, now["t"] + rng.random())
                running.on_tick(tick)
                restarted.on_tick(tick)
            now["t"] += 1.0
            if second % 700 == 699:  # yeniden baslatma: kayit, yeni defter, geri yukleme
                for symbol, items in restarted.drain_new().items():
                    saved.setdefault(symbol, []).extend(items)
                restarted = QuoteBook(clock=lambda: now["t"])
                restarted.restore(saved)
            if second % 37 == 0:
                assert restarted.max_spread("EURUSD") == running.max_spread("EURUSD"), (rate, second)


def test_restore_ignores_stale_future_and_invalid_samples():
    now = {"t": 10_000.0}
    book = QuoteBook(clock=lambda: now["t"])
    stale = [(10_000.0 - 1801 - i, 0.0002) for i in range(300)]  # pencereden eski
    future = [(10_001.0 + i, 0.0002) for i in range(300)]  # gelecekten
    bad = [(9_990.0, -1.0)]
    assert book.restore({"EURUSD": stale + future + bad}) == 0
    assert book.max_spread("EURUSD") is None
    # Geri yuklenen ornekler de zamanla eskir: 30 dakika sonra artik sayilmaz.
    assert book.restore({"EURUSD": [(9_000.0 + i, 0.0002) for i in range(200)]}) == 200
    assert book.max_spread("EURUSD") == pytest.approx(0.0006)
    now["t"] += 1800 + 200
    assert book.max_spread("EURUSD") is None
    # Ayni zamanli, ayni spread'li iki ayri tick iki ornektir (birlestirilmez).
    twin = QuoteBook(clock=lambda: 10_000.0)
    assert twin.restore({"EURUSD": [(9_999.0, 0.0002)] * 120}) == 120
    assert twin.max_spread("EURUSD") == pytest.approx(0.0006)


def test_restore_sorts_samples_by_time():
    """Sirasiz verilen ornekler zamana gore dizilir; yoksa pencere disina cikan eski ornek kuyrukta kalirdi."""
    clock = {"now": 10_000.0}
    book = QuoteBook(clock=lambda: clock["now"])
    saved = [(9_990.0 - i, 5.0) for i in range(60)] + [(8_300.0 + i, 1.0) for i in range(60)]
    assert book.restore({"XAUUSD": saved}) == 120
    clock["now"] = 10_200.0  # 8300..8359 artik pencere disinda: kalan 60 ornek sinirin altinda
    assert book.max_spread("XAUUSD") is None
