import dataclasses

import pytest

from tests.signals.helpers import instrument
from tradebot.config import ManageSettings
from tradebot.manager.manage import MoveSL, NoOp, PartialClose, decide
from tradebot.store.repo import Trade

EURUSD = instrument("EURUSD", kind="forex", tick_size=0.00001, digits=5, contract_size=100000.0)
SETTINGS = ManageSettings()
COST = 0.00003


def buy(**extra):
    values = dict(position_id="1", origin="bot", symbol="EURUSD", side="BUY", volume=0.10, initial_volume=0.10,
                  entry=1.10000, sl=1.09700, tp1=1.10600, tp2=1.10900, initial_risk_r_price=0.00300, opened_at=1.0)
    values.update(extra)
    return Trade(**values)


def sell(**extra):
    values = dict(side="SELL", sl=1.10300, tp1=1.09400, tp2=1.09100)
    values.update(extra)
    return buy(**values)


def run(trade, bid, ask=None, atr=0.00100, inst=EURUSD, settings=SETTINGS, cost=COST):
    return decide(trade, bid=bid, ask=bid + 0.00002 if ask is None else ask, atr_m15=atr,
                  cost_per_unit=cost, instrument=inst, settings=settings)


def moves(actions):
    return [a for a in actions if isinstance(a, MoveSL)]


def test_no_be_before_1r():
    assert run(buy(), bid=1.10299) == []
    assert run(buy(), bid=1.09900) == []


def test_be_at_1r_includes_costs():
    actions = run(buy(), bid=1.10300)
    assert actions == [MoveSL(1.10003, "breakeven")]
    # Maliyet tick'e yukari yuvarlanir: islem en kotu ihtimalle zararsiz kapanir
    assert run(buy(), bid=1.10300, cost=0.000031) == [MoveSL(1.10004, "breakeven")]


def test_be_is_not_repeated_once_stop_is_at_or_above_it():
    assert run(buy(sl=1.10003, be_done=True), bid=1.10400) == []
    assert run(buy(sl=1.10100, be_done=True), bid=1.10400) == []


def test_partial_at_2r_rounds_to_step():
    trade = buy(sl=1.10003, be_done=True, volume=0.15, initial_volume=0.15)
    actions = run(trade, bid=1.10600)
    assert actions == [PartialClose(0.07)]  # 0.075 adima asagi yuvarlanir
    assert run(buy(sl=1.10003, be_done=True), bid=1.10600) == [PartialClose(0.05)]
    assert run(buy(sl=1.10003, be_done=True), bid=1.10599) == []


def test_be_and_partial_are_both_requested_on_a_jump():
    actions = run(buy(), bid=1.10650)
    assert actions == [MoveSL(1.10003, "breakeven"), PartialClose(0.05)]


def test_partial_skipped_when_remaining_below_min():
    tiny = buy(sl=1.10003, be_done=True, volume=0.01, initial_volume=0.01)
    actions = run(tiny, bid=1.10600)
    assert actions == [NoOp("partial_skipped")]
    odd = buy(sl=1.10003, be_done=True, volume=0.02, initial_volume=0.02)
    assert run(odd, bid=1.10600) == [PartialClose(0.01)]
    big_min = dataclasses.replace(EURUSD, volume_min=0.10)
    assert run(buy(sl=1.10003, be_done=True, volume=0.15), bid=1.10600, inst=big_min) == [NoOp("partial_skipped")]


def test_trailing_starts_after_partial_stage_and_follows_price():
    trade = buy(sl=1.10003, be_done=True, partial_done=True, volume=0.05)
    assert run(trade, bid=1.10700) == [MoveSL(1.10600, "trail")]
    assert run(trade, bid=1.10700, atr=0.00250) == [MoveSL(1.10450, "trail")]
    before_stage = buy(sl=1.10003, be_done=True, partial_done=False, volume=0.10)
    assert moves(run(before_stage, bid=1.10500)) == []  # 2R'ye ulasmadan iz surme yok


def test_trailing_never_loosens():
    trade = buy(sl=1.10600, be_done=True, partial_done=True, volume=0.05)
    assert run(trade, bid=1.10650) == []  # 1.10550 mevcut SL'den geride
    assert run(trade, bid=1.10700) == []  # esit: degisiklik yok
    assert run(trade, bid=1.10701) == [MoveSL(1.10601, "trail")]
    assert run(trade, bid=1.10800, atr=None) == []


def test_user_override_respected():
    tighter = buy(sl=1.10150, user_sl_override=True)  # kullanici SL'i basa basin ustune cekmis
    assert run(tighter, bid=1.10300) == []
    looser = buy(sl=1.09500, user_sl_override=True)  # kullanici SL'i genisletmis: bot zarar yonune almaz, sikilastirabilir
    actions = run(looser, bid=1.10300)
    assert actions == [MoveSL(1.10003, "breakeven")]
    assert all(a.price > looser.sl for a in moves(actions))


def test_manage_flag_and_missing_risk_disable_management():
    assert run(buy(manage=False), bid=1.11000) == []
    assert run(buy(initial_risk_r_price=None), bid=1.11000) == []
    assert run(buy(initial_risk_r_price=0.0), bid=1.11000) == []
    assert run(buy(closed_at=5.0), bid=1.11000) == []
    assert run(buy(sl=None), bid=1.10300) == [MoveSL(1.10003, "breakeven")]


def test_sell_side_mirror():
    assert run(sell(), bid=1.09702, ask=1.09704) == []  # ask henuz 1R'de degil
    assert run(sell(), bid=1.09698, ask=1.09700) == [MoveSL(1.09997, "breakeven")]
    staged = sell(sl=1.09997, be_done=True)
    assert run(staged, bid=1.09398, ask=1.09400) == [PartialClose(0.05)]
    trailing = sell(sl=1.09997, be_done=True, partial_done=True, volume=0.05)
    assert run(trailing, bid=1.09298, ask=1.09300) == [MoveSL(1.09400, "trail")]
    assert run(dataclasses.replace(trailing, sl=1.09350), bid=1.09298, ask=1.09300) == []


def test_respects_stops_level():
    strict = dataclasses.replace(EURUSD, stops_level=50)  # 50 point = 0.00050
    trailing = buy(sl=1.10003, be_done=True, partial_done=True, volume=0.05)
    # ATR 0.00020 ile hedef SL 1.10680 olurdu; broker mesafesi 1.10650'ye sinirlar
    assert run(trailing, bid=1.10700, atr=0.00020, inst=strict) == [MoveSL(1.10650, "trail")]
    # Sinirlanmis deger mevcut SL'den iyi degilse hic hareket yok
    near = buy(sl=1.10660, be_done=True, partial_done=True, volume=0.05)
    assert run(near, bid=1.10700, atr=0.00020, inst=strict) == []
    # Mesafe sifir olsa bile SL fiyatin dogru tarafinda en az bir tick geride kalir
    assert run(trailing, bid=1.10700, atr=0.0) == [MoveSL(1.10699, "trail")]


def test_custom_thresholds():
    settings = ManageSettings(be_at_r=0.5, partial_at_r=1.0, partial_fraction=0.3, trail_atr_mult=2.0)
    assert run(buy(), bid=1.10150, settings=settings) == [MoveSL(1.10003, "breakeven")]
    staged = buy(sl=1.10003, be_done=True)
    assert run(staged, bid=1.10300, settings=settings) == [PartialClose(0.03)]
    trailing = buy(sl=1.10003, be_done=True, partial_done=True)
    assert run(trailing, bid=1.10700, settings=settings) == [MoveSL(1.10500, "trail")]
