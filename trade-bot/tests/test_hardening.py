"""Faz 4 hata senaryolari: bot gozetimsiz calisirken beklenmeyen durumlarda para kaybettirecek bir sey yapmamali."""
import asyncio
import sqlite3

import pytest

from tests.app_helpers import NOW, feed_ticks, started
from tradebot.manager.manage import PartialClose


def posts(app):
    return app.fake.calls("POST", "/positions")


async def open_one(app):
    await app.bot.on_bar_close()
    await app.fake.flush()
    return app.repo.open_trades("bot")[0]


async def test_account_closed_for_new_positions_still_manages_open_trades(tmp_path):
    app = await started(tmp_path)
    trade = await open_one(app)
    app.fake.account_status = "close_only"  # marjin/hesap kisiti: yeni pozisyon acilamaz
    assert await app.bot.reconcile_now()  # duzenli mutabakat hesap ayarlarini da yeniler
    await app.bot.reconcile_now()
    assert app.kinds().count("account_blocked") == 1 and "account_blocked" in app.notifier.kinds()  # tek uyari
    app.advance(900)
    summary = await app.bot.on_bar_close()
    assert summary.skipped == "account_blocked"
    assert len(posts(app)) == 1
    risk = trade.initial_risk_r_price
    await app.fake.set_price("XAUUSD", round(trade.entry + risk, 2), round(trade.entry + risk + 0.2, 2))
    await app.bot.manage_tick()
    await app.fake.flush()
    assert app.repo.get_trade(trade.position_id).sl > trade.sl  # acik islem yonetilmeye devam eder


async def test_broker_refusing_new_positions_is_not_retried(tmp_path):
    app = await started(tmp_path)
    app.fake.account_status = "close_only"
    await app.bot.on_bar_close()
    await app.fake.flush()
    assert len(posts(app)) == 1 and app.repo.open_trades() == []
    for _ in range(3):  # ayni mumda ve sonraki denetimlerde emir YINELENMEZ
        await app.bot.on_bar_close()
        await app.bot.resolve_orders()
        await app.fake.flush()
    assert len(posts(app)) == 1


async def test_partial_fill_is_recorded_with_the_real_volume_and_stays_protected(tmp_path):
    app = await started(tmp_path)
    app.fake.fill_fraction = 0.5
    trade = await open_one(app)
    requested = float(posts(app)[0][2]["volume"])
    position = next(iter(app.fake.positions.values()))
    assert trade.volume == pytest.approx(float(position["volume"])) and trade.volume < requested
    assert trade.sl is not None and app.fake._sltp(position["position_id"]) is not None  # SL borsada duruyor
    # Risk hesabi gercek hacimle: gercek zarar, planlanandan buyuk olamaz.
    assert trade.initial_volume == pytest.approx(trade.volume)
    # Stop yonetimi gercek hacimle surer: 1R'de stop girise cekilir.
    risk = trade.initial_risk_r_price
    await app.fake.set_price("XAUUSD", round(trade.entry + risk, 2), round(trade.entry + risk + 0.2, 2))
    await app.bot.manage_tick()
    await app.fake.flush()
    after = app.repo.get_trade(trade.position_id)
    assert after.is_open and after.volume == pytest.approx(trade.volume) and after.sl >= trade.entry


async def test_database_write_failure_means_no_order_is_sent(tmp_path, monkeypatch):
    """Emir kaydi yazilamiyorsa (disk dolu) emir GONDERILMEZ: kaydi olmayan emir takip edilemez."""
    app = await started(tmp_path)

    def full(*args, **kwargs):
        raise sqlite3.OperationalError("database or disk is full")

    monkeypatch.setattr(app.repo, "insert_order", full)
    with pytest.raises(sqlite3.OperationalError):
        await app.bot.on_bar_close()
    await app.fake.flush()
    assert posts(app) == [] and app.repo.open_trades() == []
    monkeypatch.undo()
    summary = await app.bot.on_bar_close()  # disk acilinca bot kaldigi yerden devam eder
    assert summary.opened == 1


async def test_a_failing_periodic_task_does_not_stop_the_loop(tmp_path):
    app = await started(tmp_path)
    calls = {"n": 0}

    async def action():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("beklenmeyen hata")
        raise asyncio.CancelledError  # ucuncu turda testi bitir

    async def no_sleep(_):
        return None

    app.bot._sleep = no_sleep
    with pytest.raises(asyncio.CancelledError):
        await app.bot._every(1.0, action, "deneme")
    assert calls["n"] == 3  # iki hata donguyu durdurmadi


async def test_server_clock_behind_the_price_feed_is_reported_once(tmp_path):
    app = await started(tmp_path)
    await app.bot.heartbeat()
    assert "clock_skew" not in app.kinds()
    quote = app.bot.quotes.quote("XAUUSD")
    await feed_ticks(app, "XAUUSD", quote["bid"], quote["ask"], app.clock["now"] + 140, count=5)  # tickler ~135 sn ileride
    await app.bot.heartbeat()
    await feed_ticks(app, "XAUUSD", quote["bid"], quote["ask"], app.clock["now"] + 140, count=5)
    await app.bot.heartbeat()
    assert app.kinds().count("clock_skew") == 1 and "clock_skew" in app.notifier.kinds()
    await feed_ticks(app, "XAUUSD", quote["bid"], quote["ask"], app.clock["now"], count=5)
    await app.bot.heartbeat()
    assert "clock_ok" in app.kinds()


async def test_account_reopening_is_noticed_without_a_restart(tmp_path):
    app = await started(tmp_path)
    app.fake.account_status = "close_only"
    await app.bot.reconcile_now()
    assert (await app.bot.on_bar_close()).skipped == "account_blocked" and posts(app) == []
    app.fake.account_status = "active"
    await app.bot.reconcile_now()
    assert "account_open" in app.kinds()
    assert (await app.bot.on_bar_close()).opened == 1


async def test_a_single_future_tick_is_not_a_clock_alarm(tmp_path):
    """Inceleme I4: tek bir ileri tarihli tick uyari uretmemeli; fark iki kalp atisinda surmeli."""
    app = await started(tmp_path)
    quote = app.bot.quotes.quote("XAUUSD")
    await feed_ticks(app, "XAUUSD", quote["bid"], quote["ask"], app.clock["now"] + 11, count=5)  # 6-10 sn ileride
    await app.bot.heartbeat()
    await feed_ticks(app, "XAUUSD", quote["bid"], quote["ask"], app.clock["now"], count=5)
    await app.bot.heartbeat()
    assert "clock_skew" not in app.kinds()
    await feed_ticks(app, "XAUUSD", quote["bid"], quote["ask"], app.clock["now"] + 6, count=5)  # en cok 5 sn ileride: sinirda, ustunde degil
    await app.bot.heartbeat()
    await feed_ticks(app, "XAUUSD", quote["bid"], quote["ask"], app.clock["now"] + 6, count=5)
    await app.bot.heartbeat()
    assert "clock_skew" not in app.kinds()


async def test_malformed_account_details_never_replace_the_good_copy(tmp_path):
    """Inceleme I5: bicimi bozuk bir yanit hesap durumunu dondurmamali (bakiye/varlik guncellenmeye devam eder)."""
    app = await started(tmp_path)
    good = app.bot._details
    real_get = app.fake.get

    async def broken(path):
        if path.endswith("/account"):
            return {}
        return await real_get(path)

    app.fake.get = broken
    assert await app.bot.reconcile_now()
    assert app.bot._details is good and "account_blocked" not in app.kinds()
    app.fake.balance = 9_000.0
    assert await app.bot.reconcile_now()
    assert app.bot.account.balance == 9_000.0 and app.bot.account.can_open


async def test_a_task_that_keeps_failing_is_reported_once(tmp_path):
    app = await started(tmp_path)
    calls = {"n": 0}

    async def action():
        calls["n"] += 1
        if calls["n"] <= 8:
            raise RuntimeError("beklenmeyen hata")
        if calls["n"] == 9:
            return None  # duzeldi: sayac sifirlanir
        raise asyncio.CancelledError

    async def no_sleep(_):
        return None

    app.bot._sleep = no_sleep
    with pytest.raises(asyncio.CancelledError):
        await app.bot._every(1.0, action, "yonetim")
    assert app.kinds().count("loop_failing") == 1 and "loop_failing" in app.notifier.kinds()
    assert app.bot._loop_failures == {}


async def test_restart_does_not_wait_for_spread_samples_again(tmp_path):
    """Canlida goruldu: her dagitim/yeniden baslatmadan sonra sessiz semboller "max_spread missing" ile
    eleniyordu, cunku spread ornekleri sifirdan birikiyordu. Ornekler saklanir; kural degismez."""
    from tests.app_helpers import restart

    app = await started(tmp_path, dry_run=True)
    limit = app.bot.quotes.max_spread("XAUUSD")
    assert limit is not None
    held = len(app.bot.quotes._spreads["XAUUSD"])
    await app.bot.save_spreads()  # dakikada bir calisan kayit
    await app.bot.save_spreads()  # ikinci kayit yalnizca YENI ornekleri ekler: ornekler cogalmaz
    saved = app.repo.conn.execute("SELECT COUNT(*) FROM spread_ticks WHERE symbol = 'XAUUSD'").fetchone()[0]
    assert saved == held
    app.advance(20)  # dagitim: servis 20 sn kapali

    again = restart(app)
    await again.bot.start()
    assert again.bot.quotes.max_spread("XAUUSD") == pytest.approx(limit)
    assert again.bot.quotes.quote("XAUUSD") is None  # fiyat geri yuklenmez; taze tick beklenir

    # Eski satirlar her kayitta silinir: tablo son 30 dakikayla sinirli kalir.
    again.advance(1800 + 60)
    await again.bot.save_spreads()
    assert again.repo.conn.execute("SELECT COUNT(*) FROM spread_ticks").fetchone()[0] == 0
    again.advance(-(1800 + 60))
    # Uzun kesintiden sonra eski ornekler kullanilmaz: isinma yeniden gerekir.
    again.advance(1800 + 60)
    later = restart(again)
    await later.bot.start()
    assert later.bot.quotes.max_spread("XAUUSD") is None


async def test_spread_samples_survive_only_for_the_same_account_and_a_failed_save_is_harmless(tmp_path, monkeypatch):
    from tests.app_helpers import restart

    app = await started(tmp_path, dry_run=True)
    await app.bot.save_spreads()
    # Baska bir hesap icin saklanmis ornekler (farkli spread profili) kullanilmaz.
    assert app.repo.load_spreads(app.clock["now"] - 1800, "999999") == {}
    assert "XAUUSD" in app.repo.load_spreads(app.clock["now"] - 1800, app.fake.account_id)

    def full(*args, **kwargs):
        raise sqlite3.OperationalError("database or disk is full")

    monkeypatch.setattr(app.repo, "append_spreads", full)
    await app.bot.save_spreads()  # hata yutulur; kalp atisi ve tarama etkilenmez
    await app.bot.heartbeat()
    assert (await app.bot.on_bar_close()).would_open == 1
    monkeypatch.undo()
    again = restart(app)
    await again.bot.start()
    assert again.bot.quotes.max_spread("XAUUSD") is not None
