import pytest

from tests.signals.helpers import instrument
from tradebot.config import RiskSettings
from tradebot.risk.portfolio import check_entry
from tradebot.signals.adapter import Candidate
from tradebot.store.repo import Trade

INSTRUMENTS = {s: instrument(s, kind="forex") for s in ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURGBP", "NZDCAD")}
INSTRUMENTS["XAUUSD"] = instrument("XAUUSD")
INSTRUMENTS["BTCUSD"] = instrument("BTCUSD", kind="crypto")


def candidate(symbol="EURUSD", side="BUY"):
    return Candidate(symbol=symbol, side=side, entry=1.1, stop_loss=1.09 if side == "BUY" else 1.11,
                     take_profit_1=1.12, take_profit_2=1.13, lots=0.1, strategy_id="fx_trend_momentum_v6",
                     setup_id="s-" + symbol + side, net_rr=1.9, analysis_id="a" * 64, risk_amount=15.0)


def trade(symbol, side="BUY", origin="bot", n=[0]):
    n[0] += 1
    return Trade(position_id=str(n[0]), origin=origin, symbol=symbol, side=side, volume=0.1, entry=1.1, sl=1.09,
                 initial_risk_r_price=0.01, opened_at=1.0)


def check(cand=None, **overrides):
    args = dict(open_bot=[], bot_pnl_today=0.0, bot_pnl_total=0.0, start_capital=3000.0, halted=False,
                settings=RiskSettings(), instruments=INSTRUMENTS)
    args.update(overrides)
    return check_entry(cand or candidate(), **args)


def test_clean_state_allows():
    verdict = check()
    assert verdict.allowed is True and verdict.should_halt is False and verdict.reason == "ok"


def test_halted_blocks():
    verdict = check(halted=True)
    assert verdict.allowed is False and "dur" in verdict.reason


def test_max_open_bot_trades():
    open_bot = [trade("GBPUSD", "SELL"), trade("USDJPY", "SELL"), trade("XAUUSD")]
    assert check(open_bot=open_bot[:2]).allowed is True
    assert check(candidate("NZDCAD"), open_bot=open_bot).allowed is False
    assert check(candidate("NZDCAD"), open_bot=open_bot, settings=RiskSettings(max_open_bot=4)).allowed is True


def test_one_trade_per_symbol():
    verdict = check(open_bot=[trade("EURUSD", "SELL")])
    assert verdict.allowed is False and "EURUSD" in verdict.reason


def test_currency_exposure_counts_both_legs():
    usd_short = [trade("EURUSD", "BUY"), trade("GBPUSD", "BUY")]  # iki kez USD satildi
    assert check(candidate("AUDUSD", "BUY"), open_bot=usd_short).allowed is False
    assert check(candidate("USDJPY", "SELL"), open_bot=usd_short).allowed is False
    assert check(candidate("USDJPY", "BUY"), open_bot=usd_short).allowed is True
    assert check(candidate("NZDCAD", "BUY"), open_bot=usd_short).allowed is True
    eur_long = [trade("EURUSD", "BUY"), trade("EURGBP", "BUY")]
    blocked = check(candidate("EURUSD", "BUY"), open_bot=[trade("EURGBP", "BUY"), trade("EURJPY", "BUY")])
    assert blocked.allowed is False and "EUR" in blocked.reason  # EUR iki kez alinmis
    one_each = [trade("EURGBP", "BUY"), trade("GBPUSD", "SELL")]  # EUR long 1, GBP short 2, USD long 1
    assert check(candidate("EURUSD", "BUY"), open_bot=one_each).allowed is True
    assert check(candidate("GBPJPY", "SELL"), open_bot=one_each).allowed is False
    assert check(candidate("XAUUSD", "SELL"), open_bot=eur_long).allowed is True


def test_metal_and_crypto_use_instrument_currencies():
    open_bot = [trade("XAUUSD", "BUY"), trade("BTCUSD", "BUY")]  # iki kez USD satildi
    verdict = check(candidate("EURUSD", "BUY"), open_bot=open_bot)
    assert verdict.allowed is False and "USD" in verdict.reason
    assert check(candidate("EURUSD", "SELL"), open_bot=open_bot).allowed is True


def test_daily_loss_limit():
    assert check(bot_pnl_today=-149.99).allowed is True
    verdict = check(bot_pnl_today=-150.0)  # 3000'in %5'i
    assert verdict.allowed is False and verdict.should_halt is False and "gunluk" in verdict.reason
    assert check(bot_pnl_today=-150.0, settings=RiskSettings(daily_loss_pct=10)).allowed is True


def test_total_loss_sets_halt():
    assert check(bot_pnl_total=-749.0).should_halt is False
    verdict = check(bot_pnl_total=-750.0)  # 3000'in %25'i
    assert verdict.allowed is False and verdict.should_halt is True and "toplam" in verdict.reason


def test_manual_trades_not_counted():
    manual = [trade("EURUSD", "BUY", "manual"), trade("GBPUSD", "BUY", "manual"), trade("AUDUSD", "BUY", "manual"),
              trade("XAUUSD", "BUY", "manual")]
    assert check(candidate("EURUSD", "BUY"), open_bot=manual).allowed is True


def test_unknown_start_capital_blocks():
    for capital in (None, 0.0, -5.0):
        assert check(start_capital=capital).allowed is False


def test_unknown_instrument_falls_back_to_symbol_halves():
    open_bot = [trade("CHFJPY", "SELL"), trade("CADJPY", "SELL")]  # JPY iki kez alindi
    assert check(candidate("USDJPY", "SELL"), open_bot=open_bot, instruments={}).allowed is False
