"""Ileri test: gecmis mumlarin yeniden oynatilmasi ve botun bu isi nasil calistirdigi."""
import asyncio
import json
from pathlib import Path

import pytest

from tests.app_helpers import started
from tests.test_scan_summary import public_get
from tradebot import app as app_module
from tradebot import backtest, forward, yeartest
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

    def imap(self, function, items):
        return (function(item) for item in items)


def short_job(monkeypatch, app):
    """Kisa pencereler: gercek V9 motoru ve stratejiler, kisa sure. Alt surec yerine ayni surecte calisir."""
    monkeypatch.setattr(app_module, "BACKTEST_DAYS", 1)
    monkeypatch.setattr(app_module, "BACKTEST_V9_DAYS", 0.05)
    monkeypatch.setattr(app_module, "YEAR_DAYS", 0.1)
    monkeypatch.setattr(app_module, "YEAR_CHUNK_DAYS", 0.05)
    monkeypatch.setattr(app_module, "BACKTEST_FETCH_PAUSE", 0.0)
    jobs = []

    async def in_process(job, module="tradebot.forward"):
        jobs.append({**json.loads(job.read_text()), "module": module})
        import sqlite3
        db = sqlite3.connect(jobs[-1]["history"])
        try:  # gecmis dosyasinda olusmakta olan mum bulunmaz
            for tf, at in db.execute("SELECT tf, time FROM bars"):
                assert at + forward.DURATIONS[tf] <= jobs[-1]["end"], (tf, at)
        finally:
            db.close()
        runner = yeartest.run_job if module.endswith("yeartest") else forward.run_job
        await asyncio.to_thread(runner, job, InlinePool)
        return 0

    monkeypatch.setattr(app.bot, "_backtest_spawn", in_process)
    return jobs


async def test_bot_runs_forward_then_year_test_in_dry_run_and_publishes_only_numbers(tmp_path, monkeypatch):
    app = await started(tmp_path, dry_run=True)
    await app.bot.record_spreads()  # olculmus saatlik spread profili
    jobs = short_job(monkeypatch, app)
    assert (await public_get(app, "/health/backtest")).json() == {"state": "idle", "result": None}
    assert (await public_get(app, "/health/yeartest")).json() == {"state": "idle", "result": None}
    summary = await app.bot.backtest_once()
    assert summary["version"] == forward.VERSION and summary["symbols"] == 1
    assert set(summary["swing"]["strategies"]) == set(forward.SWING_IDS)
    assert [job["module"] for job in jobs] == ["tradebot.forward", "tradebot.yeartest"] and jobs[0]["skip_v9"] is True
    job = jobs[1]
    assert job["account"]["equity"] == 10_000.0  # gercek varlik dosyaya yazilmaz (sahte hesap da 10000)
    assert job["end"] % 86400 == 0 and job["year_start"] == job["end"] - 0.1 * 86400 and len(job["v9_ids"]) == 4
    year = app.bot.yeartest_report(full=True)["result"]
    assert year["version"] == yeartest.VERSION and year["complete"] is True and app.bot.backtest_state == "done"
    assert set(year["strategies"]) == set(yeartest.TB_IDS) | set(job["v9_ids"])  # 14 strateji
    assert year["progress"]["v9_chunks_done"] == year["progress"]["v9_chunks_total"] == 2
    assert year["progress"]["v9_evaluations"] >= 8 and year["rules"]["swap"] == 0
    for row in year["strategies"].values():
        assert set(row["windows"]) == {"1m", "6m", "1y"} and "curve" in row["windows"]["1y"]
        assert row["verdict"]["passed"] in (None, False)  # bu kadar kisa veriyle hicbir strateji "gecti" olamaz
    folder = tmp_path / "backtest"
    assert not (folder / "history.db").exists() and not (folder / "job.json").exists()  # is bitince silinir
    public = await public_get(app, "/health/yeartest")
    assert public.json()["state"] == "done" and "by_symbol" not in public.text and "curve" not in public.text
    assert public.json()["result"]["strategies"].keys() == year["strategies"].keys()
    for secret in ("123456", "\"balance\"", "equity", "lots", "risk_amount"):
        assert secret not in public.text and secret not in (await public_get(app, "/health/backtest")).text
    assert await app.bot.backtest_once() is None  # tam ve taze sonuc varken yeniden calismaz


async def test_unfinished_year_test_resumes_with_the_same_window_history_and_finished_parts(tmp_path, monkeypatch):
    app = await started(tmp_path, dry_run=True)
    jobs = short_job(monkeypatch, app)
    fetches = []
    real = app.bot._backtest_history

    async def counted(*args, **kwargs):
        fetches.append(1)
        return await real(*args, **kwargs)

    monkeypatch.setattr(app.bot, "_backtest_history", counted)
    monkeypatch.setattr(app_module, "BACKTEST_BUDGET", -1.0)  # sure hemen doluyor: yillik test hic ilerlemez
    monkeypatch.setattr(app_module, "YEAR_ROUNDS", 2)
    await app.bot.backtest_once()
    assert [job["module"][-8:] for job in jobs] == [".forward", "yeartest", "yeartest"]  # bitmeyen is bir tur daha
    partial = app.bot.yeartest_report(full=True)["result"]
    assert partial["complete"] is False and app.bot.backtest_state == "partial"
    assert partial["progress"]["tb_symbols_done"] == 0 and (tmp_path / "backtest" / "history.db").exists()
    assert all(row["verdict"]["passed"] is None for row in partial["strategies"].values())
    app.clock["now"] += 86400.0  # ertesi gun yeniden baslayan surec ayni pencere ve ayni gecmisle surer
    monkeypatch.setattr(app_module, "BACKTEST_BUDGET", 3600.0)
    await app.bot.backtest_once()
    done = app.bot.yeartest_report(full=True)["result"]
    assert done["complete"] is True and len(fetches) == 1 and jobs[-1]["end"] == jobs[0]["end"]
    # Biten parcalar dosyada durur: yeniden calistirilirsa V9 hic degerlendirilmez.
    job = tmp_path / "backtest" / "job.json"
    job.write_text(json.dumps({k: v for k, v in jobs[-1].items() if k != "module"} | {"deadline": 4e9}))
    backtest.write_history(Path(jobs[-1]["history"]), [("XAUUSD", "M15", 0, 1.0, 1.0, 1.0, 1.0)])
    monkeypatch.setattr(forward, "v9_symbol", lambda args: (_ for _ in ()).throw(AssertionError("yeniden calisti")))
    monkeypatch.setattr(forward, "swing_trades", lambda *a, **k: (_ for _ in ()).throw(AssertionError("yeniden calisti")))
    again = yeartest.run_job(job, InlinePool)
    assert again["complete"] is True and again["strategies"].keys() == done["strategies"].keys()
    app.clock["now"] += 8 * 86400.0  # tamamlanan sonuc eskiyince yeni pencere acilir
    monkeypatch.undo()
    short = short_job(monkeypatch, app)
    await app.bot.backtest_once()
    assert short[0]["end"] == jobs[0]["end"] + 9 * 86400.0


async def test_forward_result_is_published_before_the_year_test_and_includes_the_week_reproduction(tmp_path, monkeypatch):
    app = await started(tmp_path, dry_run=True)
    short_job(monkeypatch, app)
    published = []
    real = app.bot.repo.set_setting
    monkeypatch.setattr(app.bot.repo, "set_setting", lambda key, value: (published.append(key), real(key, value))[1])
    summary = await app.bot.backtest_once()
    keys = [key for key in published if key in ("backtest_result", "yeartest_result")]
    assert keys == ["backtest_result", "yeartest_result"]  # ileri test once yayinlanir
    replica = summary["week_replica"]
    assert "error" not in replica and set(replica["missing"]) | set(replica["coverage"]) == set(forward.week_replica.SYMBOLS)
    assert replica["soft"]["match"]["reference"] == 182 and replica["strict"]["match"]["reference"] == 184


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
    assert set(full["planned"]) == set(forward.PLAN_IDS + forward.FIXED_IDS) and full["planned"]["tb_week_trade_v1"]["raw"]["all"]["trades"] == 0
    # Portfoy kurallari bu stratejilere de uygulanir (ayni gun art arda 3 kayiptan sonra giris yok).
    day = 50 * 86400.0
    streak = [planned(day + i * 7200, -1.0) for i in range(3)] + [planned(day + 30_000, 5.0)]
    assert forward.summarize_planned(streak, split)["rules"]["all"]["sum_r"] == -3.0


# ---------------------------------------------------------------- WEEK TRADE: kaynak kodla (bt.py) birebirlik
def week_bars(golden):
    from tests.signals.market_gen import market
    from tradebot import week_replica
    bars = {}
    for index, symbol in enumerate(week_replica.SYMBOLS):
        frames, k = market(golden["seed"] + index, golden["days"]), golden["scale"][symbol]
        scale = lambda rows: [dict(b, open=b["open"] * k, high=b["high"] * k, low=b["low"] * k, close=b["close"] * k)  # noqa: E731
                              for b in rows]
        bars[symbol] = {"H4": scale(frames["H4"]), "D1": scale(frames["D1"])}
    return bars


def test_week_trade_port_reproduces_the_trade_list_of_the_original_code():
    """Referans, kullanicinin ozgun `bt.py`si ayni sentetik veriyle calistirilarak uretildi (alti sembol, portfoy
    kurallari dahil). Tasinan kod ayni islem listesini vermeli: giris zamani, sembol, yon, R, cikis, neden, uzama."""
    from pathlib import Path
    from tradebot import week_replica
    golden = json.loads((Path(__file__).parent / "week_golden.json").read_text())
    bars = week_bars(golden)
    found = week_replica.all_signals(bars)
    for name, soft in (("soft", True), ("strict", False)):
        mine = week_replica.run(bars, soft=soft, mode="bt", found=found)
        want = golden[name]
        assert len(mine) == len(want) >= 50
        for got, row in zip(mine, want):
            assert [got["at"], got["symbol"], got["side"]] == row[:3]
            assert abs(got["r"] - row[3]) < 1e-4 and [int(got["exit"]), got["why"], got["stretch"]] == row[4:]
        assert {row[1] for row in want} == set(week_replica.SYMBOLS) and {row[5] for row in want} >= {"stop", "time"}
    # Karsilastirma araci: ayni liste tam eslesir; kaydirilmis bir giris "1 gun icinde" sayilir.
    soft = week_replica.run(bars, soft=True, mode="bt", found=found)
    same = week_replica.compare(soft, golden["soft"], 1e12)
    assert same["exact"] == same["reference"] == same["ours"] and same["only_ours"] == same["only_reference"] == 0
    assert same["matched_same_result_sign"] == same["exact"]
    shifted = [dict(soft[0], at=soft[0]["at"] + 14400)] + soft[2:]
    moved = week_replica.compare(shifted, golden["soft"], 1e12)
    assert moved["within_1d"] == 1 and moved["only_reference"] == 1 and moved["exact"] == same["exact"] - 2


def test_week_trade_corrected_measurement_differs_only_where_the_source_was_optimistic():
    from tradebot import week_replica as W
    at = 1_800_000_000 // 14400 * 14400
    bar = lambda i, o, h, low, c: {"time": at + i * 14400, "open": o, "high": h, "low": low, "close": c}  # noqa: E731
    flat = lambda moment: 0.2  # noqa: E731
    # Bosluk: mum stopun otesinde aciliyor. Kaynak stop fiyatindan (-1R) sayar; duzeltilmis olcum acilistan (-1,5R).
    gap = [bar(0, 100, 100.5, 99.5, 100), bar(1, 98.5, 98.6, 98.0, 98.2)]
    assert W.simulate(1, 100.0, 1.0, 0.5, at, gap, "bt", flat)["r"] == -1.0
    assert W.simulate(1, 100.0, 1.0, 0.5, at, gap, "fixed", flat)["r"] == pytest.approx(-1.5)
    # SAT ask'tan kapanir: duzeltilmis olcumde spread stopu yaklastirir; kaynakta cikis maliyeti yoktur.
    near = [bar(0, 100, 100.9, 99.5, 100), bar(1, 100, 100.2, 99.9, 100)]
    assert W.simulate(-1, 100.0, 1.0, 0.5, at, near, "bt", flat)["why"] == "open"
    assert W.simulate(-1, 100.0, 1.0, 0.5, at, near, "fixed", flat) == {"r": -1.0, "exit": at, "why": "stop"}
    # +1R -> girise, +2R -> +1R kilit, 2R asilinca en iyi - 2 x ATR; 7 gunde +1R yoksa cikis.
    run_up = [bar(0, 100, 103.0, 99.9, 102.9), bar(1, 102.9, 102.9, 101.0, 101.5)]
    assert W.simulate(1, 100.0, 1.0, 0.5, at, run_up, "bt", flat)["r"] == pytest.approx(2.0)  # 3R - 2 x 0,5
    slow = [bar(i, 100, 100.3, 99.8, 100.2) for i in range(60)]
    timed = W.simulate(1, 100.0, 1.0, 0.5, at, slow, "bt", flat)
    assert timed["why"] == "time" and timed["exit"] - at == 7 * 86400 and timed["r"] == pytest.approx(0.2)
    # Ozet: acik kalanlar duzeltilmis toplamda yok; altin haric satir; gecelik faiz duyarliligi sonucu dusurur.
    rows = [{"at": W.START + i * 86400, "symbol": symbol, "side": "BUY", "stretch": False, "r": r, "exit": 0, "why": why,
             "nights": 5, "cost_r": 0.01, "night_r": 0.02}
            for i, (symbol, r, why) in enumerate([("XAUUSD", 3.0, "stop"), ("EURUSD", -1.0, "stop"),
                                                  ("BTCUSD", 1.0, "time"), ("XAUUSD", 2.5, "open")])]
    replica, fixed = W.summarize(rows, exclude_open=False), W.summarize(rows, exclude_open=True)
    assert replica["all"]["net_r"] == 5.5 and fixed["all"]["net_r"] == 3.0 and fixed["open"] == {"trades": 1, "r": 2.5}
    assert fixed["ex_xau"]["net_r"] == 0.0 and fixed["ex_xau"]["trades"] == 2 and fixed["all"]["pf"] == 4.0
    # Gecelik faiz: ana senaryo 0 (toplamlar). Ikinci senaryo yalnizca swap'li sembollere (caprazlara) uygulanir;
    # bu ornekte capraz yok, sonuc degismez. En kotu senaryo butun sembollere uygular.
    assert fixed["all"]["nights"] == 15 and fixed["swap"]["cross_nights"] == 0
    assert fixed["swap"]["crosses"]["0.06"] == {"all": 3.0, "ex_xau": 0.0}
    assert fixed["swap"]["everything"]["0.06"]["all"] == pytest.approx(3.0 - 15 * 0.02 * 0.06, abs=0.01)
    cross = [dict(rows[1], symbol="GBPAUD", r=1.0, nights=10)]
    assert W.summarize(cross, exclude_open=True)["swap"]["crosses"]["0.06"]["all"] == pytest.approx(1.0 - 10 * 0.02 * 0.06, abs=0.01)
    assert W.SWAP_FREE == {"BTCUSD", "ETHUSD", "XAUUSD", "EURUSD", "USDCHF"}
    assert fixed["all"]["max_dd"] == -1.0 and fixed["by_symbol"]["XAUUSD"]["trades"] == 1


def test_corrected_week_measurement_takes_the_trail_atr_from_before_the_entry():
    """Kaynak, iz suren stopun ATR'sini giris mumunu da katarak aliyordu; duzeltilmis olcum almaz."""
    from tradebot import week_replica as W
    from tradebot.signals.modules.strategies import week_trade
    from tradebot.signals.modules.strategies.v13 import Frame
    golden = json.loads((Path(__file__).parent / "week_golden.json").read_text())
    bars = week_bars(golden)
    found = W.all_signals(bars)
    fixed = W.run(bars, soft=True, mode="fixed", spread=lambda symbol, moment: 0.0, found=found)
    seen = 0
    for at, symbol, sign, stretch, risk, atr_closed in found:
        h4 = bars[symbol]["H4"]
        index = next(i for i, b in enumerate(h4) if b["time"] == at - 14400)  # sinyal mumu = giristen onceki mum
        assert atr_closed == week_trade.simple_atr(Frame(h4[max(0, index - W.WINDOW_H4 + 1):index + 1]))[-1]
        with_entry_bar = week_trade.simple_atr(Frame(h4[:index + 2]))[-1]
        seen += int(abs(with_entry_bar - atr_closed) > 1e-12)
    assert seen > len(found) * 0.9 and len(fixed) > 40  # iki ATR neredeyse her zaman farklidir
    # Ayni girdiyle iki kip yalnizca ATR kaynagi ve dolum kuraliyla ayrisir: en az bir islemin sonucu degisir.
    plain = W.run(bars, soft=True, mode="bt", found=found)
    assert [t["at"] for t in plain][:5] == [t["at"] for t in fixed][:5]


def test_listed_swap_cost_counts_each_rollover_with_its_weekday_multiplier():
    """Broker'in listeledigi swap (gece basina puan) uygulansaydi islemin maliyeti: carsamba 3 kat, hafta sonu 0."""
    from tradebot import week_replica as W
    monday = 4 * 86400.0  # 1970-01-05 pazartesi 00:00 UTC
    swap = {"long": -16.5, "short": 0.0, "point": 0.00001,
            "multipliers": {"MON": 1, "TUE": 1, "WED": 3, "THU": 1, "FRI": 1, "SAT": 0, "SUN": 0}}
    week = W.listed_swap_r(swap, 1, monday + 3600, monday + 7 * 86400 + 3600, 0.012)  # bir tam hafta: 1+1+3+1+1 = 7
    assert week == pytest.approx(-16.5 * 0.00001 * 7 / 0.012)
    assert W.listed_swap_r(swap, 1, monday + 3600, monday + 20 * 3600, 0.012) == 0.0  # gun devrinden once kapandi
    assert W.listed_swap_r(swap, 1, monday + 3600, monday + 23 * 3600, 0.012) == pytest.approx(-16.5e-5 / 0.012)
    assert W.listed_swap_r(swap, -1, monday + 3600, monday + 7 * 86400, 0.012) == 0.0  # satis tarafi 0
    assert W.listed_swap_r(None, 1, 0, 86400, 1.0) is None and W.listed_swap_r({"long": None, "point": 1e-5}, 1, 0, 1, 1.0) is None
    rows = [{"at": W.START, "symbol": "EURUSD", "side": "BUY", "stretch": False, "r": 1.0, "exit": 0, "why": "stop",
             "nights": 7, "cost_r": 0.01, "night_r": 0.02, "listed_swap_r": -0.1},
            {"at": W.START + 86400, "symbol": "XAUUSD", "side": "SELL", "stretch": False, "r": 2.0, "exit": 0,
             "why": "stop", "nights": 3, "cost_r": 0.01, "night_r": 0.02, "listed_swap_r": None}]
    listed = W.summarize(rows, exclude_open=True)["swap"]["listed"]
    assert listed == {"trades_with_data": 1, "trades": 2, "cost_r": -0.1, "all": 2.9, "ex_xau": 0.9,
                      "by_symbol": {"BTCUSD": 0, "ETHUSD": 0, "XAUUSD": 0, "EURUSD": -0.1, "USDCHF": 0, "GBPAUD": 0}}


def test_listed_swaps_are_read_from_the_real_instrument_conditions():
    import json as _json
    from pathlib import Path as _Path
    from tradebot.exness import schema
    raw = _json.loads((_Path(__file__).parent / "exness/fixtures/real/conditions/EURUSD.json").read_text())
    item = schema.parse_instrument(raw)
    assert item.swap_long == -16.5 and item.swap_short == 0.0
    assert item.swap_multipliers["WED"] == 3 and item.swap_multipliers["SAT"] == 0
    assert schema.parse_instrument({**raw, "swap_long": None, "swap_multipliers": "bozuk"}).swap_multipliers is None
