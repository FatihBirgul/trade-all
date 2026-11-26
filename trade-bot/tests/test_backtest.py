"""Ileri test: gecmis mumlarin yeniden oynatilmasi ve botun bu isi nasil calistirdigi."""
import asyncio
import json

from tests.app_helpers import started
from tests.test_scan_summary import public_get
from tradebot import app as app_module
from tradebot import backtest, forward
from tradebot.exness.schema import Account, Instrument
from tradebot.signals.adapter import Candidate

RULES = {"be_at_r": 1.0, "partial_at_r": 2.0, "partial_fraction": 0.5, "trail_atr_mult": 1.0}
ACCOUNT = Account(currency="USC", balance=1.0, equity=1.0, margin=0.0, margin_free=1.0, leverage=None,
                  can_open=True, can_trade=True)


def instrument(symbol="EURUSD"):
    return Instrument(symbol=symbol, broker_symbol=symbol + "c", kind="forex", tick_size=0.00001, contract_size=1000,
                      volume_min=0.01, volume_max=10, volume_step=0.01, stops_level=0, digits=5, currency_base="EUR",
                      currency_profit="USD", currency_margin="EUR", calc_mode="forex", exec_mode="market",
                      trading_hours=None, tradable=True)


def flat_history(moves, symbol="EURUSD"):
    """40 duz mum, ardindan (low, high, close) hareketleri; fiyat 1.1000 cevresinde."""
    bars = [{"time": i * 900, "open": 1.1, "high": 1.1002, "low": 1.0998, "close": 1.1} for i in range(40)]
    bars += [{"time": (40 + i) * 900, "open": 1.1, "low": low, "high": high, "close": close}
             for i, (low, high, close) in enumerate(moves)]
    history = backtest.History()
    history.add(symbol, "M15", bars)
    return history


def signal_at(times, side="BUY"):
    """Verilen mum kapanislarinda (acilis sirasi) aday ureten sahte degerlendirici."""
    def evaluate(provider, symbol, now):
        quote = provider.quote(symbol)
        if int((now - 5) // 900) - 1 not in times or quote is None:
            return []
        entry = quote["ask"] if side == "BUY" else quote["bid"]
        sign = 1 if side == "BUY" else -1
        return [Candidate(symbol=symbol, side=side, entry=entry, stop_loss=entry - sign * 0.0010,
                          take_profit_1=entry + sign * 0.0020, take_profit_2=entry + sign * 0.0030, lots=0.01,
                          strategy_id="s", setup_id=f"{symbol}-{now}", net_rr=2.0, analysis_id="a",
                          risk_amount=1.0)]
    return evaluate


def run(history, evaluate, spread=0.0002, **kwargs):
    result = backtest.replay([instrument()], history, {"EURUSD": spread}, ACCOUNT, rules=RULES, start=0.0,
                             end=10**9, evaluate=evaluate, **kwargs)
    return result, backtest.summarize(result, start=0.0, end=10**9)


def test_buy_pays_the_spread_in_distance_and_a_stop_is_minus_one_r():
    # 40. mumun kapanisinda BUY: giris ask = 1.1002, stop 1.0992 (bid'e gore yalnizca 8 pip uzakta).
    result, summary = run(flat_history([(1.0999, 1.1001, 1.1), (1.0991, 1.1001, 1.0995)]), signal_at({40}))
    trade = result["trades"][0]
    assert (trade["r"], trade["first"], trade["spread_r"]) == (-1.0, "SL", 0.2)
    assert trade["gross_r"] is None or trade["gross_r"] > -1.0  # spread'siz olsaydi stop olmazdi (9 pip dusus)
    assert summary["total"]["losses"] == 1 and summary["total"]["sum_r"] == -1.0


def test_sell_is_closed_at_the_ask():
    # SELL bid'den acilir (1.1000), stop 1.1010. Bid en cok 1.1009'a cikti; ask = 1.1011 stopa degdi.
    result, _ = run(flat_history([(1.0999, 1.1001, 1.1), (1.0999, 1.1009, 1.1005)]), signal_at({40}, "SELL"))
    assert result["trades"][0]["r"] == -1.0
    result, _ = run(flat_history([(1.0999, 1.1001, 1.1), (1.0999, 1.1009, 1.1005)]), signal_at({40}, "SELL"),
                    spread=0.0)
    assert result["trades"][0]["r"] is None  # spread yoksa stop olmazdi


def test_no_second_trade_while_one_is_open_and_reentry_after_a_stop_is_marked():
    moves = [(1.0999, 1.1001, 1.1)] * 3 + [(1.0985, 1.1001, 1.1)] + [(1.0999, 1.1001, 1.1)] * 3
    result, summary = run(flat_history(moves), signal_at({40, 41, 44}))
    assert [t["at"] for t in result["trades"]] == [41 * 900 + 5.0, 45 * 900 + 5.0]
    assert result["coverage"]["skipped_open"] == 1  # 41. mumdaki sinyal: ilk islem hala acik
    assert [t["reentry"] for t in result["trades"]] == [False, True]
    assert summary["reentry"]["after_stop"]["trades"] == 1


def test_budget_stops_the_replay_and_says_so():
    ticks = iter(range(0, 10_000, 10))
    result, summary = run(flat_history([(1.0999, 1.1001, 1.1)] * 20), signal_at(set()), budget=35.0,
                          timer=lambda: next(ticks))
    assert result["coverage"]["out_of_budget"] is True and result["coverage"]["symbols"] == []
    assert summary["total"]["trades"] == 0 and summary["total"]["avg_r"] is None


def test_history_file_round_trip(tmp_path):
    path = tmp_path / "h.db"
    backtest.write_history(path, [("EURUSD", "M15", 900, 1.0, 1.2, 0.9, 1.1), ("EURUSD", "M15", 0, 1.0, 1.1, 0.9, 1.0)])
    history = backtest.read_history(path)
    assert [b["time"] for b in history.closed("EURUSD", "M15", 1800, 10)] == [0, 900]
    assert history.closed("EURUSD", "M15", 1799, 10)[-1]["time"] == 0  # kapanmamis mum verilmez


class InlinePool:
    """Alt surec havuzu yerine ayni surecte calisan sahte havuz (testlerde surec baslatilmaz)."""

    def __init__(self, count):
        self.count = count

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def imap_unordered(self, function, items):
        return (function(item) for item in items)


def short_job(monkeypatch, app):
    """~1 gunluk pencere: gercek V9 motoru ve swing stratejileri, kisa sure."""
    monkeypatch.setattr(app_module, "BACKTEST_DAYS", 1)
    monkeypatch.setattr(app_module, "BACKTEST_V9_DAYS", 0.05)
    monkeypatch.setattr(app_module, "BACKTEST_FETCH_PAUSE", 0.0)
    jobs = []

    async def in_process(job):
        jobs.append(json.loads(job.read_text()))
        import sqlite3
        db = sqlite3.connect(jobs[-1]["history"])
        try:  # gecmis dosyasinda olusmakta olan mum bulunmaz
            for tf, at in db.execute("SELECT tf, time FROM bars"):
                assert at + forward.DURATIONS[tf] <= jobs[-1]["end"], (tf, at)
        finally:
            db.close()
        await asyncio.to_thread(forward.run_job, job, InlinePool)
        return 0

    monkeypatch.setattr(app.bot, "_backtest_spawn", in_process)
    return jobs


async def test_bot_runs_the_forward_test_once_in_dry_run_and_publishes_only_numbers(tmp_path, monkeypatch):
    app = await started(tmp_path, dry_run=True)
    await app.bot.record_spreads()  # olculmus saatlik spread profili
    jobs = short_job(monkeypatch, app)
    assert (await public_get(app, "/health/backtest")).json() == {"state": "idle", "result": None}
    summary = await app.bot.backtest_once()
    assert summary["version"] == forward.VERSION and summary["symbols"] == 1
    assert summary["v9_coverage"] == {"symbols_done": 1, "symbols_total": 1, "workers": 1,
                                      "evaluations": summary["v9_coverage"]["evaluations"], "errors": 0,
                                      "complete": True}
    assert summary["v9_coverage"]["evaluations"] >= 4
    assert set(summary["swing"]["strategies"]) == set(forward.SWING_IDS)
    assert summary["spread_profile"] == {"symbols": 1, "hours_measured_median": 1}
    job = jobs[0]
    assert job["account"]["equity"] == 10_000.0  # gercek varlik dosyaya yazilmaz (sahte hesap da 10000)
    assert job["end"] % 86400 == 0 and job["split"] == job["start"] + (job["end"] - job["start"]) * 2 / 3
    assert list(job["bounds"]) == ["XAUUSD"] and {row[0] for row in [("D1",)]} <= set(forward.DURATIONS)
    folder = tmp_path / "backtest"
    assert not (folder / "history.db").exists() and not (folder / "job.json").exists()  # is bitince silinir
    assert (folder / "v9-XAUUSD.json").exists()  # biten sembol saklanir: yarim kalan is kaldigi yerden surer
    response = await public_get(app, "/health/backtest")
    assert response.json()["state"] == "done" and response.json()["result"]["v9"] == summary["v9"]
    for secret in ("123456", "balance", "equity", "lots", "risk_amount"):
        assert secret not in response.text
    assert await app.bot.backtest_once() is None  # tam ve taze sonuc varken yeniden calismaz


async def test_unfinished_v9_phase_is_resumed_without_redoing_finished_symbols(tmp_path, monkeypatch):
    app = await started(tmp_path, dry_run=True)
    short_job(monkeypatch, app)
    monkeypatch.setattr(app_module, "BACKTEST_BUDGET", -1.0)  # sure hemen doluyor: V9 hic bitmez
    first = await app.bot.backtest_once()
    assert first["v9_coverage"]["complete"] is False and app.bot.backtest_state == "partial"
    assert not (tmp_path / "backtest" / "v9-XAUUSD.json").exists()
    monkeypatch.setattr(app_module, "BACKTEST_BUDGET", 3600.0)
    second = await app.bot.backtest_once()  # tamamlanmamis sonuc "taze" sayilmaz: is yeniden calisir
    assert second["v9_coverage"]["complete"] is True and app.bot.backtest_state == "done"
    # Biten sembolun dosyasi durdukca V9 o sembolde yeniden calistirilmaz.
    job = tmp_path / "backtest" / "job.json"
    saved = json.loads((tmp_path / "backtest" / "v9-XAUUSD.json").read_text())
    signature = saved["signature"].split(":")
    history = tmp_path / "backtest" / "h.db"
    backtest.write_history(history, [("XAUUSD", "M15", 0, 1.0, 1.0, 1.0, 1.0)])
    job.write_text(json.dumps({"instruments": [{"symbol": "XAUUSD", "kind": "metal"}], "spreads": {"XAUUSD": {"hours": {}, "all": 0.2}},
                               "start": float(signature[1]), "end": float(signature[2]), "split": float(signature[1]),
                               "v9_start": float(signature[1]), "history": str(history),
                               "result": str(tmp_path / "backtest" / "again.json"), "workers": 1}))
    monkeypatch.setattr(forward, "v9_symbol", lambda args: (_ for _ in ()).throw(AssertionError("yeniden calisti")))
    again = forward.run_job(job, InlinePool)
    assert again["v9_coverage"]["complete"] is True and again["v9"] == second["v9"]


async def test_backtest_never_runs_live_and_a_failure_is_harmless(tmp_path, monkeypatch):
    live = await started(tmp_path / "live")
    assert await live.bot.backtest_once() is None and live.bot.backtest_state == "idle"
    app = await started(tmp_path / "dry", dry_run=True)
    short_job(monkeypatch, app)

    async def crash(job):
        return 1

    monkeypatch.setattr(app.bot, "_backtest_spawn", crash)
    assert await app.bot.backtest_once() is None
    assert app.bot.backtest_state == "failed: RuntimeError"
    assert (await app.bot.on_bar_close()).would_open == 1  # bot etkilenmez


# ---------------------------------------------------------------- forward.py birimleri
def trade(at, r, closed_after=3600.0, strategy="tb_smc_sweep_v1", side="BUY"):
    results = {str(t): [r, None if r is None else at + closed_after, None] for t in forward.TARGETS}
    return {"strategy_id": strategy, "symbol": "EURUSD", "side": side, "at": at, "results": results,
            "spread_r": 0.01, "stop_daily_atr": 1.5}


def test_hourly_spread_falls_back_to_the_symbol_median():
    spreads = forward.Spreads({"EURUSD": {"hours": {"3": 0.0004}, "all": 0.0001}})
    assert spreads.at("EURUSD", 3 * 3600 + 5) == 0.0004 and spreads.at("EURUSD", 14 * 3600) == 0.0001
    assert spreads.has("EURUSD") and not spreads.has("GBPUSD")
    assert spreads.coverage() == {"symbols": 1, "hours_measured_median": 1}


def test_portfolio_rules_cap_five_entries_a_day_and_stop_after_three_straight_losses():
    day = 10 * 86400.0
    six = [trade(day + i * 600, 1.0, closed_after=100_000.0) for i in range(6)]
    assert len(forward.apply_rules(six, "2.0")) == 5  # gunde en cok 5 giris
    losses = [trade(day + i * 7200, -1.0) for i in range(3)] + [trade(day + 30_000, 1.0), trade(day + 86400 + 60, 1.0)]
    kept = forward.apply_rules(losses, "2.0")
    assert [t["at"] for t in kept] == [day, day + 7200, day + 14400, day + 86400 + 60]  # ayni gun 4. giris yok
    # Kayiplar henuz KAPANMADIYSA (sonuc bilinmiyorsa) giris engellenmez: gelecegi goren kural olmaz.
    pending = [trade(day + i * 600, -1.0, closed_after=50_000.0) for i in range(4)]
    assert len(forward.apply_rules(pending, "2.0")) == 4


def test_selection_uses_only_the_first_period_and_reports_the_second():
    split = 100 * 86400.0
    rows = []
    for i in range(20):  # ic orneklem: dar bant iyi, genis bant kotu
        rows.append(trade(i * 86400.0, 1.0, strategy="tb_emapb_h1_20_21_v1"))
        rows.append(trade(i * 86400.0 + 5, -1.0, strategy="tb_emapb_h1_21_50_v1"))
    for i in range(10):  # dis orneklem: tam tersi
        rows.append(trade(split + i * 86400.0, -1.0, strategy="tb_emapb_h1_20_21_v1"))
        rows.append(trade(split + i * 86400.0 + 5, 1.0, strategy="tb_emapb_h1_21_50_v1"))
    summary = forward.summarize_swing(rows, split)
    chosen = summary["selected"]["ema_pullback"]
    assert chosen["strategy_id"] == "tb_emapb_h1_20_21_v1"  # secim ic orneklemle yapilir
    assert chosen["is"]["avg_r"] == 1.0 and chosen["oos"]["avg_r"] == -1.0  # dis orneklem oldugu gibi raporlanir
    assert summary["selected"]["smc"] is None  # yeterli islem yoksa secim yapilmaz
    assert summary["strategies"]["tb_emapb_h1_21_50_v1"]["targets"]["2.0"]["raw"]["oos"]["sum_r"] == 10.0


def test_swing_replay_finds_the_smc_trade_and_never_looks_ahead(tmp_path):
    from tests.signals.test_swing_strategies import D1, END, H4, bar, rising, smc_h1, smc_m15
    history = backtest.History()
    m15 = [bar(END - (400 - i) * 900, 100.4, 100.45, 100.35, 100.4) for i in range(397)] + smc_m15()
    future = [bar(END + i * 900, 100.5, 100.6 + i * 0.2, 100.45, 100.55 + i * 0.2) for i in range(40)]  # yukselis
    history.add("EURUSD", "M15", m15 + future)
    history.add("EURUSD", "H1", smc_h1() + [bar(END + i * 3600, 101, 101.5, 100.9, 101.2) for i in range(10)])
    history.add("EURUSD", "H4", rising(80, 0.05, 100.5, H4, END))
    history.add("EURUSD", "D1", rising(80, 0.26, 100.5, D1, END, spread=1.0))
    spreads = forward.Spreads({"EURUSD": {"hours": {}, "all": 0.02}})
    trades = forward.swing_trades("EURUSD", "forex", history, spreads, END - 3600, END + 3600)
    smc = [t for t in trades if t["strategy_id"] == "tb_smc_sweep_v1"]
    assert len(smc) == 1 and smc[0]["side"] == "BUY" and smc[0]["at"] == END + 5
    assert smc[0]["stop_daily_atr"] >= 1.5 and 0 < smc[0]["spread_r"] < 0.05
    assert smc[0]["results"]["1.5"][0] is not None or smc[0]["results"]["1.5"][2] is not None
    # Ayni veri, gelecek mumlar OLMADAN: sinyal ayni anda ve ayni yonde (gelecege bakilmiyor).
    past = backtest.History()
    past.add("EURUSD", "M15", m15)
    for tf in ("H1", "H4", "D1"):
        past.add("EURUSD", tf, [b for b in history.all("EURUSD", tf) if b["time"] + forward.DURATIONS[tf] <= END])
    alone = [t for t in forward.swing_trades("EURUSD", "forex", past, spreads, END - 3600, END + 3600)
             if t["strategy_id"] == "tb_smc_sweep_v1"]
    assert len(alone) == 1 and (alone[0]["at"], alone[0]["side"]) == (smc[0]["at"], smc[0]["side"])


def test_stop_day_stays_closed_and_selected_strategies_share_one_portfolio():
    day = 10 * 86400.0
    # Uc kayip kapandi, ardindan eski bir islem kazancla kapandi: gun yine kapali kalir.
    rows = [trade(day, 1.0, closed_after=40_000.0)] + [trade(day + 600 + i * 7200, -1.0) for i in range(3)]
    rows += [trade(day + 50_000, 1.0), trade(day + 86400 + 60, 1.0)]
    assert [t["at"] for t in forward.apply_rules(rows, "2.0")][-2:] == [day + 600 + 2 * 7200, day + 86400 + 60]
    # Hesap geneli: iki stratejinin islemleri AYNI gunluk siniri paylasir.
    mixed = [trade(day + i * 600, 1.0, closed_after=100_000.0,
                   strategy=("tb_smc_sweep_v1", "tb_emapb_h1_20_21_v1")[i % 2]) for i in range(8)]
    targets = {"tb_smc_sweep_v1": "2.0", "tb_emapb_h1_20_21_v1": "1.5"}
    assert len(forward.apply_rules(mixed, targets)) == 5


def test_in_sample_ends_at_the_split_and_open_trades_are_reported_apart():
    split = 100 * 86400.0
    rows = [trade(split - 86400.0, 1.0), trade(split - 600.0, 3.0, closed_after=7200.0),  # ikincisi ayrimi asiyor
            trade(split + 600.0, -1.0), trade(split + 900.0, None)]
    rows[-1]["results"] = {key: [None, None, 0.4] for key in rows[-1]["results"]}
    periods = forward._swing_periods(rows, split, "2.0")
    assert periods["is"]["trades"] == 1 and periods["is"]["sum_r"] == 1.0 and periods["straddle"] == 1
    assert periods["oos"] == {"trades": 2, "open": 1, "wins": 0, "flat": 0, "losses": 1, "sum_r": -1.0,
                              "avg_r": -1.0, "open_r": 0.4, "pf": 0.0, "max_dd": -1.0}  # acik islem 0 sayilmaz
    summary = forward.summarize_swing(rows, split)
    assert summary["portfolio"] is None  # secim yoksa portfoy satiri da yok
    spreads = forward.Spreads({"EURUSD": {"hours": {3: 0.0004}, "all": 0.0001}})
    assert spreads.at("EURUSD", 3 * 3600.0) == 0.0004  # saat anahtari sayi da olsa bulunur


def test_wide_stop_never_comes_closer_than_one_and_a_half_daily_atr():
    assert forward.wide_distance(0.2, 1.0) == 1.5 and forward.wide_distance(2.0, 1.0) == 2.0


def test_replay_shows_strategies_only_closed_and_current_bars_and_simulates_from_the_next_bar(monkeypatch):
    from tests.signals.test_swing_strategies import D1, END, H4, bar, rising, smc_h1, smc_m15
    history = backtest.History()
    m15 = [bar(END - (400 - i) * 900, 100.4, 100.45, 100.35, 100.4) for i in range(397)] + smc_m15()
    future = [bar(END + i * 900, 100.5, 100.6 + i * 0.2, 100.45, 100.55 + i * 0.2) for i in range(40)]
    history.add("EURUSD", "M15", m15 + future)
    history.add("EURUSD", "H1", smc_h1() + [bar(END + i * 3600, 101, 101.5, 100.9, 101.2) for i in range(10)])
    history.add("EURUSD", "H4", rising(80, 0.05, 100.5, H4, END) + [bar(END, 101, 109, 100.9, 108)])
    history.add("EURUSD", "D1", rising(80, 0.26, 100.5, D1, END, spread=1.0) + [bar(END, 101, 109, 100.9, 108)])
    seen, simulated = [], []
    real_modules, real_simulate = forward.modules, forward.outcome.simulate_swing

    class Spy:
        def __init__(self, inner):
            self.inner, self.id = inner, inner.id

        def evaluate(self, context):
            seen.append(context)
            return self.inner.evaluate(context)

    def simulate(side, entry, stop, target, at, bars, **kwargs):
        simulated.append((side, entry, at, bars[0]["time"] if bars else None))
        return real_simulate(side, entry, stop, target, at, bars, **kwargs)

    monkeypatch.setattr(forward, "modules", lambda kind: [Spy(m) for m in real_modules(kind)])
    monkeypatch.setattr(forward.outcome, "simulate_swing", simulate)
    spreads = forward.Spreads({"EURUSD": {"hours": {}, "all": 0.02}})
    trades = forward.swing_trades("EURUSD", "forex", history, spreads, END - 6 * 3600, END + 3 * 3600)
    assert trades and len(seen) > 30
    for context in seen:
        for tf, duration in forward.DURATIONS.items():
            bars = context.bars[tf]
            assert bars and bars[-1]["time"] + duration <= context.now  # olusmakta olan mum yok
        assert context.bars["H1"][-1]["time"] + 2 * 3600 > context.now  # ve en yeni kapanmis H1 mumu (bayat degil)
    assert all(first == at - 5 for _, _, at, first in simulated)  # benzetim giris mumundan SONRAKI mumla baslar
    side, entry = next((side, entry) for side, entry, at, _ in simulated if at == END + 5)
    assert side == "BUY" and entry == 100.5 + 0.02  # AL: kapanis + spread (ask)


async def test_unfinished_job_keeps_its_window_across_days(tmp_path, monkeypatch):
    app = await started(tmp_path, dry_run=True)
    jobs = short_job(monkeypatch, app)
    monkeypatch.setattr(app_module, "BACKTEST_BUDGET", -1.0)
    monkeypatch.setattr(app_module, "BACKTEST_ROUNDS", 2)
    assert (await app.bot.backtest_once())["v9_coverage"]["complete"] is False
    assert len(jobs) == 2  # bitmeyen is ayni gecmisle bir tur daha denenir
    app.clock["now"] += 86400.0  # ertesi gun yeniden baslayan surec ayni pencereyle surer
    monkeypatch.setattr(app_module, "BACKTEST_BUDGET", 3600.0)
    done = await app.bot.backtest_once()
    assert done["v9_coverage"]["complete"] is True and len(jobs) == 3 and jobs[2]["end"] == jobs[0]["end"]
    app.clock["now"] += 86400.0  # tamamlanan isten sonra (sonuc eskiyince) yeni pencere acilir
    await app.bot.backtest_once()
    assert jobs[3]["end"] == jobs[0]["end"] + 2 * 86400.0


async def test_history_never_stores_a_bar_that_is_still_forming(tmp_path, monkeypatch):
    app = await started(tmp_path, dry_run=True)
    short_job(monkeypatch, app)  # gecmis dosyasindaki her mumun pencere sonunda kapanmis oldugunu denetler
    real = app_module.schema.parse_candles
    forming = {"time": int(app.clock["now"] // 900) * 900, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
               "tick_volume": 1}
    monkeypatch.setattr(app_module.schema, "parse_candles", lambda payload: real(payload) + [dict(forming)])
    assert await app.bot.backtest_once() is not None and app.bot.backtest_state == "done"


# ---------------------------------------------------------------- eski masanin kodundan tasinan stratejiler
def generated(seed=1, days=240, cut=None):
    from tests.signals.market_gen import DURATIONS, market
    history = backtest.History()
    for tf, bars in market(seed, days).items():
        history.add("X", tf, [b for b in bars if cut is None or b["time"] + DURATIONS[tf] <= cut])
    return history


def test_replay_runs_the_ported_strategies_with_their_own_exit_plans_and_without_looking_ahead():
    from tests.signals.market_gen import T0
    spreads = forward.Spreads({"X": {"hours": {}, "all": 0.01}})
    start, end = T0 + 200 * 86400, T0 + 240 * 86400
    trades = [t for t in forward.swing_trades("X", "crypto", generated(), spreads, start, end)
              if t["strategy_id"] in forward.PLAN_IDS]
    assert {t["strategy_id"] for t in trades} == set(forward.PLAN_IDS)
    for trade_ in trades:
        assert list(trade_["results"]) == [forward.PLAN_KEY] and trade_["kind"] == "crypto"
        assert trade_["weekend"] == ((int(trade_["at"] // 86400) + 3) % 7 >= 5) and 0 < trade_["spread_r"] < 0.2
        day = trade_["strategy_id"] in ("tb_smc_day_v13", "tb_emapb_day_v13")
        assert (trade_["volume_ratio"] is not None) == trade_["strategy_id"].endswith("_v13")
        assert (trade_["stretch"] is not None) == (trade_["strategy_id"] == "tb_week_trade_v1")
        assert trade_["exit"] in ((None, "SL", "TP1", "TP", "TIME") if day else (None, "SL", "TRAIL", "TIME"))
    assert any(t["weekend"] for t in trades) and any(not t["weekend"] for t in trades)
    # Gelecek kesilince: her stratejinin kesim anina kadarki ILK sinyali ayni (sonrakiler acik islemden etkilenir).
    cut = T0 + 215 * 86400 + 5 * 3600
    early = [t for t in forward.swing_trades("X", "crypto", generated(cut=cut), spreads, start, end)
             if t["strategy_id"] in forward.PLAN_IDS]
    first = lambda rows: {name: next((t["at"], t["side"], t["model"]) for t in rows if t["strategy_id"] == name)  # noqa: E731
                          for name in {t["strategy_id"] for t in early}}
    assert len(early) >= 5 and first(early) == first([t for t in trades if t["at"] <= cut])


def test_h4_state_knows_a_swing_only_after_three_more_candles_have_closed():
    from tests.signals.test_v13 import bar
    highs = [10 + 0.01 * i for i in range(14)] + [15.0] + [9 - 0.01 * i for i in range(10)]  # tek tepe: indeks 14
    history = backtest.History()
    history.add("X", "H4", [bar(i * 14400, 8.5, h, 8.0, 8.6) for i, h in enumerate(highs)])
    state = forward.h4_state(history, "X")
    assert state(10 * 14400) is None  # ATR icin yeterli mum yok
    assert state(17 * 14400)["high"] is None  # tepeden sonra yalnizca 2 mum kapandi: henuz bilinmiyor
    late = state(18 * 14400)
    assert late["high"] == (18 * 14400, 15.0) and late["atr"] > 0  # ucuncu mum kapaninca bilinir
    assert forward.h4_state(backtest.History(), "X")(1e9) is None


def planned(at, r, strategy="tb_smc_day_v13", closed_after=3600.0, **extra):
    row = {"strategy_id": strategy, "symbol": "X", "side": "BUY", "at": at, "spread_r": 0.1, "stop_daily_atr": 0.5,
           "results": {forward.PLAN_KEY: [r, None if r is None else at + closed_after, None if r is not None else 0.3]},
           "kind": "forex", "model": "1 SMC OB+FVG", "score": 70, "volume_ratio": 1.0, "stretch": None,
           "weekend": False, "exit": "SL" if (r or 0) < 0 else "TP"}
    row.update(extra)
    return row


def test_planned_summary_reports_profit_factor_drawdown_cost_and_the_requested_splits():
    split = 100 * 86400.0
    rows = [planned(1 * 86400.0, 2.0), planned(2 * 86400.0, -1.0), planned(3 * 86400.0, -1.0, model="3 Sweep"),
            planned(4 * 86400.0, 1.0, volume_ratio=0.5), planned(split + 86400.0, -1.0, kind="crypto", weekend=True),
            planned(split + 2 * 86400.0, 3.0, kind="crypto"), planned(split + 3 * 86400.0, None, kind="crypto")]
    summary = forward.summarize_planned(rows, split)
    whole = summary["raw"]["all"]
    assert (whole["trades"], whole["open"], whole["wins"], whole["losses"]) == (7, 1, 3, 3)
    assert whole["sum_r"] == 3.0 and whole["pf"] == 2.0 and whole["max_dd"] == -2.0 and whole["open_r"] == 0.3
    assert summary["raw"]["is"]["sum_r"] == 1.0 and summary["raw"]["oos"]["sum_r"] == 2.0
    assert summary["spread_r_median"] == 0.1 and summary["exits"] == {"SL": 3, "TP": 4}
    assert set(summary["by_model"]) == {"1 SMC OB+FVG", "3 Sweep"} and summary["by_model"]["3 Sweep"]["all"]["sum_r"] == -1.0
    assert summary["by_kind"]["crypto"]["all"]["trades"] == 3
    assert summary["crypto_week"]["weekend"]["all"]["sum_r"] == -1.0 and summary["crypto_week"]["weekday"]["all"]["sum_r"] == 3.0
    assert summary["volume"]["low"]["all"]["sum_r"] == 1.0 and summary["volume"]["ok"]["all"]["trades"] == 6
    assert summary["stretch"] == {}  # yalnizca WEEK TRADE'de dolar
    assert forward.stats([1.0, 1.0])["pf"] is None  # kayip yoksa PF tanimsiz
    full = forward.summarize_swing(rows, split)
    assert set(full["planned"]) == set(forward.PLAN_IDS) and full["planned"]["tb_week_trade_v1"]["raw"]["all"]["trades"] == 0
    # Portfoy kurallari bu stratejilere de uygulanir (ayni gun art arda 3 kayiptan sonra giris yok).
    day = 50 * 86400.0
    streak = [planned(day + i * 7200, -1.0) for i in range(3)] + [planned(day + 30_000, 5.0)]
    assert forward.summarize_planned(streak, split)["rules"]["all"]["sum_r"] == -3.0
