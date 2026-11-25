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
        # Kucuk hesap: onizleme reddetmez, en kucuk lotu ve gercek zarari UYARIYLA gosterir.
        tiny = await http.post("/trades/preview", json={"symbol": "XAUUSD", "side": "BUY", "sl_distance": 5.0})
        assert tiny.status_code == 200
        shown = tiny.json()
        assert shown["lots"] == shown["volume_min"] and shown["suggested_lots"] < shown["volume_min"]
        assert any("en küçük lot" in w for w in shown["warnings"]) and any("üstünde" in w for w in shown["warnings"])
        assert shown["loss_pct"] > shown["settings_risk_pct"]
        # Emir ise lot acikca verilmeden gonderilmez; kullanici onizlenen lotu onaylayip gonderirse acilir.
        blind = await http.post("/trades", json={"symbol": "XAUUSD", "side": "BUY", "sl_distance": 5.0})
        assert blind.status_code == 422 and "açıkça" in blind.json()["detail"]
        assert app.fake.calls("POST", "/positions") == []
        below = await http.post("/trades/preview", json={"symbol": "XAUUSD", "side": "BUY", "sl_distance": 5.0,
                                                        "lots": shown["volume_min"] / 10})
        assert below.status_code == 422
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


async def test_resolve_reports_an_existing_order_without_sending_anything(tmp_path):
    app = await started(tmp_path)
    payload = {"symbol": "XAUUSD", "side": "BUY", "sl_distance": 5.0, "client_id": "sonuc-sor-0001"}
    async with client(app) as http:
        sent = (await http.post("/trades", json=payload)).json()
        opened = len(app.fake.calls("POST", "/positions"))
        result = await http.post("/trades/sonuc-sor-0001/resolve", json={})
        assert result.status_code == 200
        assert result.json() == {"found": True, "state": sent["state"], "lots": sent["lots"]}
        assert len(app.fake.calls("POST", "/positions")) == opened == 1  # sormak emir acmaz
        # Bulunan emir gecersiz kilinmaz: ayni kimlikle yeniden gelen istek hala "duplicate" doner.
        again = await http.post("/trades", json=payload)
        assert again.status_code == 200 and again.json()["duplicate"] is True
    assert len(app.fake.calls("POST", "/positions")) == 1


async def test_resolve_voids_an_order_that_never_arrived_so_a_late_request_cannot_open_it(tmp_path):
    app = await started(tmp_path)
    payload = {"symbol": "XAUUSD", "side": "BUY", "sl_distance": 5.0, "client_id": "yolda-kaldi-0001"}
    async with client(app) as http:
        result = await http.post("/trades/yolda-kaldi-0001/resolve", json={})
        assert result.status_code == 200 and result.json() == {"found": False, "state": None, "lots": None}
        late = await http.post("/trades", json=payload)  # yolda kalmis istek sonradan ulasti
        assert late.status_code == 409 and "iptal" in late.json()["detail"]
        assert app.fake.calls("POST", "/positions") == []
        assert (await http.post("/trades/yolda-kaldi-0001/resolve", json={})).json()["found"] is False  # yinelenebilir
        fresh = await http.post("/trades", json={**payload, "client_id": "yeni-emir-0002"})  # yeni kimlik calisir
        assert fresh.status_code == 200
        assert (await http.post("/trades/kisa/resolve", json={})).status_code == 422
    async with client(app, authed=False) as http:
        assert (await http.post("/trades/yolda-kaldi-0001/resolve", json={})).status_code in (401, 403)
    assert len(app.fake.calls("POST", "/positions")) == 1


async def test_lot_must_be_on_the_step_grid_and_risk_pct_cannot_silence_the_warning(tmp_path):
    """Inceleme I3: adim disi lot gonderimde yukari yuvarlanabilirdi; istekteki risk_pct uyariyi susturabilirdi."""
    app = await started(tmp_path)
    base = {"symbol": "XAUUSD", "side": "BUY", "sl_distance": 5.0}
    async with client(app) as http:
        assert (await http.post("/trades/preview", json={**base, "lots": 0.015})).status_code == 422
        off_grid = await http.post("/trades", json={**base, "lots": 0.015})
        assert off_grid.status_code == 422 and "adım" in off_grid.json()["detail"]
        assert app.fake.calls("POST", "/positions") == []
        double = (await http.post("/trades/preview", json={**base, "risk_pct": 2.0})).json()
        assert double["risk_pct"] == 2.0 and double["settings_risk_pct"] == 0.5
        assert any("risk sınırınızın (%0.5) üstünde" in w for w in double["warnings"])
        sent = await http.post("/trades", json={**base, "lots": 0.02})
        assert sent.status_code == 200 and sent.json()["lots"] == 0.02
    assert float(app.fake.calls("POST", "/positions")[0][2]["volume"]) == 0.02
