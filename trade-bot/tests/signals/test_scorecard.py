import json

import httpx
import pytest

from tests.app_helpers import NOW, started
from tradebot.api.auth import issue_token
from tradebot.api.server import create_app
from tradebot.config import BotSettings, FusionSettings, strategy_mode
from tradebot.signals.scorecard import scorecard, strategies_to_pause, trade_r
from tradebot.store.repo import Repo, Trade

TREND, RANGE = "fx_trend_momentum_v6", "fx_range_reversion_v6"


def add(repo, n, r, *, strategy=TREND, origin="bot", votes=None, at=1000.0, risk=10.0):
    trade = Trade(position_id=str(n), origin=origin, symbol="EURUSD", side="BUY", volume=0.0, entry=1.1,
                  strategy_id=strategy, risk_amount=risk, opened_at=at - 60, closed_at=at + n,
                  votes_json=json.dumps(votes) if votes else None)
    repo.upsert_trade(trade)
    repo.add_realized(str(n), f"d{n}", at + n, r * (risk or 0.0) if risk else r)


def test_trade_r():
    assert trade_r(Trade(position_id="1", origin="bot", symbol="X", side="BUY", volume=0, entry=1, pnl=-15.0, risk_amount=10.0)) == -1.5
    assert trade_r(Trade(position_id="1", origin="bot", symbol="X", side="BUY", volume=0, entry=1, pnl=5.0)) is None
    assert trade_r(Trade(position_id="1", origin="bot", symbol="X", side="BUY", volume=0, entry=1, pnl=5.0, risk_amount=0.0)) is None


def test_scorecard_groups_by_strategy_and_module(tmp_path):
    repo = Repo(tmp_path / "bot.db")
    add(repo, 1, 2.0, votes={"mtf": 1, "regime": -1})
    add(repo, 2, -1.0, votes={"mtf": 1, "regime": 1})
    add(repo, 3, -1.0, strategy=RANGE, votes={"mtf": -1})
    add(repo, 4, 5.0, origin="manual")  # elle islemler karneye girmez
    add(repo, 5, 3.0, risk=None)        # riski bilinmeyen islem R'ye cevrilemez
    card = scorecard(repo, BotSettings())
    assert card["strategies"][TREND]["live"] == {"trades": 2, "wins": 1, "win_rate": 0.5, "avg_r": 0.5,
                                                 "profit_factor": 2.0}
    assert card["strategies"][RANGE]["live"]["trades"] == 1 and card["strategies"][RANGE]["mode"] == "live"
    assert card["strategies"]["fx_confirmed_breakout_v6"]["live"]["trades"] == 0  # hic islem yoksa da listelenir
    assert card["modules"]["mtf"]["support"]["avg_r"] == 0.5 and card["modules"]["mtf"]["against"]["avg_r"] == -1.0
    assert card["modules"]["regime"]["against"]["trades"] == 1 and card["modules"]["regime"]["support"]["avg_r"] == -1.0
    assert card["totals"]["trades"] == 3


def test_profit_factor_and_win_rate(tmp_path):
    repo = Repo(tmp_path / "bot.db")
    for n, r in enumerate([3.0, 1.0, -1.0, -1.0], start=1):
        add(repo, n, r)
    live = scorecard(repo, BotSettings())["strategies"][TREND]["live"]
    assert live["win_rate"] == 0.5 and live["avg_r"] == 0.5 and live["profit_factor"] == pytest.approx(2.0)
    only_wins = Repo(tmp_path / "b.db")
    add(only_wins, 1, 2.0)
    assert scorecard(only_wins, BotSettings())["strategies"][TREND]["live"]["profit_factor"] is None


def test_auto_pause_needs_20_trades_and_negative_avg_r(tmp_path):
    repo = Repo(tmp_path / "bot.db")
    for n in range(1, 20):
        add(repo, n, -1.0)
    assert strategies_to_pause(repo, BotSettings()) == []  # 19 islem: henuz erken
    add(repo, 20, -1.0)
    found = strategies_to_pause(repo, BotSettings())
    assert [s for s, _ in found] == [TREND] and found[0][1]["avg_r"] == -1.0

    good = Repo(tmp_path / "good.db")
    for n in range(1, 25):
        add(good, n, 0.5 if n % 2 else -0.4)
    assert strategies_to_pause(good, BotSettings()) == []  # ortalama R > 0
    lenient = BotSettings(fusion=FusionSettings(pause_min_trades=30))
    assert strategies_to_pause(repo, lenient) == []
    assert strategies_to_pause(repo, BotSettings(strategy_modes={TREND: "shadow"})) == []  # zaten canli degil


async def losing_app(tmp_path):
    app = await started(tmp_path)
    for n in range(100, 120):
        add(app.repo, n, -1.0, at=NOW - 1000.0)  # gecmiste kapanmis islemler
    return app


async def test_auto_pause_persists_and_notifies_once(tmp_path):
    app = await losing_app(tmp_path)
    for _ in range(3):
        await app.bot.heartbeat()
    assert app.notifier.kinds().count("strategy_paused") == 1 and app.kinds().count("strategy_paused") == 1
    assert strategy_mode(app.repo.get_bot_settings(), TREND) == "shadow"
    again = Repo(tmp_path / "bot.db")  # yeniden baslatma: kalici
    assert strategy_mode(again.get_bot_settings(), TREND) == "shadow"
    assert scorecard(again, again.get_bot_settings())["strategies"][TREND]["paused"]["trades"] == 20


async def test_paused_strategy_continues_in_shadow(tmp_path):
    app = await losing_app(tmp_path)
    summary = await app.bot.on_bar_close()  # tarama basinda karne denetlenir
    assert summary.opened == 0 and summary.shadowed == 1
    assert app.fake.calls("POST", "/positions") == []
    assert [tuple(r) for r in app.repo.conn.execute("SELECT reason FROM shadow_trades")] == [("paused",)]


async def test_mode_endpoint_requires_token_and_confirm_for_live(tmp_path):
    app = await losing_app(tmp_path)
    await app.bot.heartbeat()
    token = issue_token(app.repo, now=NOW)
    api = create_app(app.bot, clock=lambda: app.clock["now"])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://bot") as http:
        assert (await http.post(f"/strategies/{TREND}/mode", json={"mode": "live"})).status_code == 401
        http.headers["Authorization"] = f"Bearer {token}"
        assert (await http.post(f"/strategies/{TREND}/mode", json={"mode": "live"})).status_code == 409
        assert (await http.post("/strategies/yok/mode", json={"mode": "off"})).status_code == 404
        assert (await http.post(f"/strategies/{TREND}/mode", json={"mode": "turbo"})).status_code == 422
        app.advance(10)
        ok = await http.post(f"/strategies/{TREND}/mode", json={"mode": "live", "confirm": True})
        assert ok.status_code == 200 and ok.json() == {"strategy_id": TREND, "mode": "live"}
        assert (await http.post(f"/strategies/{RANGE}/mode", json={"mode": "off"})).status_code == 200  # kapatmak onaysiz
    settings = app.repo.get_bot_settings()
    assert strategy_mode(settings, TREND) == "live" and strategy_mode(settings, RANGE) == "off"
    # Yeniden acilan strateji eski karnesi yuzunden hemen yeniden duraklatilmaz
    await app.bot.heartbeat()
    assert strategy_mode(app.repo.get_bot_settings(), TREND) == "live"
    assert app.notifier.kinds().count("strategy_paused") == 1


async def test_scorecard_endpoint(tmp_path):
    app = await losing_app(tmp_path)
    token = issue_token(app.repo, now=NOW)
    api = create_app(app.bot, clock=lambda: app.clock["now"])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://bot") as http:
        assert (await http.get("/scorecard")).status_code == 401
        body = (await http.get("/scorecard", headers={"Authorization": f"Bearer {token}"})).json()
    assert body["strategies"][TREND]["live"]["trades"] == 20 and body["strategies"][TREND]["live"]["avg_r"] == -1.0
    assert set(body["modules"]) >= {"mtf", "regime", "session"}
