"""Tests for the NEW outcome-tracking + watchlist-related backend endpoints.

Covers:
  GET  /api/performance
  POST /api/history/evaluate-all
  POST /api/analysis  -> outcome defaults + history includes outcome
  Unit test: outcome_engine WIN/LOSS/NEUTRAL correctness on crafted candles.
"""
import os
import sys
import pytest
import requests

BASE_URL = (
    os.environ.get("EXPO_BACKEND_URL")
    or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or ""
).rstrip("/")
API = f"{BASE_URL}/api"
LONG = 120

# Make outcome engine importable (unit test).
sys.path.insert(0, "/app/backend")


@pytest.fixture(scope="session")
def api_client():
    if not BASE_URL:
        pytest.skip("Set EXPO_BACKEND_URL to an isolated V1 test server")
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------------- /api/performance ----------------
class TestPerformance:
    def test_performance_shape(self, api_client):
        r = api_client.get(f"{API}/performance", timeout=20)
        assert r.status_code == 200, r.text
        j = r.json()
        for k in ("total", "wins", "losses", "pending", "neutral", "resolved", "hit_rate", "note", "by_direction"):
            assert k in j, f"Missing key {k}"
        assert isinstance(j["total"], int)
        assert isinstance(j["wins"], int)
        assert isinstance(j["losses"], int)
        assert isinstance(j["pending"], int)
        assert isinstance(j["neutral"], int)
        assert j["resolved"] == j["wins"] + j["losses"]
        # hit_rate is null OR percentage 0-100
        hr = j["hit_rate"]
        assert hr is None or (0 <= hr <= 100)
        bd = j["by_direction"]
        assert "bullish" in bd and "bearish" in bd
        for side in ("bullish", "bearish"):
            for k in ("total", "wins", "losses", "pending", "resolved", "hit_rate"):
                assert k in bd[side]


# ---------------- /api/history/evaluate-all ----------------
class TestEvaluateAll:
    def test_evaluate_all(self, api_client):
        r = api_client.post(f"{API}/history/evaluate-all", timeout=LONG)
        assert r.status_code == 200, r.text
        j = r.json()
        assert "evaluated" in j and isinstance(j["evaluated"], int)
        assert "performance" in j
        perf = j["performance"]
        assert "hit_rate" in perf and "total" in perf and "by_direction" in perf

    def test_evaluate_all_idempotent(self, api_client):
        r1 = api_client.post(f"{API}/history/evaluate-all", timeout=LONG)
        assert r1.status_code == 200
        # Perf snapshot after first eval
        p1 = api_client.get(f"{API}/performance", timeout=15).json()
        # Second run should not crash and totals must be stable (wins/losses can only grow, not decrease)
        r2 = api_client.post(f"{API}/history/evaluate-all", timeout=LONG)
        assert r2.status_code == 200
        p2 = api_client.get(f"{API}/performance", timeout=15).json()
        assert p2["total"] == p1["total"]
        assert p2["wins"] >= p1["wins"]
        assert p2["losses"] >= p1["losses"]


# ---------------- Analysis outcome default + history contains outcome ----------------
class TestAnalysisOutcomeField:
    def test_new_analysis_has_pending_outcome(self, api_client):
        r = api_client.post(f"{API}/analysis", json={"symbol": "BTCUSDT", "timeframe": "4H"}, timeout=LONG)
        assert r.status_code == 200, r.text
        a = r.json()
        assert "outcome" in a
        assert a["outcome"].get("status") == "pending"
        return a["id"]

    def test_history_items_have_outcome(self, api_client):
        r = api_client.get(f"{API}/history", timeout=20)
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) > 0
        for it in items[:10]:
            assert "outcome" in it, f"item {it.get('id')} missing outcome"
            status = (it["outcome"] or {}).get("status")
            assert status in ("pending", "win", "loss", "neutral", "unresolvable")


# ---------------- Unit: outcome engine correctness ----------------
class TestOutcomeEngineUnit:
    def _run(self, direction, target, invalid, candles):
        from market_ai.engines import outcome as oe
        analysis = {"direction": direction, "zones": {"target_1": target, "invalidation": invalid}}
        return oe.evaluate(analysis, candles)

    def test_bullish_win(self):
        # Bullish: target above, invalid below. First candle sweeps up to target.
        candles = [
            {"time": 1, "open": 100, "high": 111, "low": 99, "close": 110, "volume": 1},
        ]
        out = self._run("bullish", 110, 95, candles)
        assert out["status"] == "win"
        assert out["bars_to_resolve"] == 1

    def test_bullish_loss(self):
        # First candle drops to invalidation before touching target.
        candles = [
            {"time": 1, "open": 100, "high": 104, "low": 94, "close": 96, "volume": 1},
        ]
        out = self._run("bullish", 110, 95, candles)
        assert out["status"] == "loss"

    def test_bearish_win(self):
        candles = [
            {"time": 1, "open": 100, "high": 101, "low": 89, "close": 90, "volume": 1},
        ]
        out = self._run("bearish", 90, 105, candles)
        assert out["status"] == "win"

    def test_bearish_loss(self):
        candles = [
            {"time": 1, "open": 100, "high": 106, "low": 99, "close": 105, "volume": 1},
        ]
        out = self._run("bearish", 90, 105, candles)
        assert out["status"] == "loss"

    def test_neutral_not_scored(self):
        out = self._run("neutral", 110, 95, [])
        assert out["status"] == "neutral"

    def test_both_in_same_candle_conservative_loss(self):
        # Bullish: high hits target AND low hits invalid same candle -> loss (conservative).
        candles = [{"time": 1, "open": 100, "high": 111, "low": 94, "close": 100, "volume": 1}]
        out = self._run("bullish", 110, 95, candles)
        assert out["status"] == "loss"

    def test_pending_when_no_touch(self):
        candles = [{"time": 1, "open": 100, "high": 104, "low": 96, "close": 102, "volume": 1}]
        out = self._run("bullish", 110, 95, candles)
        assert out["status"] == "pending"

    def test_summarize_hit_rate(self):
        from market_ai.engines import outcome as oe
        outs = [
            {"status": "win"}, {"status": "win"}, {"status": "loss"},
            {"status": "pending"}, {"status": "neutral"},
        ]
        s = oe.summarize(outs)
        assert s["total"] == 5
        assert s["wins"] == 2 and s["losses"] == 1
        assert s["resolved"] == 3
        assert s["hit_rate"] == round(2 / 3 * 100, 1)
