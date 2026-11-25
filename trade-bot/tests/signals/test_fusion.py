import dataclasses

import pytest
from pydantic import ValidationError

from tests.signals.helpers import NOW, instrument, provider_from_fixture
from tradebot.config import FusionSettings
from tradebot.signals import v9
from tradebot.signals.fusion import MODULES, Vote, collect_votes, risk_multiplier, scale_lots, score

SATURDAY = NOW + 86_400


def votes(**values):
    return [Vote(module, values.get(module, 0), "") for module in MODULES]


def test_all_support_is_100_all_against_is_0_all_abstain_is_50():
    weights = FusionSettings().weights
    assert score([Vote(m, 1, "") for m in MODULES], weights) == 100.0
    assert score([Vote(m, -1, "") for m in MODULES], weights) == 0.0
    assert score([Vote(m, 0, "") for m in MODULES], weights) == 50.0
    assert score([], weights) == 50.0


def test_weights_shift_score():
    flat = {m: 1.0 for m in MODULES}
    heavy = {**flat, "mtf": 5.0}
    mixed = votes(mtf=1, regime=-1)
    assert score(mixed, flat) == pytest.approx(50.0)
    assert score(mixed, heavy) > 50.0
    assert score(votes(mtf=-1, regime=1), heavy) < 50.0


def test_zero_weight_module_ignored():
    weights = {m: 0.0 for m in MODULES} | {"mtf": 1.0}
    assert score(votes(mtf=1, regime=-1, momentum=-1), weights) == 100.0
    assert score(votes(mtf=1), {m: 0.0 for m in MODULES}) == 50.0
    assert score(votes(mtf=1), {}) > 50.0  # agirligi verilmeyen modul 1.0 sayilir


def test_tiers():
    settings = FusionSettings()
    assert risk_multiplier(39.9, settings) is None
    assert risk_multiplier(40.0, settings) == 0.5
    assert risk_multiplier(59.9, settings) == 0.5
    assert risk_multiplier(60.0, settings) == 0.75
    assert risk_multiplier(79.9, settings) == 0.75
    assert risk_multiplier(80.0, settings) == 1.0
    assert risk_multiplier(100.0, settings) == 1.0
    custom = FusionSettings(min_score=50, mid_score=70, high_score=90)
    assert risk_multiplier(49.0, custom) is None and risk_multiplier(89.0, custom) == 0.75


def test_settings_validation():
    for bad in (dict(min_score=-1), dict(high_score=101), dict(min_score=70, mid_score=60),
                dict(mid_score=90, high_score=80), dict(weights={"mtf": -1.0}), dict(weights={"mtf": 11.0})):
        with pytest.raises(ValidationError):
            FusionSettings(**bad)
    assert FusionSettings().weights["mtf"] == 2.0 and FusionSettings().weights["regime"] == 2.0
    assert set(FusionSettings().weights) == set(MODULES)


def test_scaled_lots_round_down_to_step():
    inst = instrument()  # adim 0.01, en kucuk 0.01
    assert scale_lots(0.10, 1.0, inst) == pytest.approx(0.10)
    assert scale_lots(0.10, 0.75, inst) == pytest.approx(0.07)  # 0.075 asagi yuvarlanir
    assert scale_lots(0.03, 0.5, inst) == pytest.approx(0.01)   # 0.015 -> 0.01


def test_multiplier_below_min_lot_becomes_observation():
    inst = instrument()
    assert scale_lots(0.01, 0.5, inst) is None  # 0.005: en kucuk lotun alti -> islem yok, yukari yuvarlanmaz
    assert scale_lots(0.01, 0.75, inst) is None
    big_min = dataclasses.replace(inst, volume_min=0.10, volume_step=0.10)
    assert scale_lots(0.10, 0.75, big_min) is None


def report(direction):
    return v9.engine().analyze(provider_from_fixture(direction), "XAUUSD", "M15", now=NOW,
                               confirmations=("H1", "H4"), balance=10_000, risk_pct=0.5)


def test_votes_from_buy_fixture_report():
    result = {v.module: v.value for v in collect_votes(report("BUY"), "BUY", now=NOW, kind="metal")}
    assert set(result) == set(MODULES)
    assert result["mtf"] == 1 and result["regime"] == 1 and result["momentum"] == 1 and result["confluence"] == 1
    assert result["session"] == 1  # Cuma 08:00 UTC: Londra seansi
    assert result["other_strategies"] == 0
    assert score(collect_votes(report("BUY"), "BUY", now=NOW, kind="metal"), FusionSettings().weights) >= 80


def test_sell_fixture_mirrors():
    sell = {v.module: v.value for v in collect_votes(report("SELL"), "SELL", now=NOW, kind="metal")}
    assert sell["mtf"] == 1 and sell["regime"] == 1 and sell["momentum"] == 1
    against = {v.module: v.value for v in collect_votes(report("SELL"), "BUY", now=NOW, kind="metal")}
    assert against["mtf"] == -1 and against["regime"] == -1 and against["momentum"] == -1


def test_session_vote_by_kind_and_time():
    buy = report("BUY")
    by = lambda now, kind: {v.module: v.value for v in collect_votes(buy, "BUY", now=now, kind=kind)}["session"]
    assert by(NOW, "forex") == 1
    assert by(SATURDAY, "forex") == -1  # seans disi
    assert by(SATURDAY, "crypto") == 0 and by(NOW, "crypto") == 0
    assert by(NOW - 6 * 3600, "forex") == 0  # 02:00 UTC: yalnizca Asya


def test_votes_tolerate_missing_sections():
    result = collect_votes({"strategies": [], "routing": None}, "BUY", now=NOW, kind="forex")
    assert {v.module for v in result} == set(MODULES)
    assert all(v.value == 0 for v in result if v.module != "session")


# ---------------------------------------------------------------- servis dongusuyle
import json  # noqa: E402

from tests.app_helpers import started  # noqa: E402
from tradebot.config import BotSettings  # noqa: E402


async def test_filled_trade_stores_score_and_votes(tmp_path):
    app = await started(tmp_path)
    summary = await app.bot.on_bar_close()
    await app.fake.flush()
    trade = app.repo.open_trades("bot")[0]
    assert summary.opened == 1 and trade.score >= 80
    stored = json.loads(trade.votes_json)
    assert stored["mtf"] == 1 and set(stored) == set(MODULES)
    signal = next(e for e in app.repo.events() if e["kind"] == "signal")
    assert signal["data"]["score"] == trade.score and signal["data"]["votes"]["regime"] == 1


async def test_low_score_records_observation_and_sends_no_order(tmp_path):
    app = await started(tmp_path)
    app.repo.set_bot_settings(BotSettings(dry_run=False, fusion=FusionSettings(min_score=100, mid_score=100, high_score=100)))
    summary = await app.bot.on_bar_close()
    assert summary.candidates == 1 and summary.observed == 1 and summary.opened == 0
    assert app.fake.calls("POST", "/positions") == [] and app.notifier.sent == []
    observed = next(e for e in app.repo.events() if e["kind"] == "signal_observed")
    assert observed["data"]["symbol"] == "XAUUSD" and 80 <= observed["data"]["score"] < 100
    assert "güven puanı" in observed["message"]


async def test_mid_score_reduces_lots_and_risk(tmp_path):
    full = await started(tmp_path / "full")
    await full.bot.on_bar_close()
    await full.fake.flush()
    full_trade = full.repo.open_trades("bot")[0]

    app = await started(tmp_path / "half")
    app.repo.set_bot_settings(BotSettings(dry_run=False, fusion=FusionSettings(min_score=40, mid_score=100, high_score=100)))
    await app.bot.on_bar_close()
    await app.fake.flush()
    half = app.repo.open_trades("bot")[0]
    assert half.volume == pytest.approx(int(full_trade.volume * 50 + 1e-9) / 100)  # 0.5x, adima asagi
    assert half.risk_amount == pytest.approx(full_trade.risk_amount * half.volume / full_trade.volume)
    assert half.volume < full_trade.volume and half.sl == full_trade.sl  # stop ve hedefler degismez


async def test_fusion_disabled_uses_full_risk(tmp_path):
    app = await started(tmp_path)
    app.repo.set_bot_settings(BotSettings(dry_run=False, fusion=FusionSettings(enabled=False, min_score=100,
                                                                              mid_score=100, high_score=100)))
    summary = await app.bot.on_bar_close()
    await app.fake.flush()
    trade = app.repo.open_trades("bot")[0]
    assert summary.opened == 1 and trade.score is None and trade.votes_json is None


async def test_score_never_raises_risk_above_v9_sizing(tmp_path):
    app = await started(tmp_path)
    await app.bot.on_bar_close()
    await app.fake.flush()
    trade = app.repo.open_trades("bot")[0]
    assert trade.risk_amount <= 10_000 * 0.005 + 1e-6
