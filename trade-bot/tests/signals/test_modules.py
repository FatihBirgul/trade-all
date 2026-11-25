"""Ortak modul arayuzu: oylar tasima oncesiyle birebir ayni; yeni modul tek dosya + tek kayit."""
import copy

import pytest

from tests.app_helpers import NOW
from tests.signals import legacy_votes
from tests.signals.test_fusion import report
from tradebot.config import FUSION_MODULES
from tradebot.signals import fusion
from tradebot.signals.modules import Context, Signal, Vote, base, modules, register


def test_registry_lists_every_fusion_module_once_in_weight_order():
    assert [m.id for m in modules("vote")] == list(FUSION_MODULES)
    assert all(m.kind == "vote" for m in modules("vote"))
    with pytest.raises(ValueError, match="iki kez"):
        register(modules("vote")[0])


def variants(data):
    """Gercek V9 raporu ve alanlari oynatilmis kopyalari: her modulun uc sonucu da gorulsun."""
    yield data
    for path, value in ((("regime", "direction"), "bearish"), (("regime", "direction"), None),
                        (("momentum", "rsi14_wilder"), 30.0), (("momentum", "macd_histogram"), -1.0),
                        (("confluence", "bullish_strength"), 0.0), (("confluence", "bearish_strength"), 99.0),
                        (("market_structure", "v5_pivots"), {"trend": "down"}),
                        (("market_structure", "v5_pivots"), {"break_of_structure": "bullish", "trend": "down"}),
                        (("mtf", "source_context"), {"higher_timeframe_alignment": {"direction": "up", "agreement_ratio": 0.4}}),
                        (("mtf", "source_context"), {"higher_timeframe_alignment": {"direction": "down", "agreement_ratio": 1}}),
                        (("candlestick_patterns", "patterns"), [{"direction": "bullish", "confirmed_at": 1, "age_bars": 2}]),
                        (("candlestick_patterns", "patterns"), [{"direction": "bearish", "confirmed_at": None}]),
                        (("chart_patterns", "patterns"), [{"direction": "bearish", "state": "ACTIVE"},
                                                          {"direction": "bullish", "state": "EXPIRED"}]),
                        (("routing", "strategy_id"), "baska"), (("strategies",), None), (("mtf",), "bozuk")):
        changed = copy.deepcopy(data)
        node = changed
        for key in path[:-1]:
            node = node.setdefault(key, {}) if isinstance(node.get(key), dict) or key not in node else node[key]
        node[path[-1]] = value
        yield changed


@pytest.mark.parametrize("direction", ["BUY", "SELL"])
def test_votes_identical_to_pre_refactor(direction):
    data = report(direction).model_dump()
    checked = 0
    for variant in variants(data):
        for side in ("BUY", "SELL"):
            for kind, now in (("metal", NOW), ("crypto", NOW), ("forex", NOW + 15 * 3600)):
                new = fusion.collect_votes(variant, side, now=now, kind=kind)
                old = legacy_votes.collect_votes(variant, side, now=now, kind=kind)
                assert [(v.module, v.value, v.detail) for v in new] == [(v.module, v.value, v.detail) for v in old]
                checked += 1
    assert checked == 17 * 2 * 3


def test_module_raising_is_an_abstain_not_a_crash(monkeypatch):
    class Broken:
        id, kind = "regime", "vote"

        def evaluate(self, context):
            raise RuntimeError("bozuk modul")

    monkeypatch.setitem(base._REGISTRY, "regime", Broken())
    votes = {v.module: v.value for v in fusion.collect_votes(report("BUY"), "BUY", now=NOW, kind="metal")}
    assert votes["regime"] == 0 and len(votes) == len(FUSION_MODULES)  # destek sayilmaz, tarama surer


def test_adding_a_module_is_one_class_and_one_register_call(monkeypatch):
    monkeypatch.setattr(base, "_REGISTRY", dict(base._REGISTRY))

    class AlwaysLong:
        id, kind = "tb_test_strategy", "strategy"

        def evaluate(self, context: Context):
            return Signal("BUY", 1.1, 1.09, 1.12, "test", bar_time=0)

    register(AlwaysLong())
    assert [m.id for m in modules("strategy")][-1] == "tb_test_strategy"
    assert [m.id for m in modules("vote")] == list(FUSION_MODULES)  # oy modulleri etkilenmez
    signal = modules("strategy")[-1].evaluate(Context(symbol="EURUSD", now=0.0))
    assert isinstance(signal, Signal) and not isinstance(signal, Vote)
    with pytest.raises(ValueError, match="gecersiz modul turu"):
        register(type("Bad", (), {"id": "x", "kind": "indicator"})())
