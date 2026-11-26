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
