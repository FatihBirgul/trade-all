"""Evrenden sembol dusmesi (2026-11-26: altin ve gumus tarama listesinden sessizce dustu).

Katalog yalnizca acilista okunuyordu ve evren uyeligi broker'in O ANKI islem kipine bagliydi: acilista (ya da bir
olay iletisinde) isleme kapali gorunen sembol, broker yeniden acsa da surec yasadikca listede yoktu; ayar ekrani ve
backtest de o sembolu gormuyordu. Beklenen: uyelik kalici, kapali sembol kendiliginden geri doner, dusus bildirilir."""
from tests.api.test_manual_preview import client
from tests.app_helpers import build, restart, started
from tradebot.exness import schema


def close(fake, symbol, mode="close_only"):
    fake.instruments[symbol]["trade_mode"] = mode


def universe(app):
    return {i.symbol for i in app.bot.catalog.universe()}


async def test_symbol_closed_at_startup_stays_a_member_and_returns_when_the_broker_reopens_it(tmp_path):
    app = build(tmp_path)
    close(app.fake, "XAUUSD")
    await app.bot.start()
    assert "XAUUSD" not in universe(app)  # kapaliyken taranmaz, emir acilmaz (degismedi)
    assert "XAUUSD" in {i.symbol for i in app.bot.catalog.members()}
    assert app.bot.universe_status()["closed"] == {"XAUUSD": "close_only"}
    assert "symbols_dropped" not in app.notifier.kinds()  # hic taranmamis sembol "dustu" diye bildirilmez
    close(app.fake, "XAUUSD", "enabled")
    await app.bot.watch_universe()
    assert "XAUUSD" in universe(app)
    assert app.bot.universe_status()["closed"] == {}
    await app.bot.heartbeat()
    assert "XAUUSD" in app.bot._subscribed  # fiyat aboneligi de tamamlanir


async def test_drop_is_reported_once_with_the_reason_and_survives_a_restart(tmp_path):
    app = await started(tmp_path)
    assert "XAUUSD" in universe(app) and "symbols_dropped" not in app.kinds()
    close(app.fake, "XAUUSD", "trading_disabled")
    raw = dict(app.fake.instruments["XAUUSD"])
    app.bot.catalog.update(schema.parse_instrument(raw))  # broker olayi: sembol isleme kapandi
    assert "XAUUSD" not in universe(app)
    await app.bot.watch_universe()
    await app.bot.watch_universe()
    sent = [item for item in app.notifier.sent if item[0] == "symbols_dropped"]
    assert len(sent) == 1 and "XAUUSD" in sent[0][2] and "trading_disabled" in sent[0][2]
    again = restart(app)
    await again.bot.start()  # hala kapali: yeniden bildirim yok, ama durum gorunur
    assert "symbols_dropped" not in again.notifier.kinds()
    assert again.bot.universe_status()["closed"] == {"XAUUSD": "trading_disabled"}


async def test_symbol_missing_from_the_broker_catalog_after_a_restart_is_reported(tmp_path):
    app = await started(tmp_path)
    del app.fake.instruments["XAUUSD"]
    again = restart(app)
    await again.bot.start()
    sent = [item for item in again.notifier.sent if item[0] == "symbols_dropped"]
    assert len(sent) == 1 and "XAUUSD" in sent[0][2] and "katalo" in sent[0][2]


async def test_incomplete_instrument_event_does_not_remove_a_known_symbol(tmp_path):
    app = await started(tmp_path)
    partial = {k: v for k, v in app.fake.instruments["XAUUSD"].items() if k != "volume_max"}
    app.bot.catalog.update(schema.parse_instrument(partial))
    assert "XAUUSD" in universe(app)


async def test_symbol_list_and_health_keep_a_closed_member_visible(tmp_path):
    app = build(tmp_path)
    close(app.fake, "XAUUSD")
    await app.bot.start()
    async with client(app) as http:
        rows = {row["symbol"]: row for row in (await http.get("/symbols")).json()["symbols"]}
        health = (await http.get("/health")).json()
    assert rows["XAUUSD"]["open"] is False and "EURUSD" in rows
    assert health["universe"]["closed"] == {"XAUUSD": "close_only"}
    assert health["universe"]["members"] == health["universe"]["active"] + 1


async def test_partial_event_that_reports_a_close_still_closes_the_symbol(tmp_path):
    """Eksik ileti sozlesme bilgisini silemez, ama bildirdigi KAPANMA uygulanir (kapali tarafa hata)."""
    app = await started(tmp_path)
    partial = {k: v for k, v in app.fake.instruments["XAUUSD"].items() if k != "volume_max"} | {"trade_mode": "close_only"}
    app.bot.catalog.update(schema.parse_instrument(partial))
    kept = app.bot.catalog.get("XAUUSD")
    assert kept.tradable is False and kept.trade_mode == "close_only" and kept.volume_max > 0
    assert "XAUUSD" not in universe(app)
    await app.bot.watch_universe()  # broker'da hala acik: tam kayit geri getirir
    assert "XAUUSD" in universe(app)


async def test_recheck_is_bounded_and_unreadable_instruments_are_not_retried_forever(tmp_path):
    app = build(tmp_path)
    app.fake.instruments["BROKEN"] = {"instrument": 5}  # ayristirilamayan kayit (evren disi olabilir)
    await app.bot.start()
    assert app.bot.universe_status()["unreadable"] == 1 and "symbols_dropped" not in app.notifier.kinds()
    counts = []
    for _ in range(5):
        before = len(app.fake.requests)
        await app.bot.watch_universe()
        counts.append(len(app.fake.requests) - before)
    assert counts == [1, 1, 1, 0, 0]
