import logging

import pytest

from tests.signals.helpers import NOW, account, instrument, provider_from_fixture
from tradebot.signals.adapter import Candidate, evaluate, evaluate_symbol


def run(provider, **overrides):
    args = dict(equity=10_000.0, risk_pct=0.5, commission_per_lot=0.0, enabled_strategies=None, now=NOW)
    args.update(overrides)
    return evaluate_symbol(provider, "XAUUSD", **args)


def test_buy_fixture_yields_candidate():
    candidate = run(provider_from_fixture("BUY"))
    assert isinstance(candidate, Candidate)
    assert candidate.side == "BUY" and candidate.symbol == "XAUUSD"
    assert candidate.stop_loss < candidate.entry < candidate.take_profit_1 < candidate.take_profit_2
    assert candidate.lots >= 0.01 and candidate.net_rr >= 1.5
    assert 0 < candidate.risk_amount <= 10_000.0 * 0.005
    assert candidate.strategy_id.startswith("fx_") and len(candidate.setup_id) == 24
    assert len(candidate.analysis_id) == 64
    r = candidate.entry - candidate.stop_loss
    assert candidate.take_profit_2 - candidate.entry == pytest.approx(3 * r, abs=0.011)


def test_sell_fixture_yields_candidate():
    candidate = run(provider_from_fixture("SELL"))
    assert candidate.side == "SELL" and candidate.stop_loss > candidate.entry > candidate.take_profit_1


def test_same_bar_gives_same_setup_id():
    assert run(provider_from_fixture("BUY")).setup_id == run(provider_from_fixture("BUY")).setup_id


def test_wait_yields_none(caplog):
    provider = provider_from_fixture("BUY", ticks=50)  # spread politikasi dogrulanamaz
    with caplog.at_level(logging.INFO, logger="tradebot.signals.adapter"):
        assert run(provider) is None
    assert "XAUUSD" in caplog.text
    result = evaluate(provider, "XAUUSD", equity=10_000.0, risk_pct=0.5, commission_per_lot=0.0,
                      enabled_strategies=None, now=NOW)
    assert result.candidate is None and result.decision not in ("BUY_CANDIDATE", "SELL_CANDIDATE")
    assert result.reasons


def test_min_lot_over_risk_returns_none_without_notification():
    provider = provider_from_fixture("BUY", acct=account(equity=20.0))
    result = evaluate(provider, "XAUUSD", equity=20.0, risk_pct=0.5, commission_per_lot=0.0,
                      enabled_strategies=None, now=NOW)
    assert result.candidate is None and result.decision == "NO_TRADE"
    assert "minimum lot exceeds risk budget" in " ".join(result.reasons)
    # Adaptorun bildirim gonderebilecegi bir bagimliligi yoktur: yalnizca sonuc doner ve loglanir.
    import inspect
    assert "notif" not in inspect.signature(evaluate).parameters.__repr__().lower()


def test_cent_account_sizes_in_cent_currency():
    cent = instrument(contract_size=1.0)  # cent hesapta 1 lot = 1 ons varsayimi
    provider = provider_from_fixture("BUY", acct=account("USC", 3000.0), inst=cent)
    candidate = run(provider, equity=3000.0)
    assert candidate is not None
    assert candidate.risk_amount <= 15.0 and candidate.lots >= 0.01


def test_blocked_account_yields_none():
    assert run(provider_from_fixture("BUY", acct=account(can_open=False))) is None


def test_disabled_strategies():
    candidate = run(provider_from_fixture("BUY"))
    assert run(provider_from_fixture("BUY"), enabled_strategies={candidate.strategy_id}) is not None
    assert run(provider_from_fixture("BUY"), enabled_strategies={"fx_range_reversion_v6"}) is None
    assert run(provider_from_fixture("BUY"), enabled_strategies=set()) is None
    assert run(provider_from_fixture("BUY"), enabled_strategies={"bilinmeyen"}) is None


def test_commission_lowers_net_rr():
    free = run(provider_from_fixture("BUY"))
    paid = run(provider_from_fixture("BUY"), commission_per_lot=7.0)
    assert paid is None or paid.net_rr < free.net_rr
