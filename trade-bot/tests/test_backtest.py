"""Ileri test: gecmis mumlarin yeniden oynatilmasi ve botun bu isi nasil calistirdigi."""
import asyncio
import json

from tests.app_helpers import started
from tests.test_scan_summary import public_get
from tradebot import app as app_module
from tradebot import backtest
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


async def test_bot_runs_the_backtest_once_in_dry_run_and_publishes_only_numbers(tmp_path, monkeypatch):
    app = await started(tmp_path, dry_run=True)
    monkeypatch.setattr(app_module, "BACKTEST_DAYS", 0.05)  # ~5 mum: gercek V9 motoru, kisa sure
    monkeypatch.setattr(app_module, "BACKTEST_FETCH_PAUSE", 0.0)
    jobs = []

    async def in_process(job):
        jobs.append(json.loads(job.read_text()))
        await asyncio.to_thread(backtest.run_job, job)
        return 0

    monkeypatch.setattr(app.bot, "_backtest_spawn", in_process)
    assert (await public_get(app, "/health/backtest")).json() == {"state": "idle", "result": None}
    summary = await app.bot.backtest_once()
    assert summary["version"] == backtest.VERSION and summary["coverage"]["evaluations"] >= 4
    assert summary["coverage"]["errors"] == 0 and "XAUUSD" in summary["coverage"]["symbols"]
    assert jobs[0]["account"]["equity"] == 10_000.0  # gercek varlik dosyaya yazilmaz (sahte hesap da 10000)
    assert not (tmp_path / "backtest" / "history.db").exists()  # gecmis dosyasi isten sonra silinir
    response = await public_get(app, "/health/backtest")
    assert response.json()["state"] == "done" and response.json()["result"]["total"] == summary["total"]
    for secret in ("123456", "balance", "equity", "lots", "risk_amount"):
        assert secret not in response.text
    assert await app.bot.backtest_once() is None  # taze sonuc varken yeniden calismaz


async def test_backtest_never_runs_live_and_a_failure_is_harmless(tmp_path, monkeypatch):
    live = await started(tmp_path / "live")
    assert await live.bot.backtest_once() is None and live.bot.backtest_state == "idle"
    app = await started(tmp_path / "dry", dry_run=True)
    monkeypatch.setattr(app_module, "BACKTEST_DAYS", 0.05)
    monkeypatch.setattr(app_module, "BACKTEST_FETCH_PAUSE", 0.0)

    async def crash(job):
        return 1

    monkeypatch.setattr(app.bot, "_backtest_spawn", crash)
    assert await app.bot.backtest_once() is None
    assert app.bot.backtest_state == "failed: RuntimeError"
    assert (await app.bot.on_bar_close()).would_open == 1  # bot etkilenmez
