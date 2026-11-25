import httpx
import pytest
from starlette.testclient import TestClient

from tests.app_helpers import NOW, build, started
from tradebot.api.auth import create_pair_code, issue_token
from tradebot.api.server import create_app
from tradebot.store.repo import Trade


def client_for(app, token=None):
    api = create_app(app.bot, clock=lambda: app.clock["now"])
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://bot", headers=headers)


async def authed(tmp_path, **kwargs):
    app = await started(tmp_path, **kwargs)
    token = issue_token(app.repo, now=app.clock["now"])
    return app, client_for(app, token)


async def open_trade(app):
    await app.bot.on_bar_close()
    await app.fake.flush()
    return app.repo.open_trades("bot")[0]


async def test_health_is_public_and_minimal(tmp_path):
    app = await started(tmp_path)
    app.advance(30)
    await app.bot.heartbeat()
    async with client_for(app) as http:
        response = await http.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "last_scan_at": None, "heartbeat_at": NOW + 30,
                               "stream_connected": True, "halted": False, "last_scan": None, "tick_errors": 0,
                               "tick_error": None, "tick_acks": 0, "quoted_now": 1}


async def test_health_reports_last_scan_counts_without_account_data(tmp_path):
    """Dagitimdan sonra taramanin calistigi buradan dogrulanir; herkese acik oldugu icin yalnizca sayilar."""
    app = await started(tmp_path)
    await app.bot.on_bar_close()
    async with client_for(app) as http:
        body = (await http.get("/health")).json()
    assert body["last_scan"] == {"at": NOW, "scanned": 4, "closed": 0, "errors": 0, "skipped": None,
                                 "quoted": 1, "candle_retries": 0}  # yalnizca XAUUSD icin fiyat akisi var
    assert body["last_scan_at"] == NOW
    text = str(body)
    assert "10000" not in text and "XAUUSD" not in text and "candidates" not in text and "opened" not in text

    app.streams[0].go_down()
    await app.bot.on_bar_close()
    async with client_for(app) as http:
        body = (await http.get("/health")).json()
    assert body["stream_connected"] is False and body["last_scan"]["skipped"] == "stream_down"


async def test_requires_token(tmp_path):
    app = await started(tmp_path)
    protected = [("GET", "/status"), ("GET", "/positions"), ("GET", "/settings"), ("GET", "/events"),
                 ("GET", "/reports"), ("POST", "/bot/stop"), ("POST", "/bot/resume"), ("POST", "/bot/close-all"),
                 ("POST", "/trades"), ("PUT", "/settings"), ("PATCH", "/positions/1"), ("POST", "/positions/1/close"),
                 ("POST", "/devices")]
    async with client_for(app) as http:
        for method, path in protected:
            assert (await http.request(method, path, json={})).status_code == 401, path
    async with client_for(app, "yanlis-token") as http:
        assert (await http.get("/status")).status_code == 401
    assert app.fake.calls("POST") == [] and app.fake.calls("DELETE") == []


async def test_pair_code_single_use(tmp_path):
    app = await started(tmp_path)
    code = create_pair_code(app.repo, now=app.clock["now"])
    assert len(code) == 6 and code.isdigit()
    async with client_for(app) as http:
        first = await http.post("/pair", json={"code": code})
        second = await http.post("/pair", json={"code": code})
        assert first.status_code == 200 and second.status_code == 401
        token = first.json()["token"]
        assert len(token) >= 32
        ok = await http.get("/status", headers={"Authorization": f"Bearer {token}"})
        assert ok.status_code == 200
    stored = [row[0] for row in app.repo.conn.execute("SELECT token_hash FROM api_tokens")]
    assert token not in stored and len(stored[0]) == 64  # yalnizca hash saklanir


async def test_pair_code_expires_and_locks_after_failures(tmp_path):
    app = await started(tmp_path)
    code = create_pair_code(app.repo, now=app.clock["now"])
    app.advance(601)
    async with client_for(app) as http:
        assert (await http.post("/pair", json={"code": code})).status_code == 401
        fresh = create_pair_code(app.repo, now=app.clock["now"])
        wrong = "000000" if fresh != "000000" else "111111"
        for _ in range(5):
            assert (await http.post("/pair", json={"code": wrong})).status_code == 401
        assert (await http.post("/pair", json={"code": fresh})).status_code == 401  # deneme siniri: kod iptal
        assert (await http.post("/pair", json={"code": "12"})).status_code == 422


async def test_status_and_positions(tmp_path):
    app, http = await authed(tmp_path)
    trade = await open_trade(app)
    await app.fake.set_price("XAUUSD", trade.entry + 1.0, trade.entry + 1.2)
    async with http:
        status = (await http.get("/status")).json()
        positions = (await http.get("/positions")).json()
    assert status["equity"] is not None and status["open_bot"] == 1 and status["currency"] == "USD"
    assert status["pnl_today"]["bot"] == pytest.approx(trade.volume * 100, abs=0.01)
    assert status["pnl_today"]["manual"] == 0 and status["dry_run"] is False
    assert status["server_time"] >= NOW  # uygulama kalp atisi bayatligini buna gore olcer
    position = positions["positions"][0]
    assert position["position_id"] == trade.position_id and position["origin"] == "bot"
    assert position["unrealized_pnl"] == pytest.approx(trade.volume * 100, abs=0.01)
    assert position["r_multiple"] == pytest.approx(1.0 / trade.initial_risk_r_price, rel=1e-6)
    assert position["price"] == trade.entry + 1.0 and position["manage"] is True


async def test_patch_position_marks_user_override_and_manage_flag(tmp_path):
    app, http = await authed(tmp_path)
    trade = await open_trade(app)
    async with http:
        response = await http.patch(f"/positions/{trade.position_id}", json={"sl": trade.sl - 1.0, "manage": False})
        assert response.status_code == 200
        await app.fake.flush()
        changed = app.repo.get_trade(trade.position_id)
        assert changed.sl == pytest.approx(trade.sl - 1.0) and changed.user_sl_override is True
        assert changed.manage is False
        assert (await http.patch("/positions/404", json={"sl": 1.0})).status_code == 404
        assert (await http.patch(f"/positions/{trade.position_id}", json={"sl": -1})).status_code == 422
        assert (await http.patch(f"/positions/{trade.position_id}", json={})).status_code == 422


async def test_close_position_full_and_partial(tmp_path):
    app, http = await authed(tmp_path)
    trade = await open_trade(app)
    async with http:
        partial = await http.post(f"/positions/{trade.position_id}/close", json={"volume": 0.01})
        assert partial.status_code == 200
        await app.fake.flush()
        assert app.repo.get_trade(trade.position_id).volume == pytest.approx(trade.volume - 0.01)
        full = await http.post(f"/positions/{trade.position_id}/close", json={})
        assert full.status_code == 200
        await app.fake.flush()
        assert not app.repo.get_trade(trade.position_id).is_open
        assert (await http.post(f"/positions/{trade.position_id}/close", json={})).status_code == 404


async def test_manual_trade_origin_manual(tmp_path):
    app, http = await authed(tmp_path)
    async with http:
        sized = await http.post("/trades", json={"symbol": "XAUUSD", "side": "BUY", "sl_distance": 5.0})
        assert sized.status_code == 200, sized.text
        await app.fake.flush()
        auto = app.repo.open_trades("manual")[0]
        # lot verilmedi: gercek equity'nin %0.5'i riske gore (10000 * 0.005 / (5 * 100)) = 0.10
        assert auto.volume == pytest.approx(0.10) and auto.side == "BUY"
        assert auto.sl == pytest.approx(auto.entry - 5.0) and auto.tp2 is None

        response = await http.post("/trades", json={"symbol": "XAUUSD", "side": "SELL", "sl_distance": 5.0,
                                                     "tp_distance": 10.0, "lots": 0.03})
        assert response.status_code == 200, response.text
        await app.fake.flush()
        trades = app.repo.open_trades("manual")
        assert len(trades) == 2 and app.repo.open_trades("bot") == []
        trade = trades[1]
        assert (trade.side, trade.volume) == ("SELL", 0.03)
        assert trade.sl == pytest.approx(trade.entry + 5.0) and trade.tp2 == pytest.approx(trade.entry - 10.0)
        assert all("stop_loss_price" in call[2] for call in app.fake.calls("POST", "/positions"))

        assert (await http.post("/trades", json={"symbol": "NOPE", "side": "BUY", "sl_distance": 5})).status_code == 404
        assert (await http.post("/trades", json={"symbol": "XAUUSD", "side": "BUY"})).status_code == 422
        assert (await http.post("/trades", json={"symbol": "XAUUSD", "side": "BUY", "sl_distance": 0})).status_code == 422
        no_quote = await http.post("/trades", json={"symbol": "EURUSD", "side": "BUY", "sl_distance": 0.001})
        assert no_quote.status_code == 409


async def test_manual_trades_do_not_count_against_bot_limits(tmp_path):
    app, http = await authed(tmp_path)
    async with http:
        for _ in range(4):
            await http.post("/trades", json={"symbol": "XAUUSD", "side": "BUY", "sl_distance": 5.0, "lots": 0.01})
        await app.fake.flush()
    assert len(app.repo.open_trades("manual")) == 4
    summary = await app.bot.on_bar_close()
    assert summary.opened == 1  # bot kendi limitine gore hala islem acabiliyor


async def test_stop_and_resume(tmp_path):
    app, http = await authed(tmp_path)
    async with http:
        assert (await http.post("/bot/stop")).json()["stopped"] is True
        assert (await app.bot.on_bar_close()).skipped == "stopped"
        assert (await http.post("/bot/resume", json={})).json()["stopped"] is False
        assert (await app.bot.on_bar_close()).opened == 1
    assert "bot_stopped" in app.kinds() and "bot_resumed" in app.kinds()


async def test_resume_after_halt_requires_confirm(tmp_path):
    app, http = await authed(tmp_path)
    app.advance(60)
    app.repo.upsert_trade(Trade(position_id="9", origin="bot", symbol="EURUSD", side="BUY", volume=0.0, entry=1.1,
                                opened_at=NOW + 10, closed_at=NOW + 60))
    app.repo.add_realized("9", "deal-loss", NOW + 60, -2600.0)
    await app.bot.on_bar_close()
    assert app.repo.bot_state().halted is True
    async with http:
        refused = await http.post("/bot/resume", json={})
        assert refused.status_code == 409 and app.repo.bot_state().halted is True
        assert (await http.post("/bot/resume", json={"confirm_halt": False})).status_code == 409
        accepted = await http.post("/bot/resume", json={"confirm_halt": True})
        assert accepted.status_code == 200
    state = app.repo.bot_state()
    assert state.halted is False and state.halt_reason is None
    # Devam, olcum tabanini sifirlar: bot ayni kayip yuzunden hemen yeniden durmaz
    assert state.start_capital == app.bot.account.equity and state.start_at == NOW + 60
    app.advance(1)
    await app.bot.heartbeat()
    assert app.repo.bot_state().halted is False


async def test_close_all_requires_exact_confirm(tmp_path):
    app, http = await authed(tmp_path)
    await open_trade(app)
    async with http:
        await http.post("/trades", json={"symbol": "XAUUSD", "side": "SELL", "sl_distance": 5.0, "lots": 0.01})
        await app.fake.flush()
        for body in ({}, {"confirm": "close-all"}, {"confirm": "CLOSE"}, {"confirm": True}):
            assert (await http.post("/bot/close-all", json=body)).status_code in (409, 422)
        assert len(app.repo.open_trades()) == 2 and app.fake.calls("DELETE") == []
        done = await http.post("/bot/close-all", json={"confirm": "CLOSE-ALL"})
        assert done.status_code == 200 and done.json()["requested"] == 2
        await app.fake.flush()
    assert app.repo.open_trades() == []
    assert app.repo.bot_state().stopped is True  # hepsini kapat, botu da durdurur


async def test_put_settings_out_of_range_422(tmp_path):
    app, http = await authed(tmp_path)
    async with http:
        current = (await http.get("/settings")).json()
        assert current["risk"]["risk_pct"] == 0.5 and current["dry_run"] is False
        for path, value in (("risk_pct", 1.5), ("risk_pct", 0.1), ("max_open_bot", 9), ("daily_loss_pct", 50),
                            ("total_loss_pct", 5), ("per_symbol", 2)):
            body = {**current, "risk": {**current["risk"], path: value}}
            assert (await http.put("/settings", json=body)).status_code == 422, (path, value)
        assert (await http.put("/settings", json={**current, "bilinmeyen": 1})).status_code == 422
        assert app.repo.get_bot_settings().risk.risk_pct == 0.5

        body = {**current, "risk": {**current["risk"], "risk_pct": 1.0, "max_open_bot": 5},
                "enabled_symbols": ["XAUUSD", "BTCUSD"], "dry_run": True}
        saved = await http.put("/settings", json=body)
        assert saved.status_code == 200
    settings = app.repo.get_bot_settings()
    assert settings.risk.risk_pct == 1.0 and settings.enabled_symbols == {"XAUUSD", "BTCUSD"}
    assert settings.dry_run is True and "settings_changed" in app.kinds()


async def test_reports_split_bot_manual(tmp_path):
    app, http = await authed(tmp_path)
    day = NOW - 3 * 86400
    rows = [("1", "bot", "XAUUSD", "fx_trend_momentum_v6", day, 30.0),
            ("2", "bot", "XAUUSD", "fx_trend_momentum_v6", day + 3600, -10.0),
            ("3", "bot", "EURUSD", "fx_range_reversion_v6", day + 86400, -15.0),
            ("4", "manual", "BTCUSD", None, day + 86400, 100.0)]
    for position_id, origin, symbol, strategy, at, pnl in rows:
        app.repo.upsert_trade(Trade(position_id=position_id, origin=origin, symbol=symbol, side="BUY", volume=0.0,
                                    entry=1.0, strategy_id=strategy, opened_at=at - 60, closed_at=at))
        app.repo.add_realized(position_id, "d" + position_id, at, pnl)
    async with http:
        report = (await http.get("/reports", params={"period": "day"})).json()
        assert (await http.get("/reports", params={"period": "year"})).status_code == 422
        weekly = (await http.get("/reports", params={"period": "week"})).json()
    assert report["totals"]["bot"] == {"pnl": 5.0, "trades": 3, "wins": 1, "win_rate": pytest.approx(1 / 3)}
    assert report["totals"]["manual"]["pnl"] == 100.0 and report["totals"]["manual"]["win_rate"] == 1.0
    assert report["totals"]["all"]["pnl"] == 105.0 and report["totals"]["all"]["trades"] == 4
    assert [p["pnl"] for p in report["periods"]["bot"]] == [20.0, -15.0]
    assert [p["pnl"] for p in report["periods"]["all"]] == [20.0, 85.0]
    assert report["max_drawdown"]["bot"] == pytest.approx(25.0)  # +30 tepe -> +5
    assert report["by_strategy"]["fx_trend_momentum_v6"] == {"pnl": 20.0, "trades": 2, "wins": 1}
    assert report["by_symbol"]["EURUSD"]["pnl"] == -15.0 and report["by_symbol"]["BTCUSD"]["trades"] == 1
    assert len(report["history"]) == 4 and report["history"][0]["position_id"] in ("3", "4")
    assert len(weekly["periods"]["all"]) >= 1


async def test_events_paging(tmp_path):
    app, http = await authed(tmp_path)
    await open_trade(app)
    async with http:
        events = (await http.get("/events")).json()["events"]
        assert [e["kind"] for e in events][-1] in ("scan", "trade_opened")
        last = events[-1]["id"]
        assert (await http.get("/events", params={"after": last})).json()["events"] == []
        app.repo.add_event("info", "x", "y")
        assert [e["kind"] for e in (await http.get("/events", params={"after": last})).json()["events"]] == ["x"]


async def test_events_newest_first_for_app_start(tmp_path):
    """Uygulama ilk acilista en yeni olaylari ister; eski 200 olayi sayfa sayfa gezmek zorunda kalmaz."""
    app, http = await authed(tmp_path)
    for i in range(5):
        app.repo.add_event("info", f"k{i}", "m")
    async with http:
        newest = (await http.get("/events", params={"newest": "true", "limit": 2})).json()["events"]
        assert [e["kind"] for e in newest] == ["k4", "k3"]
        oldest = (await http.get("/events", params={"limit": 2})).json()["events"]
        assert oldest[0]["id"] < oldest[1]["id"] < newest[1]["id"]


async def test_devices_register(tmp_path):
    app, http = await authed(tmp_path)
    async with http:
        ok = await http.post("/devices", json={"expo_token": "ExponentPushToken[abcDEF123_-]"})
        assert ok.status_code == 200
        await http.post("/devices", json={"expo_token": "ExponentPushToken[abcDEF123_-]"})
        assert (await http.post("/devices", json={"expo_token": "https://evil.test/hook"})).status_code == 422
    assert app.repo.devices() == ["ExponentPushToken[abcDEF123_-]"]


def test_websocket_stream_requires_token_and_pushes_status(tmp_path):
    app = build(tmp_path)
    token = issue_token(app.repo, now=NOW)
    api = create_app(app.bot, clock=lambda: app.clock["now"], stream_interval=0.01)
    with TestClient(api) as client:
        with pytest.raises(Exception):
            with client.websocket_connect("/stream"):
                pass
        with pytest.raises(Exception):
            with client.websocket_connect("/stream?token=yanlis"):
                pass
        with client.websocket_connect(f"/stream?token={token}") as socket:
            first = socket.receive_json()
            assert first["type"] == "status" and first["status"]["halted"] is False
            app.repo.add_event("info", "trade_opened", "test")
            seen = [socket.receive_json() for _ in range(6)]
            assert any(m["type"] == "event" and m["event"]["kind"] == "trade_opened" for m in seen)


async def test_put_settings_validates_symbols_thresholds_and_manage_switches(tmp_path):
    app, http = await authed(tmp_path)
    async with http:
        current = (await http.get("/settings")).json()
        assert current["manage"]["be_enabled"] is current["manage"]["partial_enabled"] is True
        assert current["manage"]["trail_enabled"] is True
        unknown = await http.put("/settings", json={**current, "enabled_symbols": ["XAUUSD", "YOKYOK"]})
        assert unknown.status_code == 422 and "YOKYOK" in unknown.json()["detail"]
        empty = await http.put("/settings", json={**current, "enabled_symbols": []})
        assert empty.status_code == 422 and "en az bir sembol" in empty.json()["detail"]
        # Esik sirasi: en dusuk <= orta <= yuksek
        for fusion in ({"min_score": 70, "mid_score": 60}, {"mid_score": 90, "high_score": 80}):
            bad = await http.put("/settings", json={**current, "fusion": {**current["fusion"], **fusion}})
            assert bad.status_code == 422, fusion
        assert app.repo.get_bot_settings().enabled_symbols is None

        body = {**current, "enabled_symbols": ["XAUUSD"], "manage": {**current["manage"], "trail_enabled": False},
                "fusion": {**current["fusion"], "mid_score": 55, "high_score": 85}}
        assert (await http.put("/settings", json=body)).status_code == 200
        # Listede kalmis, artik evrende olmayan eski sembol baska ayarin kaydini engellemez.
        stale = app.repo.get_bot_settings()
        stale.enabled_symbols = {"XAUUSD", "ESKISYM"}
        app.repo.set_bot_settings(stale)
        again = (await http.get("/settings")).json()
        assert (await http.put("/settings", json={**again, "news": {**again["news"], "window_minutes": 45}})
                ).status_code == 200
    saved = app.repo.get_bot_settings()
    assert saved.manage.trail_enabled is False and saved.manage.be_enabled is True
    assert saved.fusion.mid_score == 55 and saved.fusion.high_score == 85 and saved.news.window_minutes == 45
