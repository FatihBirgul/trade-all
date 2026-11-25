"""Haber penceresinin servis dongusune ve API'ye baglanmasi."""
import httpx

from tests.app_helpers import NOW, build, feed_ticks, load_market
from tradebot.api.auth import issue_token
from tradebot.api.server import create_app
from tradebot.config import BotSettings, NewsSettings
from tradebot.news.calendar import STALE_SECONDS, NewsCalendar
from tradebot.store.repo import Trade


def iso(epoch):
    from datetime import datetime, timezone
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def calendar_factory(rows, state=None):
    state = state if state is not None else {"ok": True}

    def responder(request):
        if not state["ok"]:
            raise httpx.ConnectError("no route")
        return httpx.Response(200, json=rows)

    def factory(repo, clock):
        return NewsCalendar(repo, transport=httpx.MockTransport(responder), clock=clock)
    return factory, state


async def app_with_news(tmp_path, rows, *, symbols=("XAUUSD",), state=None, **kwargs):
    factory, state = calendar_factory(rows, state)
    app = build(tmp_path, news=factory, **kwargs)
    quotes = {s: load_market(app.fake, s, NOW) for s in symbols}
    await app.bot.start()
    for symbol, (bid, ask) in quotes.items():
        await feed_ticks(app, symbol, bid, ask, NOW)
    return app, state


USD_NOW = [{"title": "NFP", "country": "USD", "date": iso(NOW + 20 * 60), "impact": "High"}]
EUR_NOW = [{"title": "ECB", "country": "EUR", "date": iso(NOW + 20 * 60), "impact": "High"}]


async def test_scan_skips_symbol_in_news_window_without_notification(tmp_path):
    app, _ = await app_with_news(tmp_path, USD_NOW)
    summary = await app.bot.on_bar_close()
    assert summary.news_blocked >= 1 and summary.candidates == 0 and summary.opened == 0
    assert app.fake.calls("POST", "/positions") == [] and app.notifier.sent == []
    assert not any("XAUUSD" in call[1] for call in app.fake.calls("GET", "/candles"))  # analiz bile edilmedi


async def test_unrelated_currency_news_does_not_block(tmp_path):
    app, _ = await app_with_news(tmp_path, EUR_NOW)
    summary = await app.bot.on_bar_close()
    assert summary.opened == 1  # XAUUSD: EUR haberi ilgisiz


async def test_window_setting_and_disable_are_respected(tmp_path):
    rows = [{"title": "NFP", "country": "USD", "date": iso(NOW + 50 * 60), "impact": "High"}]
    app, _ = await app_with_news(tmp_path, rows)
    assert (await app.bot.on_bar_close()).opened == 1  # 50 dk sonra: 30 dk'lik pencerenin disinda

    wide, _ = await app_with_news(tmp_path / "wide", rows)
    wide.repo.set_bot_settings(BotSettings(dry_run=False, news=NewsSettings(window_minutes=60)))
    assert (await wide.bot.on_bar_close()).news_blocked >= 1


async def test_disabled_news_filter_blocks_nothing(tmp_path):
    app, _ = await app_with_news(tmp_path, USD_NOW)
    app.repo.set_bot_settings(BotSettings(dry_run=False, news=NewsSettings(enabled=False)))
    summary = await app.bot.on_bar_close()
    assert summary.news_blocked == 0 and summary.opened == 1


async def test_open_positions_still_managed_during_news(tmp_path):
    app, _ = await app_with_news(tmp_path, EUR_NOW)
    await app.bot.on_bar_close()
    await app.fake.flush()
    trade = app.repo.open_trades("bot")[0]
    app.repo.set_setting("news_calendar", {"fetched_at": NOW, "events": [
        {"currency": "USD", "title": "NFP", "at": NOW + 60, "impact": "high"}]})
    risk = trade.initial_risk_r_price
    await app.fake.set_price("XAUUSD", round(trade.entry + risk, 2), round(trade.entry + risk + 0.2, 2))
    await app.bot.manage_tick()
    await app.fake.flush()
    assert app.repo.get_trade(trade.position_id).sl > trade.sl  # stop yonetimi haber sirasinda da surer


async def test_stale_calendar_warns_once_and_keeps_trading(tmp_path):
    app, state = await app_with_news(tmp_path, EUR_NOW)
    state["ok"] = False
    app.advance(STALE_SECONDS + 3600)
    for _ in range(3):
        await app.bot.heartbeat()
        app.advance(1000)
    assert app.notifier.kinds().count("news_unavailable") == 1
    assert app.kinds().count("news_unavailable") == 1
    # Takvim bayat olsa da bot durmaz
    assert app.repo.bot_state().halted is False and app.repo.bot_state().stopped is False


async def test_calendar_never_available_does_not_block_trading(tmp_path):
    app, _ = await app_with_news(tmp_path, USD_NOW, state={"ok": False})
    summary = await app.bot.on_bar_close()
    assert summary.opened == 1 and summary.news_blocked == 0


async def test_news_endpoint_lists_upcoming_high_impact(tmp_path):
    rows = USD_NOW + [{"title": "Retail", "country": "GBP", "date": iso(NOW + 3600), "impact": "Medium"},
                      {"title": "Eski", "country": "USD", "date": iso(NOW - 7200), "impact": "High"}]
    app, _ = await app_with_news(tmp_path, rows)
    token = issue_token(app.repo, now=NOW)
    api = create_app(app.bot, clock=lambda: app.clock["now"])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://bot") as http:
        assert (await http.get("/news")).status_code == 401
        body = (await http.get("/news", headers={"Authorization": f"Bearer {token}"})).json()
    assert body["enabled"] is True and body["window_minutes"] == 30 and body["stale"] is False
    assert [e["title"] for e in body["events"]] == ["NFP"]
