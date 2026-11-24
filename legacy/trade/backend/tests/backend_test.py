"""Backend API integration tests for Market AI.

Covers: /api/config, /api/markets, /api/markets/{symbol}, /api/markets/{symbol}/technical,
/api/analysis (with and without image), /api/history, /api/news.
"""
import base64
import io
import os

import pytest
import requests
from PIL import Image, ImageDraw

# Env-driven public backend URL (Expo public var used by RN frontend)
BASE_URL = (
    os.environ.get("EXPO_BACKEND_URL")
    or os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or ""
).rstrip("/")

API = f"{BASE_URL}/api"
LONG = 90  # analysis endpoint can be slow (AI call)


@pytest.fixture(scope="session")
def api_client():
    if not BASE_URL:
        pytest.skip("Set EXPO_BACKEND_URL to an isolated V1 test server")
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def chart_like_image_b64() -> str:
    """A synthetic candlestick-like PNG (real features: bars, edges, colors)."""
    W, H = 480, 300
    img = Image.new("RGB", (W, H), (16, 20, 28))
    d = ImageDraw.Draw(img)
    # grid
    for x in range(0, W, 40):
        d.line([(x, 0), (x, H)], fill=(40, 44, 52))
    for y in range(0, H, 30):
        d.line([(0, y), (W, y)], fill=(40, 44, 52))
    # candlesticks (up/down)
    import random
    random.seed(7)
    y_center = H // 2
    for i, x in enumerate(range(20, W - 20, 20)):
        up = random.random() > 0.5
        body_h = random.randint(6, 30)
        wick_h = body_h + random.randint(4, 20)
        color = (46, 189, 133) if up else (232, 76, 76)
        d.line([(x + 4, y_center - wick_h // 2), (x + 4, y_center + wick_h // 2)], fill=color)
        d.rectangle([(x, y_center - body_h // 2), (x + 8, y_center + body_h // 2)], fill=color)
        y_center += random.randint(-8, 8)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ---------------------------- Meta / Config --------------------------------
class TestMeta:
    def test_config(self, api_client):
        r = api_client.get(f"{API}/config", timeout=15)
        assert r.status_code == 200, r.text
        j = r.json()
        p = j["providers"]
        assert p["market_data"]["name"] == "binance" and p["market_data"]["available"] is True
        assert p["ai"]["model"] == "gpt-5.6-terra" and p["ai"]["available"] is True
        assert p["news"]["available"] is False
        assets = j["assets"]
        symbols = {a["symbol"] for a in assets}
        assert symbols >= {"BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT"}
        assert "4H" in j["timeframes"]


# ---------------------------- Markets --------------------------------------
class TestMarkets:
    def test_markets_list(self, api_client):
        r = api_client.get(f"{API}/markets", timeout=20)
        assert r.status_code == 200, r.text
        markets = r.json()["markets"]
        assert len(markets) == 7
        for m in markets:
            assert "symbol" in m and "available" in m
            if m["available"]:
                assert isinstance(m.get("price"), (int, float))
                assert "change_24h_pct" in m

    def test_market_detail_btc(self, api_client):
        r = api_client.get(f"{API}/markets/BTCUSDT", params={"timeframe": "4H"}, timeout=20)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["symbol"] == "BTCUSDT"
        assert isinstance(j.get("price"), (int, float)) and j["price"] > 0
        assert isinstance(j["sparkline"], list) and len(j["sparkline"]) > 20

    def test_market_detail_unsupported(self, api_client):
        r = api_client.get(f"{API}/markets/FOOBAR", timeout=10)
        assert r.status_code == 404

    def test_technical_btc(self, api_client):
        r = api_client.get(f"{API}/markets/BTCUSDT/technical", params={"timeframe": "4H"}, timeout=25)
        assert r.status_code == 200, r.text
        j = r.json()
        assert "technical" in j
        assert "indicators" in j["technical"]
        for k in ("ema20", "ema50", "rsi14"):
            assert k in j["technical"]["indicators"]
        assert isinstance(j["candlestick_patterns"], list)
        assert isinstance(j["chart_patterns"], list)
        assert "scores" in j and "direction" in j and "confidence" in j
        assert j["direction"] in ("bullish", "bearish", "neutral")
        assert 0 <= j["confidence"] <= 100


# ---------------------------- News -----------------------------------------
class TestNews:
    def test_news_unavailable(self, api_client):
        r = api_client.get(f"{API}/news", timeout=10)
        assert r.status_code == 200
        j = r.json()
        assert j.get("available") is False
        assert isinstance(j.get("message", ""), str) and len(j.get("message", "")) > 0


# ---------------------------- Analysis + History ---------------------------
@pytest.fixture(scope="session")
def created_analysis(api_client):
    payload = {"symbol": "BTCUSDT", "timeframe": "4H"}
    r = api_client.post(f"{API}/analysis", json=payload, timeout=LONG)
    assert r.status_code == 200, r.text
    return r.json()


class TestAnalysis:
    def test_analysis_no_image(self, created_analysis):
        a = created_analysis
        assert a["symbol"] == "BTCUSDT"
        assert a["direction"] in ("bullish", "bearish", "neutral")
        assert 0 <= a["confidence"] <= 100
        assert isinstance(a["scores"], dict) and a["scores"]
        assert isinstance(a["zones"], dict)
        assert isinstance(a["scenarios"], dict) and set(a["scenarios"].keys()) >= {"bullish", "bearish", "neutral"}
        assert isinstance(a["supporting_reasons"], list) and len(a["supporting_reasons"]) >= 1
        assert isinstance(a["contradicting_reasons"], list) and len(a["contradicting_reasons"]) >= 1
        assert isinstance(a["summary"], str) and len(a["summary"]) > 10
        assert a["ai_available"] is True
        assert a.get("id")
        assert a.get("has_image") is False
        # No mongo _id leakage
        assert "_id" not in a

    def test_analysis_with_image(self, api_client, chart_like_image_b64):
        payload = {"symbol": "ETHUSDT", "timeframe": "1H", "image_base64": chart_like_image_b64}
        r = api_client.post(f"{API}/analysis", json=payload, timeout=LONG)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["has_image"] is True
        assert isinstance(j["vision"], dict) and j["vision"]  # must be populated
        # Vision object should have expected keys OR an error field
        if j["vision"].get("available") is False:
            pytest.fail(f"Vision unavailable: {j['vision'].get('error')}")
        # Common expected keys from ai_provider prompt
        expected_any = {"trend", "chart_patterns", "candlestick_structures", "support_resistance", "notes"}
        assert expected_any & set(j["vision"].keys()), f"Vision keys unexpected: {list(j['vision'].keys())}"

    def test_analysis_unsupported_symbol(self, api_client):
        r = api_client.post(f"{API}/analysis", json={"symbol": "FOOBAR", "timeframe": "4H"}, timeout=15)
        assert r.status_code == 400


class TestHistory:
    def test_history_lists_created(self, api_client, created_analysis):
        r = api_client.get(f"{API}/history", timeout=15)
        assert r.status_code == 200
        items = r.json()["items"]
        ids = {i["id"] for i in items}
        assert created_analysis["id"] in ids

    def test_history_detail(self, api_client, created_analysis):
        r = api_client.get(f"{API}/history/{created_analysis['id']}", timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert j["id"] == created_analysis["id"]
        assert "_id" not in j

    def test_history_delete(self, api_client, created_analysis):
        r = api_client.delete(f"{API}/history/{created_analysis['id']}", timeout=15)
        assert r.status_code == 200
        assert r.json().get("deleted") == 1
        # verify gone
        g = api_client.get(f"{API}/history/{created_analysis['id']}", timeout=10)
        assert g.status_code == 404

    def test_history_detail_invalid_id(self, api_client):
        r = api_client.get(f"{API}/history/not-a-valid-oid", timeout=10)
        assert r.status_code == 400
