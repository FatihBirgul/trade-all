"""Faz 2 bagimsiz incelemesinin bulgulari icin gerileme testleri (C1, I1–I6, kullanici SL/TP dogrulamasi)."""
import httpx
import pytest

from tests.app_helpers import NOW, started
from tests.execution.helpers import candidate
from tests.news.test_bot_news import EUR_NOW, USD_NOW, app_with_news
from tests.signals.test_scorecard import RANGE, TREND, add, losing_app
from tests.signals.test_shadow import Engine, bar, book, fake_report, run_all
from tradebot.api.auth import issue_token
from tradebot.api.server import create_app
from tradebot.config import strategy_mode
from tradebot.news.calendar import STALE_SECONDS
from tradebot.signals import scorecard

M15 = 900
BREAKOUT = "fx_confirmed_breakout_v6"


def client(app):
    token = issue_token(app.repo, now=app.clock["now"])
    api = create_app(app.bot, clock=lambda: app.clock["now"])
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://bot",
                             headers={"Authorization": f"Bearer {token}"})


# ------------------------------------------------------------------ C1: PUT /settings ile canliya alma yok
async def test_stale_settings_copy_cannot_revive_a_paused_strategy(tmp_path):
    """Istemci ayarlari okudu; bot stratejiyi duraklatti; istemci eski kopyayi ilgisiz bir degisiklikle
    geri gonderdi. Strateji onaysiz canliya donmemeli ve gercek emir acilmamali."""
    app = await losing_app(tmp_path)
    async with client(app) as http:
        stale = (await http.get("/settings")).json()
        assert stale["strategy_modes"] == {}
        await app.bot.heartbeat()  # bot duraklatir
        assert strategy_mode(app.repo.get_bot_settings(), TREND) == "shadow"
        stale["news"]["window_minutes"] = 45
        response = await http.put("/settings", json=stale)
        assert response.status_code == 409 and TREND in response.json()["detail"]
    settings = app.repo.get_bot_settings()
    assert strategy_mode(settings, TREND) == "shadow" and settings.news.window_minutes == 30  # hicbir sey yazilmadi
    assert TREND in scorecard.paused(app.repo)
    assert "settings_changed" not in app.kinds()
    summary = await app.bot.on_bar_close()
    assert summary.opened == 0 and app.fake.calls("POST", "/positions") == []


async def test_settings_put_cannot_take_any_strategy_live_but_other_changes_work(tmp_path):
    app = await started(tmp_path)
    async with client(app) as http:
        body = (await http.get("/settings")).json()
        body["strategy_modes"] = {RANGE: "off", BREAKOUT: "shadow"}
        assert (await http.put("/settings", json=body)).status_code == 200  # kapatmak/golgeye almak serbest
        for revived in ({RANGE: "live", BREAKOUT: "shadow"}, {RANGE: "off"}, {}):
            body["strategy_modes"] = revived
            assert (await http.put("/settings", json=body)).status_code == 409
        body["strategy_modes"] = {RANGE: "off", BREAKOUT: "shadow"}
        body["risk"]["risk_pct"] = 0.25
        assert (await http.put("/settings", json=body)).status_code == 200
        body["strategy_modes"]["olmayan_strateji"] = "off"
        assert (await http.put("/settings", json=body)).status_code == 422
    settings = app.repo.get_bot_settings()
    assert strategy_mode(settings, RANGE) == "off" and strategy_mode(settings, BREAKOUT) == "shadow"
    assert settings.risk.risk_pct == 0.25


async def test_off_to_live_needs_confirm_and_does_not_reset_an_unpaused_scorecard(tmp_path):
    """I5/I6: 19 zarar, kapat, ac, 20. zarar -> yine duraklatilir (sayac sifirlanmaz)."""
    app = await started(tmp_path)
    for n in range(100, 119):
        add(app.repo, n, -1.0, at=NOW - 1000.0)
    await app.bot.heartbeat()
    assert strategy_mode(app.repo.get_bot_settings(), TREND) == "live"  # 19 islem: henuz esik degil
    async with client(app) as http:
        assert (await http.post(f"/strategies/{TREND}/mode", json={"mode": "off"})).status_code == 200
        assert (await http.post(f"/strategies/{TREND}/mode", json={"mode": "live"})).status_code == 409
        assert strategy_mode(app.repo.get_bot_settings(), TREND) == "off"
        app.advance(10)
        assert (await http.post(f"/strategies/{TREND}/mode", json={"mode": "live", "confirm": True})).status_code == 200
    add(app.repo, 119, -1.0, at=app.clock["now"] + 1)
    app.advance(60)
    await app.bot.heartbeat()
    assert strategy_mode(app.repo.get_bot_settings(), TREND) == "shadow"
    assert app.notifier.kinds().count("strategy_paused") == 1


# ------------------------------------------------------------------ I1, I2: golge islemler
def test_shadow_counts_the_bar_it_was_opened_in(tmp_path):
    """Canlida islem mum kapanisindan 5 sn sonra, yeni mumun icinde acilir. O mumdaki stop sayilmali."""
    shadow = book(tmp_path)
    shadow.open(candidate(), "shadow", None, NOW + 5)  # giris 1.1002, SL 1.0972, TP 1.1062
    bars = [bar(-1, 1.0900, 1.1200),  # acilistan once kapanmis mum: sayilmaz
            bar(0, 1.0950, 1.1010),   # acilis mumu: stop goruldu
            bar(1, 1.1000, 1.1070)]   # sonraki mum hedefe gitti
    closed = shadow.resolve("EURUSD", bars, NOW + 2 * M15)
    assert len(closed) == 1 and closed[0]["result_r"] == pytest.approx(-1.0)


def test_a_persisting_setup_yields_one_shadow_trade_not_one_per_bar(tmp_path):
    shadow = book(tmp_path)
    assert shadow.open(candidate(setup="s" * 23 + "1"), "paused", 70.0, NOW + 5) is True
    for n in (1, 2, 3):  # egilim suruyor: her mumda yeni setup_id ile ayni aday
        assert shadow.open(candidate(setup="s" * 23 + str(n + 1)), "paused", 70.0, NOW + n * M15 + 5) is False
    assert shadow.open(candidate(side="SELL", setup="t" * 24, entry=1.1, sl=1.103, tp1=1.094, tp2=1.091),
                       "paused", 70.0, NOW + 5) is True  # ters yon ayri bir islemdir
    count = shadow._db.execute("SELECT COUNT(*) FROM shadow_trades WHERE side = 'BUY'").fetchone()[0]
    assert count == 1
    shadow.resolve("EURUSD", [bar(0, 1.0990, 1.1070)], NOW + M15)  # ilk islem hedefte kapandi
    assert shadow.open(candidate(setup="u" * 24), "paused", 70.0, NOW + 4 * M15 + 5) is True  # yenisi acilabilir


async def test_scorecard_separates_shadow_reasons_and_results_since_pause(tmp_path):
    app = await losing_app(tmp_path)
    shadow = book(tmp_path)
    shadow.open(candidate(setup="a" * 24), "low_score", 30.0, NOW - 5000)  # canlida zaten acilmazdi
    shadow.resolve("EURUSD", [bar(0, 1.0900, 1.1010, start=NOW - 5000)], NOW - 4000)
    await app.bot.heartbeat()  # duraklatma: NOW
    app.advance(10)
    shadow.open(candidate(setup="b" * 24), "paused", 80.0, app.clock["now"])
    shadow.resolve("EURUSD", [bar(0, 1.0990, 1.1070, start=app.clock["now"])], app.clock["now"] + M15)
    card = scorecard.scorecard(app.repo, app.repo.get_bot_settings())["strategies"][TREND]
    assert card["shadow"]["trades"] == 2
    assert card["shadow_by_reason"]["low_score"]["avg_r"] == pytest.approx(-1.0)
    assert card["shadow_by_reason"]["paused"]["avg_r"] == pytest.approx(2.0)
    assert card["shadow_since_pause"] == card["shadow_by_reason"]["paused"]
    assert scorecard.scorecard(app.repo, app.repo.get_bot_settings())["strategies"][RANGE]["shadow_since_pause"] is None


# ------------------------------------------------------------------ I4, I6: coklu strateji degerlendirmesi
class ShadowRoutedEngine:
    """Yonlendirici golgedeki trend stratejisini seciyor; kirilim stratejisi de CONFIRMED ve canli."""

    def __init__(self, live_side="BUY"):
        self.calls, self.live_side = [], live_side

    def analyze(self, provider, symbol, timeframe, **kwargs):
        enabled = sorted(kwargs["enabled_strategies"])
        self.calls.append(enabled)
        if TREND in enabled:
            return fake_report("BUY_CANDIDATE", TREND, [TREND, BREAKOUT])
        if BREAKOUT in enabled:
            return fake_report(f"{self.live_side}_CANDIDATE", BREAKOUT, [BREAKOUT], side=self.live_side)
        return fake_report("WAIT", None, [])


def test_shadow_strategy_does_not_mute_a_live_one():
    engine = ShadowRoutedEngine()
    results = run_all(engine, {TREND: "shadow"})
    assert [(r.candidate.strategy_id, r.mode) for r in results] == [(TREND, "shadow"), (BREAKOUT, "live")]
    assert TREND not in engine.calls[1]  # ikinci degerlendirme yalnizca canli stratejilerle


def test_live_candidate_against_the_shadow_direction_is_not_taken():
    results = run_all(ShadowRoutedEngine(live_side="SELL"), {TREND: "shadow"})
    assert [(r.candidate.strategy_id, r.mode) for r in results] == [(TREND, "shadow")]


def test_live_routed_candidate_needs_no_second_evaluation():
    engine = ShadowRoutedEngine()
    results = run_all(engine, {BREAKOUT: "shadow"})
    assert [(r.candidate.strategy_id, r.mode) for r in results] == [(TREND, "live")] and len(engine.calls) == 1


class ConflictEngine(Engine):
    """V9 ters yonlu onay nedeniyle secim yapmadi (`routing.status != selected`)."""

    def analyze(self, provider, symbol, timeframe, **kwargs):
        self.calls.append(list(kwargs["enabled_strategies"]))
        report = fake_report("NO_TRADE", None, [TREND, BREAKOUT])
        report.routing = {"status": "wait", "reason": "opposing_strategy_conflict"}
        return report


def test_opposing_conflict_veto_is_never_pierced_by_single_strategy_retries():
    engine = ConflictEngine()
    results = run_all(engine)
    assert len(engine.calls) == 1  # stratejiler tek tek yeniden denenmez
    assert [r.candidate for r in results] == [None]


async def test_bot_never_rounds_a_reduced_lot_up_to_the_minimum(tmp_path):
    """Kucuk hesap: V9 en kucuk lotu veriyor. Orta puan lotu kuculttugunde islem ACILMAZ (gozlem);
    en kucuk lota yuvarlamak riski hedefin ustune cikarirdi."""
    app = await started(tmp_path, balance=300.0)
    real_score = app.bot._score

    def reduced(result, instrument, settings):
        score, votes, _ = real_score(result, instrument, settings)
        return 65.0, votes, 0.75
    app.bot._score = reduced
    summary = await app.bot.on_bar_close()
    assert summary.candidates == 1 and summary.opened == 0 and summary.observed == 1
    assert app.fake.calls("POST", "/positions") == []

    # Ayni kosulda tam carpanla islem acilir ve lot en kucuk lottur: senaryo gercekten o sinirda.
    app.bot._score = lambda result, instrument, settings: (90.0, real_score(result, instrument, settings)[1], 1.0)
    app.advance(M15)
    from tests.app_helpers import feed_ticks, load_market
    bid, ask = load_market(app.fake, "XAUUSD", app.clock["now"])
    await feed_ticks(app, "XAUUSD", bid, ask, app.clock["now"])
    summary = await app.bot.on_bar_close()
    posts = app.fake.calls("POST", "/positions")
    assert summary.opened == 1 and float(posts[0][2]["volume"]) == 0.01


# ------------------------------------------------------------------ I3: takvim hic alinamadiysa
async def test_calendar_never_fetched_warns_at_once_and_trading_continues(tmp_path):
    app, _ = await app_with_news(tmp_path, USD_NOW, state={"ok": False})
    summary = await app.bot.on_bar_close()
    assert summary.opened == 1 and summary.news_blocked == 0  # spec §6.6: bot devam eder
    await app.bot.heartbeat()
    assert app.kinds().count("news_unavailable") == 1
    kind, title, body, data = [n for n in app.notifier.sent if n[0] == "news_unavailable"][-1]
    assert "hiç alınamadı" in body and data == {"never_fetched": True}
    for _ in range(3):  # ayni gun yeniden uyarmaz
        app.advance(1000)
        await app.bot.heartbeat()
    assert app.kinds().count("news_unavailable") == 1
    async with client(app) as http:
        body = (await http.get("/news")).json()
    assert body["stale"] is True and body["fetched_at"] is None and body["events"] == []


async def test_frequent_restarts_do_not_hide_a_calendar_that_was_never_fetched(tmp_path):
    """Eskiden 'ilk deneme' bellekte tutuluyordu: 24 saatten sik yeniden baslayan serviste uyari hic cikmazdi."""
    from tests.app_helpers import build
    from tests.news.test_bot_news import calendar_factory
    app, state = await app_with_news(tmp_path, USD_NOW, state={"ok": False})
    await app.bot.heartbeat()
    for day in (1, 2):
        app.advance(20 * 3600)  # 20 saatte bir yeniden baslatma
        app.fake.event_listeners.clear()
        app.fake.tick_listeners.clear()
        app.repo.close()
        factory, _ = calendar_factory(USD_NOW, state)
        app = build(app.path, fake=app.fake, clock=app.clock, news=factory)
        await app.bot.start()
        await app.bot.heartbeat()
    assert app.kinds().count("news_unavailable") >= 2  # her yeni gunde yeniden


async def test_stale_calendar_keeps_trading(tmp_path):
    app, state = await app_with_news(tmp_path, EUR_NOW)
    state["ok"] = False
    stored = app.repo.get_setting("news_calendar")
    app.repo.set_setting("news_calendar", {**stored, "fetched_at": NOW - STALE_SECONDS - 1})  # 24 saattir yenilenemedi
    await app.bot.heartbeat()
    assert app.kinds().count("news_unavailable") == 1
    assert "24 saattir" in [n for n in app.notifier.sent if n[0] == "news_unavailable"][-1][2]
    summary = await app.bot.on_bar_close()
    assert summary.opened == 1


# ------------------------------------------------------------------ kullanici SL/TP dogrulamasi (Android C2)
async def open_trade(app):
    await app.bot.on_bar_close()
    await app.fake.flush()
    return app.repo.open_trades("bot")[0]


async def test_user_stop_far_from_price_or_on_the_wrong_side_is_rejected_before_the_broker(tmp_path):
    app = await started(tmp_path)
    trade = await open_trade(app)  # XAUUSD BUY
    price = app.bot.quotes.quote("XAUUSD")["bid"]
    before = len(app.fake.calls("PATCH", "/orders")) + len(app.fake.calls("POST", "/orders"))
    async with client(app) as http:
        path = f"/positions/{trade.position_id}"
        # binlik ayrac / eksik hane: 2 000 yerine 2,0
        far = await http.patch(path, json={"sl": round(price / 1000, 3)})
        assert far.status_code == 422 and "çok uzak" in far.json()["detail"]
        wrong = await http.patch(path, json={"sl": round(price + 5, 2)})
        assert wrong.status_code == 422 and "altında olmalı" in wrong.json()["detail"]
        wrong_tp = await http.patch(path, json={"tp": round(price - 5, 2)})
        assert wrong_tp.status_code == 422 and "üstünde olmalı" in wrong_tp.json()["detail"]
        assert len(app.fake.calls("PATCH", "/orders")) + len(app.fake.calls("POST", "/orders")) == before
        assert app.repo.get_trade(trade.position_id).user_sl_override is False
        ok = await http.patch(path, json={"sl": round(price - 3, 2)})
        assert ok.status_code == 200 and ok.json()["order"]
