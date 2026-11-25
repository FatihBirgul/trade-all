"""Elle islem onizlemesi (emir gondermez) ve sembol listesi."""
import httpx
import pytest

from tests.app_helpers import NOW, SATURDAY, started
from tradebot.api.auth import issue_token
from tradebot.api.server import create_app


def client(app, authed=True):
    headers = {"Authorization": f"Bearer {issue_token(app.repo, now=app.clock['now'])}"} if authed else {}
    api = create_app(app.bot, clock=lambda: app.clock["now"])
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://bot", headers=headers)


async def test_preview_suggests_a_lot_within_the_risk_budget_and_sends_nothing(tmp_path):
    app = await started(tmp_path)
    before = len(app.fake.requests)
    async with client(app) as http:
        response = await http.post("/trades/preview", json={"symbol": "XAUUSD", "side": "BUY", "sl_distance": 5.0,
                                                           "tp_distance": 10.0})
    assert response.status_code == 200
    body = response.json()
    quote = app.bot.quotes.quote("XAUUSD")
    assert body["entry"] == quote["ask"] and body["sl"] == pytest.approx(quote["ask"] - 5.0)
    assert body["tp"] == pytest.approx(quote["ask"] + 10.0) and body["rr"] == pytest.approx(2.0)
    assert body["lots"] == body["suggested_lots"] > 0
    assert body["loss"] <= 10_000 * 0.5 / 100 + 1e-9 and body["loss"] > 10_000 * 0.5 / 100 * 0.9
    assert body["loss_pct"] == pytest.approx(body["loss"] / 10_000 * 100) and body["risk_pct"] == 0.5
    assert body["profit"] == pytest.approx(2 * body["loss"], rel=0.01) and body["currency"] == "USD"
    assert body["warnings"] == []
    assert len(app.fake.requests) == before  # broker'a hicbir istek gitmedi
    assert app.repo.orders_in(("PENDING", "ACKED", "UNKNOWN", "FILLED")) == []


async def test_preview_matches_the_order_that_is_then_sent(tmp_path):
    app = await started(tmp_path)
    payload = {"symbol": "XAUUSD", "side": "SELL", "sl_distance": 4.0, "tp_distance": 8.0}
    async with client(app) as http:
        preview = (await http.post("/trades/preview", json=payload)).json()
        sent = (await http.post("/trades", json={**payload, "client_id": "onizleme-0001"})).json()
    assert sent["lots"] == preview["lots"] and sent["sl"] == pytest.approx(preview["sl"])
    assert sent["tp"] == pytest.approx(preview["tp"])


async def test_preview_warns_instead_of_hiding_risk(tmp_path):
    app = await started(tmp_path)
    async with client(app) as http:
        big = (await http.post("/trades/preview", json={"symbol": "XAUUSD", "side": "BUY", "sl_distance": 5.0,
                                                      "lots": 1.0})).json()
        assert big["lots"] == 1.0 and big["loss"] > 10_000 * 0.5 / 100
        assert any("risk sınırınızın" in w for w in big["warnings"]) and any("Kâr al" in w for w in big["warnings"])
        poor = (await http.post("/trades/preview", json={"symbol": "XAUUSD", "side": "BUY", "sl_distance": 5.0,
                                                       "tp_distance": 2.0})).json()
        assert any("R/R" in w for w in poor["warnings"])
        tight = (await http.post("/trades/preview", json={"symbol": "XAUUSD", "side": "BUY", "sl_distance": 0.3,
                                                        "tp_distance": 1.0})).json()
        assert any("alış-satış farkına" in w for w in tight["warnings"])
        smaller = (await http.post("/trades/preview", json={"symbol": "XAUUSD", "side": "BUY", "sl_distance": 5.0,
                                                          "risk_pct": 0.25})).json()
        assert smaller["suggested_lots"] < big["suggested_lots"] and smaller["risk_pct"] == 0.25


async def test_preview_refuses_what_the_order_would_refuse(tmp_path):
    app = await started(tmp_path, balance=20.0)
    async with client(app) as http:
        tiny = await http.post("/trades/preview", json={"symbol": "XAUUSD", "side": "BUY", "sl_distance": 5.0})
        assert tiny.status_code == 422 and "en küçük lot" in tiny.json()["detail"]
        assert (await http.post("/trades/preview", json={"symbol": "EURUSD", "side": "BUY", "sl_distance": 0.001})
                ).status_code == 409  # fiyat akisi yok
        assert (await http.post("/trades/preview", json={"symbol": "YOKYOK", "side": "BUY", "sl_distance": 1})
                ).status_code == 404
        assert (await http.post("/trades/preview", json={"symbol": "XAUUSD", "side": "BUY", "sl_distance": 0})
                ).status_code == 422
        assert (await http.post("/trades/preview", json={"symbol": "XAUUSD", "side": "BUY", "sl_distance": 5,
                                                         "risk_pct": 5})).status_code == 422
        assert (await http.post("/trades/preview", json={"symbol": "XAUUSD", "side": "BUY", "sl_distance": 99999})
                ).status_code == 422
    async with client(app, authed=False) as http:
        assert (await http.post("/trades/preview", json={"symbol": "XAUUSD", "side": "BUY", "sl_distance": 5})
                ).status_code == 401
        assert (await http.get("/symbols")).status_code == 401


async def test_symbols_lists_the_universe_with_market_state(tmp_path):
    app = await started(tmp_path)
    async with client(app) as http:
        rows = {r["symbol"]: r for r in (await http.get("/symbols")).json()["symbols"]}
    assert set(rows) == {i.symbol for i in app.bot.catalog.universe()}
    gold = rows["XAUUSD"]
    assert gold["open"] is True and gold["quoted"] is True and gold["bid"] is not None and gold["kind"] == "metal"
    assert gold["volume_min"] == 0.01 and gold["volume_step"] == 0.01
    assert rows["EURUSD"]["quoted"] is False and rows["EURUSD"]["bid"] is None  # fiyat akisi yok

    weekend = await started(tmp_path / "w", now=SATURDAY)
    async with client(weekend) as http:
        rows = {r["symbol"]: r for r in (await http.get("/symbols")).json()["symbols"]}
    assert rows["EURUSD"]["open"] is False and rows["BTCUSD"]["open"] is True
