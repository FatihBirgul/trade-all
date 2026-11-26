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


async def test_shadow_trade_survives_a_two_day_outage_with_the_right_result(tmp_path):
    """Inceleme C-I1: 32 saatten uzun kesintide stopa degen mum son 128 mumun disinda kaliyor, islem 0R ya da
    kazanc diye kaydediliyordu. Sonuc, acilistan bugune butun mumlardan hesaplanir."""
    from tests.app_helpers import load_market, restart
    from tests.execution.helpers import candidate

    app = await started(tmp_path, dry_run=True)
    await app.bot.on_bar_close()
    entry = app.bot.quotes.quote("XAUUSD")["ask"]
    shadow = candidate(symbol="XAUUSD", side="BUY", setup="iki-gun-golge-0001", entry=entry, sl=entry - 5.0,
                       tp1=entry + 10.0, tp2=entry + 15.0)
    assert app.bot.shadow.open(shadow, "shadow", 70.0, app.clock["now"])
    app.advance(48 * 3600)
    load_market(app.fake, "XAUUSD", app.clock["now"])
    last = app.fake.candles[("XAUUSD", "M15")][-1]["time"]
    rows = [{"time": t, "open": entry, "high": entry + 1.0, "low": entry - 1.0, "close": entry, "volume": 100.0}
            for t in range(NOW - 300 * 900, int(last) + 900, 900)]
    hit = next(i for i, r in enumerate(rows) if r["time"] >= NOW + 900)
    rows[hit] = {**rows[hit], "low": entry - 6.0}  # acilistan sonraki ikinci mum stopa iner
    for r in rows[hit + 100:]:
        r["high"] = entry + 12.0  # cok sonra hedefin ustune cikar: yalnizca son mumlara bakilirsa "kazanc" gorunur
    app.fake.set_candles("XAUUSD", "M15", rows)
    again = restart(app)
    await again.bot.start()
    await feed_ticks(again, "XAUUSD", entry, entry + 0.2, again.clock["now"])
    await again.bot.on_bar_close()
    row = again.repo.conn.execute("SELECT result_r, closed_at FROM shadow_trades WHERE setup_id = 'iki-gun-golge-0001'").fetchone()
    assert row is not None and row["result_r"] == pytest.approx(-1.0) and row["closed_at"] == rows[hit]["time"] + 900


async def test_one_broken_trade_does_not_stop_stop_management_for_the_others(tmp_path, monkeypatch):
    """Inceleme A-I4: bir islemde hata olursa dongu orada kesiliyor, sonraki islemlerin stopu ilerlemiyordu."""
    import tradebot.app as app_module

    app = await started(tmp_path)
    trade = await open_one(app)
    await app.fake.set_price("BTCUSD", 60_000.0, 60_010.0)
    await app.fake.external_open("BTCUSD", "buy", 0.01, sl=50_000.0)  # ikinci (elle) pozisyon
    await app.fake.flush()
    await app.bot.reconcile_now()
    assert len(app.repo.open_trades()) == 2
    listed = [t.position_id for t in app.repo.open_trades()]
    real_manage = app.bot._manage_one
    seen = []

    async def flaky(item, settings, now):
        seen.append(item.position_id)
        if item.position_id == listed[0]:
            raise RuntimeError("bozuk kayit")  # listedeki ILK islem hata verir
        return await real_manage(item, settings, now)

    monkeypatch.setattr(app.bot, "_manage_one", flaky)
    with pytest.raises(RuntimeError):  # hata gizlenmez: dongu sayaci gorur
        await app.bot.manage_tick()
    assert seen == listed  # ilk islemdeki hataya ragmen ikincisi de yonetildi
    assert app_module.LOOP_ALERT_AFTER >= 2 and trade.position_id in listed


async def test_failing_loops_are_visible_on_health_and_realerted_daily(tmp_path):
    import httpx

    from tradebot.api.server import create_app

    app = await started(tmp_path)
    for _ in range(4):
        await app.bot._loop_failed("tarama", RuntimeError("x"))
    assert app.bot.failing_loops() == {} and "loop_failing" not in app.kinds()
    await app.bot._loop_failed("tarama", RuntimeError("x"))
    await app.bot._loop_failed("tarama", RuntimeError("x"))
    assert app.bot.failing_loops() == {"tarama": 6} and app.kinds().count("loop_failing") == 1
    api = create_app(app.bot, clock=lambda: app.clock["now"])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://bot") as http:
        assert (await http.get("/health")).json()["failing_loops"] == {"tarama": 6}
    app.advance(86400 + 1)
    await app.bot._loop_failed("tarama", RuntimeError("x"))
    assert app.kinds().count("loop_failing") == 2  # hata suruyorsa ertesi gun yeniden haber verilir


async def test_clock_alarm_is_not_repeated_and_needs_consecutive_beats(tmp_path):
    app = await started(tmp_path)
    quote = app.bot.quotes.quote("XAUUSD")

    async def beat(lead):
        await feed_ticks(app, "XAUUSD", quote["bid"], quote["ask"], app.clock["now"] + lead + 5, count=5)
        await app.bot.heartbeat()

    await beat(10)
    await beat(-10)  # araya normal bir kalp atisi girdi: sayac sifirlanir
    await beat(10)
    assert "clock_skew" not in app.kinds()
    await beat(10)
    await beat(10)
    await beat(10)
    assert app.kinds().count("clock_skew") == 1  # surse de tek uyari


async def test_a_new_failure_streak_alerts_again_after_recovery_and_the_scan_loop_resets(tmp_path):
    """Inceleme: duzelen gorev bir saat sonra yeniden bozulursa uyari 24 saat beklemez; hemen gidip gelen gorev
    ise bildirim yagdirmaz."""
    app = await started(tmp_path)
    for _ in range(5):
        await app.bot._loop_failed("yonetim", RuntimeError("x"))
    assert app.kinds().count("loop_failing") == 1
    app.bot._loop_ok("yonetim")
    assert app.bot.failing_loops() == {}
    for _ in range(5):  # hemen yeniden bozuldu: ayni olayin devami sayilir
        await app.bot._loop_failed("yonetim", RuntimeError("x"))
    assert app.kinds().count("loop_failing") == 1
    app.advance(3600 + 1)
    app.bot._loop_ok("yonetim")
    for _ in range(5):  # bir saat sonra yeni hata dizisi: yeniden haber verilir
        await app.bot._loop_failed("yonetim", RuntimeError("x"))
    assert app.kinds().count("loop_failing") == 2

    # Tarama dongusu de ayni sayaci kullanir ve basarili taramada sifirlar.
    calls = {"n": 0}

    async def scan():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("tarama hatasi")
        if calls["n"] == 3:
            raise asyncio.CancelledError

    async def no_sleep(_):
        return None

    app.bot.on_bar_close = scan
    app.bot._sleep = no_sleep
    with pytest.raises(asyncio.CancelledError):
        await app.bot._bar_loop()
    assert "tarama" not in app.bot._loop_failures  # ikinci (basarili) tarama sayaci sifirladi


async def test_a_persistently_broken_trade_does_not_flood_the_log(tmp_path, monkeypatch, caplog):
    import logging

    app = await started(tmp_path)
    await open_one(app)

    async def broken(item, settings, now):
        raise RuntimeError("bozuk kayit")

    monkeypatch.setattr(app.bot, "_manage_one", broken)
    caplog.set_level(logging.ERROR)
    for _ in range(50):
        with pytest.raises(RuntimeError):
            await app.bot.manage_tick()
    assert sum("stop yonetimi hatasi" in r.message for r in caplog.records) == 1


async def test_spread_medians_are_recorded_and_give_an_hourly_profile(tmp_path):
    """Ileri testin seansa gore spread'i: bot 5 dakikalik spread medyanlarini biriktirir (kapilari etkilemez)."""
    app = await started(tmp_path, dry_run=True)
    assert await app.bot.record_spreads() == 1  # yalnizca fiyati olan sembol (XAUUSD)
    hour = int(app.clock["now"] // 3600) % 24
    profile = app.repo.spread_profile()
    assert set(profile) == {"XAUUSD"} and profile["XAUUSD"]["hours"][hour] == pytest.approx(0.2)
    app.repo.add_spread_stats([("XAUUSD", app.clock["now"] + 3600, 0.6, 50), ("XAUUSD", app.clock["now"] + 3900, 0.8, 50),
                               ("XAUUSD", app.clock["now"] + 7200, 9.0, 2)], 0)  # son satir: ornek az, sayilmaz
    profile = app.repo.spread_profile()["XAUUSD"]
    assert profile["hours"][(hour + 1) % 24] == pytest.approx(0.7) and (hour + 2) % 24 not in profile["hours"]
    app.repo.add_spread_stats([], app.clock["now"] + 10_000)  # eskiler silinir
    assert app.repo.spread_profile() == {}


async def test_daily_candle_rate_limit_and_auth_errors_are_not_swallowed(tmp_path):
    """Gunluk mum ikincil veridir ama istek siniri ve kimlik hatasi taramanin kendi kurallarina birakilir."""
    from tradebot.exness.errors import ExnessRateLimited, ExnessUnavailable
    app = await started(tmp_path)

    async def limited(symbol, tf, count=256):
        raise ExnessRateLimited("limit")

    async def down(symbol, tf, count=256):
        raise ExnessUnavailable("yok")

    app.bot.candles.get = limited
    with pytest.raises(ExnessRateLimited):
        await app.bot._daily_candles("XAUUSD")
    app.bot.candles.get = down
    await app.bot._daily_candles("XAUUSD")  # gecici hata: sessizce gecilir, tarama surer


# ---------------------------------------------------------------- mutlak lot tavani
async def test_absolute_lot_ceiling_stops_an_oversized_manual_order(tmp_path):
    """Yanlislikla girilen buyuk lot (or. 10 lot) hicbir yoldan broker'a gitmez: tavan bakiyeye ve sembole baglidir."""
    import httpx
    from tests.api.test_manual_preview import client
    from tradebot import app as app_module
    app = await started(tmp_path)  # varlik 10.000; XAUUSD'de 5 birim stop = lot basina 500 zarar
    base = {"symbol": "XAUUSD", "side": "BUY", "sl_distance": 5.0, "tp_distance": 10.0}
    before = len(app.fake.requests)
    async with client(app) as http:
        preview = (await http.post("/trades/preview", json={**base, "lots": 10.0})).json()
        assert any("GÖNDERİLEMEZ" in text and "mutlak üst sınır" in text for text in preview["warnings"])
        refused = await http.post("/trades", json={**base, "lots": 10.0, "client_id": "buyuk-lot-0001"})
        assert refused.status_code == 422 and "mutlak üst sınır" in refused.json()["detail"]
        # Stopta zarar varligin %5'ini asan her lot reddedilir (1,5 lot = %7,5); sinirin altindaki kabul edilir.
        assert (await http.post("/trades", json={**base, "lots": 1.5, "client_id": "buyuk-lot-0002"})).status_code == 422
        assert len(app.fake.requests) == before and app.repo.orders_in(("PENDING", "ACKED", "UNKNOWN")) == []
        accepted = await http.post("/trades", json={**base, "lots": 0.5, "client_id": "normal-lot-0001"})
        assert accepted.status_code == 200 and accepted.json()["lots"] == 0.5
    assert isinstance(httpx.__version__, str) and app_module.HARD_MAX_RISK_PCT == 5.0


async def test_lot_ceiling_also_guards_bot_orders_and_scales_with_the_balance(tmp_path):
    import dataclasses
    from tradebot import app as app_module
    app = await started(tmp_path)
    quote = app.bot.quotes.quote("XAUUSD")
    entry = quote["ask"]
    guard = app.bot.lot_guard
    guard("XAUUSD", "BUY", 0.5, entry, entry - 5.0)  # %2,5: gecer
    with pytest.raises(ValueError, match="stopta zarar"):
        guard("XAUUSD", "BUY", 1.01, entry, entry - 5.0)  # %5'in hemen ustu
    with pytest.raises(ValueError, match="stopta zarar"):
        guard("XAUUSD", "SELL", 1.01, entry, entry + 5.0)
    # Cok dar stopla zarar kucuk gorunse de pozisyon buyuklugu varligin 50 katini asamaz.
    lots = app.bot.account.equity * app_module.HARD_MAX_NOTIONAL_X / (entry * 100.0)
    guard("XAUUSD", "BUY", lots * 0.99, entry, entry - 0.01)
    with pytest.raises(ValueError, match="katından büyük"):
        guard("XAUUSD", "BUY", lots * 1.01, entry, entry - 0.01)
    with pytest.raises(ValueError, match="yanlış tarafında"):
        guard("XAUUSD", "BUY", 0.1, entry, entry + 5.0)
    # Tavan bakiyeyle kuculur: kucuk hesapta ayni lot reddedilir.
    app.bot.account = dataclasses.replace(app.bot.account, equity=30.0)
    with pytest.raises(ValueError, match="mutlak üst sınır"):
        guard("XAUUSD", "BUY", 0.5, entry, entry - 5.0)
    guard("XAUUSD", "BUY", 0.002, entry, entry - 5.0)
    app.bot.account = None
    with pytest.raises(ValueError, match="varlığı bilinmiyor"):
        guard("XAUUSD", "BUY", 0.01, entry, entry - 5.0)


async def test_bot_order_above_the_ceiling_is_not_sent(tmp_path):
    from tradebot.signals.adapter import Candidate
    app = await started(tmp_path)
    entry = app.bot.quotes.quote("XAUUSD")["ask"]
    huge = Candidate(symbol="XAUUSD", side="BUY", entry=entry, stop_loss=entry - 5.0, take_profit_1=entry + 5.0,
                     take_profit_2=entry + 10.0, lots=10.0, strategy_id="fx_trend_momentum_v6", setup_id="tavan-testi",
                     net_rr=2.0, analysis_id="a" * 64, risk_amount=5000.0)
    before = len(app.fake.requests)
    with pytest.raises(ValueError, match="mutlak üst sınır"):
        await app.bot.executor.open(huge, "bot")
    assert len(app.fake.requests) == before and app.repo.get_order("bot-tavan-testi") is None


async def test_auth_rejections_are_recorded_with_their_source_for_diagnosis(tmp_path):
    """Her kimlik reddi kaynagiyla ve ardisik sayisiyla kaydedilir; ozet yalnizca kod/kaynak/sure verir."""
    from tradebot.exness.errors import ExnessAuthError
    app = await started(tmp_path)
    first = ExnessAuthError("AUTH_INVALID_API_KEY", code=1000, status=401)
    await app.bot._auth_error(first)
    order = ExnessAuthError("AUTH_INVALID_API_KEY", code=1000, status=401)
    order.source = "emir"
    await app.bot._auth_error(order)
    auth = app.bot.scan_summary()["auth"]
    rejects = [row for row in auth if row["kind"] == "auth_reject"]
    assert [(row["code"], row["source"], row["streak"]) for row in rejects] == [(1000, "okuma", 1), (1000, "emir", 2)]
    assert sum(1 for row in auth if row["kind"] == "auth_error") == 1  # bildirim bir kez
    app.clock["now"] += 45.0
    app.bot.client.last_ok_at = app.clock["now"]
    await app.bot._auth_ok()
    restored = [row for row in app.bot.scan_summary()["auth"] if row["kind"] == "auth_restored"]
    assert restored and restored[0]["after_seconds"] == 45.0 and app.bot._auth_streak == 0
    assert "message" not in str(app.bot.scan_summary()["auth"])


async def test_outcomes_cross_check_every_shadow_trade_with_an_independent_calculation(tmp_path):
    from tradebot.signals.adapter import Candidate
    app = await started(tmp_path)
    now = app.clock["now"]
    opened = int(now // 900) * 900 - 20 * 900 + 10.0
    bars = [{"time": int(opened // 900) * 900 + i * 900, "open": 2000.0, "high": 2000.5, "low": 1999.5, "close": 2000.0,
             "volume": 10} for i in range(-5, 19)]
    bars[8] = dict(bars[8], low=1994.0)  # stop goruldu
    app.fake.set_candles("XAUUSD", "M15", bars)
    await app.bot.candles.get("XAUUSD", "M15", 64)
    trade = Candidate(symbol="XAUUSD", side="BUY", entry=2000.0, stop_loss=1995.0, take_profit_1=2010.0,
                      take_profit_2=2010.0, lots=0.01, strategy_id="tb_ema_pullback_v1", setup_id="capraz-1", net_rr=2.0,
                      analysis_id="a" * 64, risk_amount=1.0)
    assert app.bot.shadow.open(trade, "shadow", 60.0, opened, 0.2)
    app.bot.shadow.resolve("XAUUSD", app.bot.candles.cached("XAUUSD", "M15", 64), now)
    report = app.bot.dryrun_outcomes()
    row = report["shadows"][-1]
    assert row["result_r"] == -1.0 == row["check_r"] and row["mae_r"] <= -1.0 and row["bars"] == 4
    assert report["shadow_check"]["agree"] == 1 and report["shadow_check"]["differ"] == 0
    # Kayit bozulursa (sonuc yanlissa) capraz denetim bunu gosterir.
    app.repo.conn.execute("UPDATE shadow_trades SET result_r = 2.0")
    assert app.bot.dryrun_outcomes()["shadow_check"]["differ"] == 1


async def test_public_summary_says_whether_closed_positions_had_a_broker_side_stop(tmp_path):
    from tradebot.store.repo import Trade
    app = await started(tmp_path)
    now = app.clock["now"]
    app.repo.upsert_trade(Trade(position_id="p-1", origin="manual", symbol="XAUUSD", side="SELL", volume=0.0, entry=2000.0,
                                sl=2005.0, tp2=1990.0, last_sl=2005.0, sltp_order_id="o-1", opened_at=now - 300,
                                closed_at=now - 60, close_price=2000.2, pnl=-0.18))
    app.repo.upsert_trade(Trade(position_id="p-2", origin="manual", symbol="XAUUSD", side="BUY", volume=0.0, entry=2000.0,
                                opened_at=now - 200, closed_at=now - 100, close_price=2000.0, pnl=0.0))
    positions = app.bot.scan_summary()["positions"]
    assert positions["sl_missing_events"] == 0
    assert positions["closed"] == [
        {"origin": "manual", "symbol": "XAUUSD", "side": "BUY", "held_s": 100, "stop_seen": False, "sltp_order": False,
         "target_seen": False},
        {"origin": "manual", "symbol": "XAUUSD", "side": "SELL", "held_s": 240, "stop_seen": True, "sltp_order": True,
         "target_seen": True}]  # kapanis sirasiyla
    assert "0.18" not in str(positions) and "2005" not in str(positions)  # tutar ve fiyat yok


async def test_lot_ceiling_fails_closed_when_it_cannot_be_checked(tmp_path):
    """Giris, stop ya da lot bilinmiyorsa tavan denetlenemez: emir GONDERILMEZ (sessizce gecmez)."""
    app = await started(tmp_path)
    entry = app.bot.quotes.quote("XAUUSD")["ask"]
    guard = app.bot.lot_guard
    for lots, price, stop in ((0.1, entry, None), (0.0, entry, entry - 5.0), (float("nan"), entry, entry - 5.0)):
        with pytest.raises(ValueError, match="denetlenemedi"):
            guard("XAUUSD", "BUY", lots, price, stop)
    guard("XAUUSD", "BUY", 0.1, None, entry - 5.0)  # fiyat verilmediyse anlik fiyat kullanilir
    app.bot.quotes._last.clear()
    with pytest.raises(ValueError, match="denetlenemedi"):
        guard("XAUUSD", "BUY", 0.1, None, entry - 5.0)  # fiyat da yoksa emir yok


async def test_swap_is_measured_read_only_from_positions_held_overnight(tmp_path):
    """Gecelik faiz orani API'de yok: en az bir gece tasinmis pozisyonun birikmis swap'indan olculur. Yalnizca
    oran saklanir (tutar yok); hicbir istek gonderilmez, hicbir karar etkilenmez."""
    from tradebot.exness.schema import Position
    app = await started(tmp_path)
    now = app.clock["now"]
    entry = app.bot.quotes.quote("XAUUSD")["ask"]
    notional = abs(app.bot.provider.loss_for("XAUUSD", "BUY", 0.1, entry, 0.0))
    held = Position(id="p-gece", symbol="XAUUSD", side="BUY", volume=0.1, open_price=entry, swap=-notional * 0.05 / 365 * 2,
                    opened_at=now - 2 * 86400)
    fresh = Position(id="p-yeni", symbol="XAUUSD", side="SELL", volume=0.1, open_price=entry, swap=0.0, opened_at=now - 600)
    before = len(app.fake.requests)
    assert app.bot._observe_swaps([held, fresh]) == ["XAUUSD|BUY"]  # swap ilk kez sifirdan farkli goruldu
    assert app.bot._observe_swaps([held, fresh]) == []  # ayni durum yeniden bildirilmez
    seen = app.bot.scan_summary()["swap_observed"]
    assert list(seen) == ["XAUUSD|BUY"]  # ayni gun acilan pozisyon olculmez
    assert seen["XAUUSD|BUY"]["nights"] == 2 and seen["XAUUSD|BUY"]["rate_pct_year"] == pytest.approx(-5.0, abs=0.01)
    assert seen["XAUUSD|BUY"]["zero"] is False and len(app.fake.requests) == before
    free = Position(id="p-sifir", symbol="XAUUSD", side="SELL", volume=0.1, open_price=entry, swap=0.0,
                    opened_at=now - 3 * 86400)
    assert app.bot._observe_swaps([free]) == []  # swap 0: bildirim yok
    assert app.bot.scan_summary()["swap_observed"]["XAUUSD|SELL"] == {"at": round(now), "nights": 3, "rate_pct_year": 0.0,
                                                                     "zero": True}
    assert str(round(notional)) not in str(app.bot.scan_summary()["swap_observed"])  # tutar yok
    assert app.bot._observe_swaps([Position(id="p-bozuk", symbol="YOKUSD", side="BUY", volume=0.1, open_price=1.0,
                                            opened_at=now - 3 * 86400)]) == []  # bilinmeyen sembol botu etkilemez


async def test_owner_is_told_once_when_a_swap_free_account_starts_paying_swap(tmp_path):
    """Hesap swap'siz; broker statuyu geri alirsa gece tasinan pozisyonda swap gorulur ve BIR kez bildirilir."""
    from tradebot.exness.schema import Position
    app = await started(tmp_path)
    now = app.clock["now"]
    entry = app.bot.quotes.quote("XAUUSD")["ask"]
    calls = {"n": 0}
    position = Position(id="p-gece", symbol="XAUUSD", side="BUY", volume=0.1, open_price=entry, swap=0.0,
                        opened_at=now - 2 * 86400)

    async def fake_reconcile():
        from tradebot.execution.reconcile import ReconcileReport
        calls["n"] += 1
        return ReconcileReport(account=app.bot.account, positions=[position])

    app.bot.executor.reconcile = fake_reconcile
    await app.bot.reconcile_now()
    assert "swap_charged" not in app.kinds()  # swap 0: sessiz
    position = Position(id="p-gece", symbol="XAUUSD", side="BUY", volume=0.1, open_price=entry, swap=-1.25,
                        opened_at=now - 2 * 86400)
    await app.bot.reconcile_now()
    await app.bot.reconcile_now()
    assert app.kinds().count("swap_charged") == 1 and calls["n"] == 3
    event = next(e for e in app.repo.events() if e["kind"] == "swap_charged")
    assert "1.25" not in event["message"] and "1,25" not in event["message"]  # tutar yazilmaz
    assert any(item[0] == "swap_charged" for item in app.notifier.sent)


async def test_missing_swap_field_is_not_reported_as_swap_free(tmp_path):
    """API pozisyonda swap alanini vermezse olcum yapilmaz: "swap 0" diye yanlis teyit uretilmez."""
    from tradebot.exness.schema import Position
    app = await started(tmp_path)
    now = app.clock["now"]
    entry = app.bot.quotes.quote("XAUUSD")["ask"]
    unknown = Position(id="p-1", symbol="XAUUSD", side="BUY", volume=0.1, open_price=entry, swap=None,
                       opened_at=now - 2 * 86400)
    bad = Position(id="p-2", symbol="YOKUSD", side="BUY", volume=0.1, open_price=1.0, swap=-1.0, opened_at=now - 2 * 86400)
    good = Position(id="p-3", symbol="XAUUSD", side="SELL", volume=0.1, open_price=entry, swap=0.0,
                    opened_at=now - 2 * 86400)
    assert app.bot._observe_swaps([unknown, bad, good]) == []
    assert list(app.bot.scan_summary()["swap_observed"]) == ["XAUUSD|SELL"]  # bozuk kayit digerini dusurmez
    listed = app.bot.scan_summary()["swap_listed"]
    assert isinstance(listed, dict)
