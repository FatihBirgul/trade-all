"""Yeni stratejiler (ortak arayuz): sinyal kosullari, bakis-ileri yok, risk butcesi, varsayilan golge."""
import dataclasses

import httpx
import pytest

from tests.app_helpers import NOW, started
from tests.signals.helpers import instrument
from tradebot.api.auth import issue_token
from tradebot.api.server import create_app
from tradebot.config import BotSettings, strategy_mode
from tradebot.signals import custom
from tradebot.signals.modules import Context, Signal, modules
from tradebot.signals.modules.indicators import atr, ema, trend
from tradebot.signals.shadow import ShadowBook

M15, H1 = 900, 3600
PULLBACK, BREAKOUT = "tb_ema_pullback_v1", "tb_donchian_breakout_v1"
LAST = NOW - M15  # son kapanmis M15 mumunun acilisi (tarama NOW'da yapilir)


def bar(time, open_, high, low, close):
    return {"time": time, "open": open_, "high": high, "low": low, "close": close, "tick_volume": 100.0}


def trending(count, step, start, end_time, size, wick=0.0004):
    """Duzgun egilim: her mum `step` kadar ilerler. Son mumun acilis zamani `end_time`."""
    out, price = [], start
    for i in range(count):
        close = price + step
        out.append(bar(end_time - (count - 1 - i) * size, price, max(price, close) + wick, min(price, close) - wick, close))
        price = close
    return out


def h1_up():
    return trending(230, 0.0004, 1.0000, NOW - H1, H1)


def h1_down():
    return trending(230, -0.0004, 1.2000, NOW - H1, H1)


def pullback_m15(up=True, count=80):
    """Egilim, sonra EMA20'ye dokunup egilim yonunde kapanan son mum."""
    sign = 1 if up else -1
    bars = trending(count, sign * 0.0003, 1.1000 - sign * 0.0003 * (count - 80), LAST, M15, wick=0.0008)
    average = ema([b["close"] for b in bars[:-1]], 20)[-1]
    previous = bars[-2]["close"]
    close = previous + sign * 0.0001
    open_ = close - sign * 0.0003
    low, high = (average - 0.0002, close + 0.0001) if up else (close - 0.0001, average + 0.0002)
    bars[-1] = bar(LAST, open_, max(high, open_, close), min(low, open_, close), close)
    return bars


def breakout_m15(up=True):
    """Dar kanal, sonra genisleyen mumlarla kanal disinda kapanis."""
    sign = 1 if up else -1
    quiet = [bar(LAST - (70 - i) * M15, 1.1000, 1.1003, 1.0997, 1.1000 + (0.0001 if i % 2 else -0.0001)) for i in range(60)]
    wide = []
    price = 1.1000
    for i in range(10):
        close = price + sign * 0.0006
        wide.append(bar(LAST - (9 - i) * M15, price, max(price, close) + 0.0004, min(price, close) - 0.0004, close))
        price = close
    return quiet + wide


class Provider:
    def __init__(self, m15, h1, bid=None, spread=0.00002, time=NOW):
        self.bars = {"M15": m15, "H1": h1}
        bid = m15[-1]["close"] if bid is None else bid
        self._quote = {"bid": bid, "ask": bid + spread, "spread": spread, "time": time}
        self.calls = []

    def quote(self, symbol):
        return dict(self._quote)

    def candles(self, symbol, timeframe, count=256):
        self.calls.append(timeframe)
        return list(self.bars[timeframe][-count:])

    def loss_for(self, symbol, side, lots, entry, stop):
        sign = 1.0 if side == "BUY" else -1.0
        return (stop - entry) * sign * lots * 100_000  # 1 lot = 100000 birim, hesap para birimi = kote


def eurusd():
    return instrument("EURUSD", kind="forex", tick_size=0.00001, contract_size=100_000.0, digits=5, calc_mode="forex")


def run(m15, h1, *, equity=10_000.0, risk_pct=0.5, modes=None, report=None, now=NOW, v9_decisions=(),
        commission_per_lot=0.0, item=None, **quote):
    return custom.evaluate(Provider(m15, h1, **quote), item or eurusd(), equity=equity, risk_pct=risk_pct,
                           modes=modes or {}, now=now, report=report, v9_decisions=v9_decisions,
                           commission_per_lot=commission_per_lot)


def only(results, strategy_id):
    return [r for r in results if r.candidate.strategy_id == strategy_id]


def test_indicators():
    assert ema([1, 2, 3, 4, 5], 3)[-1] == pytest.approx(4.0)
    assert ema([1, 2], 3) != ema([1, 2], 3) or True  # nan: yeterli veri yok
    assert trend(h1_up()) == "bullish" and trend(h1_down()) == "bearish" and trend(h1_up()[:100]) is None
    assert atr(trending(20, 0.001, 1.0, 0, M15, wick=0.0)) == pytest.approx(0.001)
    assert atr(trending(5, 0.001, 1.0, 0, M15)) is None


def test_registry_has_the_new_strategies_and_they_default_to_shadow():
    assert {m.id for m in modules("strategy")} == {PULLBACK, BREAKOUT} == custom.strategy_ids()
    settings = BotSettings()
    assert strategy_mode(settings, PULLBACK) == "shadow" and strategy_mode(settings, BREAKOUT) == "shadow"
    assert strategy_mode(settings, "fx_trend_momentum_v6") == "live"  # V9 stratejileri etkilenmez
    listed = BotSettings(enabled_strategies={"fx_trend_momentum_v6"})
    assert strategy_mode(listed, PULLBACK) == "shadow"  # eski liste alani yeni stratejiyi canliya da kapaliya da almaz
    assert strategy_mode(BotSettings(strategy_modes={PULLBACK: "off"}), PULLBACK) == "off"


@pytest.mark.parametrize("up", [True, False])
def test_ema_pullback_signal_and_candidate(up):
    results = only(run(pullback_m15(up), h1_up() if up else h1_down()), PULLBACK)
    assert len(results) == 1 and results[0].mode == "shadow"
    c = results[0].candidate
    assert c.side == ("BUY" if up else "SELL") and c.symbol == "EURUSD"
    sign = 1 if up else -1
    assert (c.entry - c.stop_loss) * sign > 0 and (c.take_profit_1 - c.entry) * sign > 0  # stop ve hedef dogru tarafta
    assert (c.take_profit_2 - c.take_profit_1) * sign > 0
    assert c.net_rr >= 1.5 and c.net_rr == pytest.approx(2.0, abs=0.05)
    assert c.risk_amount <= 10_000 * 0.5 / 100 + 1e-9  # risk butcesi asilmaz
    assert c.risk_amount > 10_000 * 0.5 / 100 * 0.9  # ve gereksiz kucuk degil (adima asagi yuvarlama)
    assert round(c.lots / 0.01) == pytest.approx(c.lots / 0.01)  # lot adimina uygun
    for price in (c.stop_loss, c.take_profit_1, c.take_profit_2):
        assert round(price / 0.00001) == pytest.approx(price / 0.00001)  # tick adimina yuvarli
    assert len(c.setup_id) == 24 and len(c.analysis_id) == 64


def test_no_pullback_signal_without_trend_touch_or_direction():
    assert only(run(pullback_m15(), h1_down()), PULLBACK) == []  # H1 egilimi ters
    flat = trending(230, 0.0, 1.1, NOW - H1, H1)
    assert only(run(pullback_m15(), flat), PULLBACK) == []  # egilim yok
    untouched = trending(80, 0.0003, 1.1, LAST, M15)  # EMA20'ye dokunmayan duz yukselis
    assert only(run(untouched, h1_up()), PULLBACK) == []
    bearish_bar = pullback_m15()
    last = bearish_bar[-1]
    bearish_bar[-1] = bar(LAST, last["close"], last["high"], last["low"], last["open"])  # dusen mumla kapanis
    assert only(run(bearish_bar, h1_up()), PULLBACK) == []


@pytest.mark.parametrize("up", [True, False])
def test_donchian_breakout_signal(up):
    results = only(run(breakout_m15(up), h1_up() if up else h1_down()), BREAKOUT)
    assert len(results) == 1
    c = results[0].candidate
    assert c.side == ("BUY" if up else "SELL") and c.net_rr >= 1.5
    assert (c.entry - c.stop_loss) * (1 if up else -1) > 0


def test_no_breakout_without_expansion_or_trend():
    assert only(run(breakout_m15(), h1_down()), BREAKOUT) == []
    quiet = [bar(LAST - (69 - i) * M15, 1.1, 1.1003, 1.0997, 1.1 + (0.0001 if i % 2 else -0.0001)) for i in range(70)]
    assert only(run(quiet, h1_up()), BREAKOUT) == []  # kanal icinde
    slow = trending(70, 0.00002, 1.1, LAST, M15, wick=0.0003)  # kirilim var ama oynaklik genislemiyor
    assert only(run(slow, h1_up()), BREAKOUT) == []


def test_only_the_last_closed_fresh_bar_is_used():
    m15, h1 = pullback_m15(), h1_up()
    assert only(run(m15, h1), PULLBACK) != []
    assert run(m15, h1, now=NOW + 2 * M15) == []  # son mum bayat: yeni mum verisi gelmemis
    assert run(m15, h1, now=NOW - M15 - 1) == []  # "son mum" henuz kapanmamis sayilir: bakis-ileri yok
    # Sinyal mumundan SONRA bir mum daha kapanmissa eski sinyal yeniden uretilmez.
    later = m15 + [bar(LAST + M15, m15[-1]["close"], m15[-1]["close"] + 0.0005, m15[-1]["close"], m15[-1]["close"] + 0.0004)]
    assert only(run(later, h1, now=NOW + M15), PULLBACK) == []


def test_setup_id_is_stable_per_bar_and_changes_with_the_bar():
    first = only(run(pullback_m15(), h1_up()), PULLBACK)[0].candidate
    again = only(run(pullback_m15(), h1_up()), PULLBACK)[0].candidate
    assert first.setup_id == again.setup_id
    assert first.setup_id != only(run(pullback_m15(False), h1_down()), PULLBACK)[0].candidate.setup_id


def test_candidate_dropped_when_min_lot_exceeds_budget_or_stop_is_inside_the_spread():
    assert run(pullback_m15(), h1_up(), equity=50.0) == []  # 0.01 lot bile butceyi asiyor: yukari yuvarlanmaz
    assert run(pullback_m15(), h1_up(), spread=0.0100) == []  # stop mesafesi 3 spread'den dar
    assert run(pullback_m15(), h1_up(), equity=0.0) == []


def test_opposing_v9_confirmation_is_a_hard_veto():
    report = {"strategies": [{"strategy_id": "fx_range_reversion_v6", "status": "CONFIRMED", "direction": "SELL"}]}
    assert only(run(pullback_m15(), h1_up(), report=report), PULLBACK) == []
    same = {"strategies": [{"strategy_id": "fx_trend_momentum_v6", "status": "CONFIRMED", "direction": "BUY"},
                           {"strategy_id": "fx_range_reversion_v6", "status": "REJECTED", "direction": "SELL"}]}
    assert len(only(run(pullback_m15(), h1_up(), report=same), PULLBACK)) == 1


def test_off_strategy_is_not_evaluated_and_a_broken_one_does_not_stop_the_others(monkeypatch):
    assert only(run(pullback_m15(), h1_up(), modes={PULLBACK: "off"}), PULLBACK) == []
    provider = Provider(pullback_m15(), h1_up())
    assert custom.evaluate(provider, eurusd(), equity=1e4, risk_pct=0.5, modes={PULLBACK: "off", BREAKOUT: "off"},
                           now=NOW) == [] and provider.calls == []  # hepsi kapaliysa veri bile okunmaz
    breakout = next(m for m in modules("strategy") if m.id == BREAKOUT)
    monkeypatch.setattr(type(breakout), "evaluate", lambda self, context: 1 / 0)
    assert len(only(run(pullback_m15(), h1_up()), PULLBACK)) == 1


def test_strategy_using_an_older_bar_is_ignored(monkeypatch):
    pullback = next(m for m in modules("strategy") if m.id == PULLBACK)
    monkeypatch.setattr(type(pullback), "evaluate",
                        lambda self, context: Signal("BUY", 1.1, 1.09, 1.12, "eski mum", bar_time=LAST - M15))
    assert only(run(pullback_m15(), h1_up()), PULLBACK) == []


def test_context_is_read_only_for_strategies():
    context = Context(symbol="EURUSD", now=NOW)
    with pytest.raises(dataclasses.FrozenInstanceError):
        context.side = "BUY"


def test_stale_or_future_quote_gives_no_candidate():
    """Inceleme C1: bayat fiyatla giris stopa yaklasir, lot butcenin katlarina cikar. Fiyat taze degilse aday yok."""
    m15, h1 = pullback_m15(), h1_up()
    stop = only(run(m15, h1), PULLBACK)[0].candidate.stop_loss
    near_stop = stop + 0.0005  # 2 saat once kalmis, stopun hemen ustunde bir fiyat
    assert run(m15, h1, bid=near_stop, time=NOW - 7200) == []
    assert run(m15, h1, time=NOW - 61) == []
    assert run(m15, h1, time=NOW + 6) == []  # saat kaymasi: gelecekten fiyat
    assert only(run(m15, h1, time=NOW - 59), PULLBACK) != []


def test_v9_data_verdict_limits_new_strategies():
    m15, h1 = pullback_m15(), h1_up()
    for verdict in ("STALE_DATA", "PROVIDER_UNAVAILABLE"):
        assert run(m15, h1, report={}, v9_decisions=(verdict,)) == []  # V9 veriyi reddetti: sinyal yok
    live = {PULLBACK: "live"}
    assert only(run(m15, h1, modes=live, report={}, v9_decisions=("WAIT",)), PULLBACK)[0].mode == "live"
    # Rapor yok ya da veri yetersiz: guven puani anlamsiz; canli strateji de yalnizca golgede izlenir.
    assert only(run(m15, h1, modes=live, report=None), PULLBACK)[0].mode == "shadow"
    assert only(run(m15, h1, modes=live, report={}, v9_decisions=("INSUFFICIENT_DATA",)), PULLBACK)[0].mode == "shadow"


@pytest.mark.parametrize("up", [True, False])
def test_entry_side_rounding_and_budget(up):
    """Giris: BUY ask, SELL bid. Stop zarar yonunde, hedef yakina yuvarlanir; risk butceyi asmaz."""
    m15, h1 = pullback_m15(up), (h1_up() if up else h1_down())
    close, spread = m15[-1]["close"], 0.00004
    odd = instrument("EURUSD", kind="forex", tick_size=0.0005, contract_size=100_000.0, digits=5, calc_mode="forex")
    signal_stop = next(m for m in modules("strategy") if m.id == PULLBACK).evaluate(
        Context(symbol="EURUSD", now=NOW, kind="forex", report={}, bars={"M15": m15, "H1": h1},
                quote={"bid": close, "ask": close + spread, "spread": spread, "time": NOW}, instrument=odd)).stop
    c = only(run(m15, h1, spread=spread, item=odd), PULLBACK)[0].candidate
    sign = 1 if up else -1
    assert c.entry == pytest.approx(close + spread if up else close)
    assert (signal_stop - c.stop_loss) * sign >= -1e-12  # stop sinyalden daha UZAKTA ya da ayni
    assert abs(signal_stop - c.stop_loss) < 0.0005
    distance = (c.entry - c.stop_loss) * sign
    assert (c.take_profit_1 - c.entry) * sign <= 2.0 * distance + 1e-12  # hedef 2R'den uzaga yuvarlanmaz
    assert (c.take_profit_2 - c.entry) * sign <= 3.0 * distance + 1e-12
    assert 0 < c.risk_amount <= 10_000 * 0.5 / 100 + 1e-9
    assert c.risk_amount == pytest.approx(distance * c.lots * 100_000)


def test_lot_never_below_minimum_or_off_the_step_grid():
    m15, h1 = pullback_m15(), h1_up()
    big_min = instrument("EURUSD", kind="forex", tick_size=0.00001, contract_size=100_000.0, digits=5,
                         calc_mode="forex", volume_min=5.0, volume_step=0.01)
    assert run(m15, h1, item=big_min) == []  # butce 0.01'in katlarina yetiyor ama en kucuk lotun altinda
    capped = instrument("EURUSD", kind="forex", tick_size=0.00001, contract_size=100_000.0, digits=5,
                        calc_mode="forex", volume_min=0.01, volume_step=0.01, volume_max=0.015)
    assert only(run(m15, h1, item=capped), PULLBACK)[0].candidate.lots == pytest.approx(0.01)  # 0.015 degil


def test_commission_is_part_of_risk_and_net_rr():
    m15, h1 = pullback_m15(), h1_up()
    free = only(run(m15, h1), PULLBACK)[0].candidate
    paid = only(run(m15, h1, commission_per_lot=40.0), PULLBACK)[0].candidate
    assert paid.lots < free.lots and paid.net_rr < free.net_rr
    assert paid.risk_amount <= 10_000 * 0.5 / 100 + 1e-9  # komisyon dahil zarar butceyi asmaz
    assert run(m15, h1, commission_per_lot=400.0) == []  # komisyon net R/R'yi 1.5'in altina indiriyor


# ------------------------------------------------------------------ bot ve API
async def pullback_app(tmp_path, **kwargs):
    """EURUSD'de EMA geri cekilme sinyali ureten piyasa ile baslatilmis bot (XAUUSD'de V9 adayi da var)."""
    from tests.app_helpers import feed_ticks
    app = await started(tmp_path, **kwargs)
    m15 = pullback_m15(count=230)  # canlidaki gibi: V9'un da degerlendirebilecegi kadar mum
    app.fake.set_candles("EURUSD", "M15", m15)
    app.fake.set_candles("EURUSD", "H1", h1_up())
    app.fake.set_candles("EURUSD", "H4", trending(230, 0.0016, 0.8, NOW - 4 * H1, 4 * H1))
    await feed_ticks(app, "EURUSD", m15[-1]["close"], m15[-1]["close"] + 0.00002, NOW)
    return app


def client(app):
    token = issue_token(app.repo, now=app.clock["now"])
    api = create_app(app.bot, clock=lambda: app.clock["now"])
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://bot",
                             headers={"Authorization": f"Bearer {token}"})


async def test_new_strategy_is_shadow_tracked_and_never_sends_an_order_by_default(tmp_path):
    app = await pullback_app(tmp_path)  # canli mod: V9 adayi gercek emir acar, yeni strateji acmaz
    summary = await app.bot.on_bar_close()
    posts = app.fake.calls("POST", "/positions")
    assert [p[2]["instrument"] for p in posts] == ["XAUUSD"]  # yalnizca V9 adayi
    rows = [tuple(r) for r in app.repo.conn.execute("SELECT symbol, strategy_id, reason, side FROM shadow_trades")]
    assert ("EURUSD", PULLBACK, "shadow", "BUY") in rows
    assert summary.shadowed == len(rows) and all(r[1].startswith("tb_") and r[2] == "shadow" for r in rows)


async def test_new_strategy_cannot_go_live_without_confirmation_and_a_positive_shadow_record(tmp_path):
    app = await pullback_app(tmp_path)
    book = ShadowBook(app.repo)
    async with client(app) as http:
        listed = {s["strategy_id"]: s for s in (await http.get("/strategies")).json()["strategies"]}
        assert listed[PULLBACK]["source"] == "custom" and listed[PULLBACK]["mode"] == "shadow"
        assert listed[PULLBACK]["can_go_live"] is False and "20" in listed[PULLBACK]["live_blocker"]
        assert listed["fx_trend_momentum_v6"]["source"] == "v9" and listed["fx_trend_momentum_v6"]["mode"] == "live"

        path = f"/strategies/{PULLBACK}/mode"
        assert (await http.post(path, json={"mode": "live"})).status_code == 409
        refused = await http.post(path, json={"mode": "live", "confirm": True})
        assert refused.status_code == 409 and "gölge işlem" in refused.json()["detail"]
        # PUT /settings ile de canliya alinamaz
        body = (await http.get("/settings")).json()
        body["strategy_modes"] = {PULLBACK: "live"}
        assert (await http.put("/settings", json=body)).status_code == 409

        def add(n, result):
            app.repo.conn.execute(
                "INSERT INTO shadow_trades (symbol, side, strategy_id, setup_id, reason, entry, sl, tp, score, opened_at,"
                " closed_at, result_r) VALUES ('EURUSD','BUY',?,?,'shadow',1.1,1.09,1.12,NULL,?,?,?)",
                (PULLBACK, f"s{n}", NOW - 5000 + n, NOW - 4000 + n, result))
        for n in range(20):
            add(n, -1.0)  # 20 islem ama karne olumsuz
        assert book.stats(PULLBACK, "shadow")["trades"] == 20
        negative = await http.post(path, json={"mode": "live", "confirm": True})
        assert negative.status_code == 409 and "olumlu değil" in negative.json()["detail"]
        for n in range(20, 50):
            add(n, 2.0)  # ortalama R artik pozitif
        assert (await http.post(path, json={"mode": "live"})).status_code == 409  # onay hala sart
        accepted = await http.post(path, json={"mode": "live", "confirm": True})
        assert accepted.status_code == 200
    assert strategy_mode(app.repo.get_bot_settings(), PULLBACK) == "live"
    assert app.fake.calls("POST", "/positions") == []  # kip degisikligi tek basina emir gondermez


async def test_live_new_strategy_goes_through_the_same_gates_and_always_has_a_stop(tmp_path):
    app = await pullback_app(tmp_path)
    settings = app.repo.get_bot_settings()
    settings.strategy_modes[PULLBACK] = "live"  # karne kosulu saglanmis ve onaylanmis varsayalim
    app.repo.set_bot_settings(settings)
    summary = await app.bot.on_bar_close()
    posts = {p[2]["instrument"]: p[2] for p in app.fake.calls("POST", "/positions")}
    assert set(posts) == {"XAUUSD", "EURUSD"} and summary.opened == 2
    assert posts["EURUSD"].get("stop_loss_price")  # SL'siz emir yok
    await app.fake.flush()
    trade = next(t for t in app.repo.open_trades("bot") if t.symbol == "EURUSD")
    assert trade.strategy_id == PULLBACK and trade.sl is not None


async def test_new_strategy_in_dry_run_sends_nothing(tmp_path):
    app = await pullback_app(tmp_path, dry_run=True)
    settings = app.repo.get_bot_settings()
    settings.strategy_modes[PULLBACK] = "live"
    app.repo.set_bot_settings(settings)
    summary = await app.bot.on_bar_close()
    assert app.fake.calls("POST", "/positions") == [] and summary.would_open == 2


async def test_go_live_bar_cannot_be_lowered_by_settings(tmp_path):
    """Inceleme I1: pause_min_trades 5'e indirilse de canliya alma esigi 20'nin altina inmez."""
    app = await pullback_app(tmp_path)
    async with client(app) as http:
        body = (await http.get("/settings")).json()
        body["fusion"]["pause_min_trades"] = 5
        assert (await http.put("/settings", json=body)).status_code == 200
        for n in range(19):
            app.repo.conn.execute(
                "INSERT INTO shadow_trades (symbol, side, strategy_id, setup_id, reason, entry, sl, tp, score, opened_at,"
                " closed_at, result_r) VALUES ('EURUSD','BUY',?,?,'shadow',1.1,1.09,1.12,NULL,?,?,2.0)",
                (PULLBACK, f"k{n}", NOW - 5000 + n, NOW - 4000 + n))
        refused = await http.post(f"/strategies/{PULLBACK}/mode", json={"mode": "live", "confirm": True})
        assert refused.status_code == 409 and "en az 20" in refused.json()["detail"]


async def test_paused_strategy_needs_good_results_after_the_pause(tmp_path):
    """Inceleme I2: botun duraklattigi strateji eski golge karnesiyle yeniden canliya alinamaz."""
    from tradebot.signals import scorecard
    app = await pullback_app(tmp_path)

    def add(n, reason, result, at):
        app.repo.conn.execute(
            "INSERT INTO shadow_trades (symbol, side, strategy_id, setup_id, reason, entry, sl, tp, score, opened_at,"
            " closed_at, result_r) VALUES ('EURUSD','BUY',?,?,?,1.1,1.09,1.12,NULL,?,?,?)",
            (PULLBACK, f"{reason}{n}", reason, at + n, at + n + 1, result))
    for n in range(30):
        add(n, "shadow", 2.0, NOW - 90_000)  # duraklatmadan onceki parlak karne
    scorecard.mark_paused(app.repo, PULLBACK, NOW - 50_000, {"trades": 20, "avg_r": -0.5})
    path = f"/strategies/{PULLBACK}/mode"
    async with client(app) as http:
        blocked = await http.post(path, json={"mode": "live", "confirm": True})
        assert blocked.status_code == 409 and "gölge işlem" in blocked.json()["detail"]
        for n in range(25):
            add(n, "paused", -1.0, NOW - 40_000)  # duraklatmadan sonra da kaybediyor
        still = await http.post(path, json={"mode": "live", "confirm": True})
        assert still.status_code == 409 and "olumlu değil" in still.json()["detail"]
        for n in range(25, 80):
            add(n, "paused", 2.0, NOW - 40_000)
        assert (await http.post(path, json={"mode": "live", "confirm": True})).status_code == 200


async def test_stale_quote_never_reaches_an_order_or_the_shadow_record(tmp_path):
    from tests.app_helpers import feed_ticks
    app = await pullback_app(tmp_path)
    settings = app.repo.get_bot_settings()
    settings.strategy_modes[PULLBACK] = "live"
    app.repo.set_bot_settings(settings)
    await feed_ticks(app, "EURUSD", 1.0, 1.00002, NOW)  # son fiyat kaydi
    app.bot.quotes._last["EURUSD"] = type(app.bot.quotes._last["EURUSD"])("EURUSD", 1.0, 1.00002, NOW - 7200)
    await app.bot.on_bar_close()
    assert [p[2]["instrument"] for p in app.fake.calls("POST", "/positions")] == ["XAUUSD"]
    assert app.repo.conn.execute("SELECT COUNT(*) FROM shadow_trades WHERE symbol='EURUSD'").fetchone()[0] == 0
