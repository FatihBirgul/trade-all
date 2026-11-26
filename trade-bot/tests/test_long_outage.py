"""Uzun kesintiden sonra acilis: kacirilan mumlar cekilir, sanal islemler dogru sonuclanir, eski sinyale emir yok."""
import pytest

from tests.app_helpers import NOW, feed_ticks, load_market, restart, started
from tests.execution.helpers import candidate
from tradebot.exness import schema

M15 = 900
HOUR = 3600


def posts(app):
    return app.fake.calls("POST", "/positions")


def m15_times(app, symbol="XAUUSD"):
    return [r[0] for r in app.bot.candles._db.execute(
        "SELECT time FROM candles WHERE symbol = ? AND tf = 'M15' ORDER BY time", (symbol,))]


async def reopen(app, hours):
    """Servis `hours` saat kapali kalir; piyasa bu arada ilerler. (H4 mumlari hizali kalsin diye 4 saatin kati.)"""
    app.advance(hours * HOUR)
    bid, ask = load_market(app.fake, "XAUUSD", app.clock["now"])
    again = restart(app)
    await again.bot.start()
    await feed_ticks(again, "XAUUSD", bid, ask, again.clock["now"])
    return again


async def test_missed_candles_are_fetched_without_a_hole_after_hours_down(tmp_path):
    app = await started(tmp_path, dry_run=True)
    await app.bot.on_bar_close()
    before = m15_times(app)
    again = await reopen(app, 8)
    summary = await again.bot.on_bar_close()
    times = m15_times(again)
    assert times[-1] == before[-1] + 8 * HOUR  # en yeni kapanmis mum cekildi
    recent = times[-256:]
    assert all(b - a == M15 for a, b in zip(recent, recent[1:]))  # kesinti araliginda bosluk yok
    assert summary.errors == 0 and "XAUUSD" not in summary.data_rejects


async def test_open_trade_is_still_managed_and_no_second_order_for_the_old_setup(tmp_path):
    app = await started(tmp_path)
    await app.bot.on_bar_close()
    await app.fake.flush()
    trade = app.repo.open_trades("bot")[0]
    assert len(posts(app)) == 1

    again = await reopen(app, 8)
    assert [t.position_id for t in again.repo.open_trades("bot")] == [trade.position_id]
    assert len(posts(again)) == 1  # acilis emir gondermedi
    await again.bot.on_bar_close()
    await again.fake.flush()
    # Ayni sembolde acik islem varken yeni emir yok (sembol basina tek islem); eski setup yeniden acilmaz.
    assert len(posts(again)) == 1
    risk = trade.initial_risk_r_price
    await again.fake.set_price("XAUUSD", round(trade.entry + risk, 2), round(trade.entry + risk + 0.2, 2))
    await again.bot.manage_tick()
    await again.fake.flush()
    assert again.repo.get_trade(trade.position_id).sl >= trade.entry  # stop yonetimi surer


async def test_shadow_trade_is_resolved_from_bars_that_closed_while_down(tmp_path):
    app = await started(tmp_path, dry_run=True)
    await app.bot.on_bar_close()
    quote = app.bot.quotes.quote("XAUUSD")
    entry = quote["ask"]
    shadow = candidate(symbol="XAUUSD", side="BUY", setup="kesinti-golge-0001", entry=entry, sl=entry - 5.0,
                       tp1=entry + 10.0, tp2=entry + 15.0)
    assert app.bot.shadow.open(shadow, "shadow", 70.0, app.clock["now"])

    # Kesinti sirasinda fiyat once stopa iner: sanal islem -1R ile kapanmis olmali (kapanis ani kesintinin icinde).
    app.advance(8 * HOUR)
    load_market(app.fake, "XAUUSD", app.clock["now"])
    rows = app.fake.candles[("XAUUSD", "M15")]
    # Kesinti araligindaki mumlar duz (ne stop ne hedef); yalnizca DORDUNCU mum stopa iner.
    for i, r in enumerate(rows):
        if r["time"] >= NOW:
            rows[i] = {**r, "open": entry, "high": entry + 1.0, "low": entry - 1.0, "close": entry}
    hit = next(i for i, r in enumerate(rows) if r["time"] >= NOW + 3 * M15)
    rows[hit] = {**rows[hit], "low": entry - 6.0}
    app.fake.set_candles("XAUUSD", "M15", rows)
    again = restart(app)
    await again.bot.start()
    bid, ask = rows[-1]["close"], rows[-1]["close"] + 0.2
    await feed_ticks(again, "XAUUSD", bid, ask, again.clock["now"])
    await again.bot.on_bar_close()
    row = again.repo.conn.execute(
        "SELECT result_r, closed_at FROM shadow_trades WHERE setup_id = 'kesinti-golge-0001'").fetchone()
    assert row["result_r"] == pytest.approx(-1.0)
    assert row["closed_at"] == rows[hit]["time"] + M15  # stopa inen mumun kapanis ani; yeniden baslatma ani degil
    assert row["closed_at"] < NOW + 8 * HOUR


async def test_days_long_outage_refills_the_cache_from_scratch(tmp_path):
    app = await started(tmp_path, dry_run=True)
    await app.bot.on_bar_close()
    again = await reopen(app, 24 * 28)  # dort hafta: onbellekteki son mum, tek istekle cekilebilen araligin disinda
    before = len(again.fake.calls("GET", "/candles"))
    summary = await again.bot.on_bar_close()
    # Aralik "son mumdan bugune" degil (tek istege sigmaz, ortasi bos kalirdi): en yeni `max_candles` mum istenir.
    asked = [c[1] for c in again.fake.calls("GET", "/candles")[before:] if "instrument=XAUUSD&timeframe=M15" in c[1]]
    now = again.clock["now"]
    oldest = now - now % M15 - (again.bot.candles.max_candles - 1) * M15
    assert len(asked) == 1 and f"from={schema._iso(oldest)}" in asked[0]
    recent = m15_times(again)[-200:]
    assert recent[-1] == again.clock["now"] - M15 - (again.clock["now"] % M15)
    assert max(b - a for a, b in zip(recent, recent[1:])) == M15
    assert summary.errors == 0 and summary.scanned >= 1


async def test_restart_in_the_same_bar_never_sends_the_same_setup_twice(tmp_path):
    """Sembol bosalsa bile (islem stopla kapandi) ayni mumun ayni kurulumu icin ikinci emir gonderilmez."""
    app = await started(tmp_path)
    await app.bot.on_bar_close()
    await app.fake.flush()
    trade = app.repo.open_trades("bot")[0]
    quote = app.bot.quotes.quote("XAUUSD")
    await app.fake.set_price("XAUUSD", trade.sl - 0.5, trade.sl - 0.3)  # stop tetiklendi: sembolde acik islem kalmadi
    await app.fake.flush()

    again = restart(app)  # ayni M15 mumunun icinde yeniden baslatma
    await again.bot.start()
    assert again.repo.open_trades("bot") == []
    await feed_ticks(again, "XAUUSD", quote["bid"], quote["ask"], again.clock["now"])  # fiyat geri geldi
    summary = await again.bot.on_bar_close()
    await again.fake.flush()
    # Iki katman korur: `already_submitted` denetimi ve emir kaydinin tekil anahtari (`bot-<setup>`).
    # Biri bozulsa digeri tutar; burada sonuc (borsaya giden emir sayisi) sinanir.
    assert len(posts(again)) == 1, summary
    assert again.repo.conn.execute("SELECT COUNT(*) FROM orders WHERE kind = 'open'").fetchone()[0] == 1
