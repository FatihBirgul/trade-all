"""Endeks spread olcumu (Faz 5 maliyet modeli): US30/US500/USTEC'e yalnizca OLCUM icin abone olunur; evrende
degiller, taranmaz, emir acilmaz."""
from tests.app_helpers import NOW, build
from tests.fakes.exness import conditions


async def test_index_is_subscribed_and_measured_but_never_traded(tmp_path):
    app = build(tmp_path)
    app.fake.instruments["US30"] = conditions("US30", category="Indices", base="US30", quote="USD", digits=1,
                                              contract="1")
    await app.bot.start()
    assert "US30" in app.bot._tick_symbols()
    assert "US30" not in {i.symbol for i in app.bot.catalog.universe()}
    assert "US30" not in {i.symbol for i in app.bot.catalog.members()}
    for k in range(30):
        await app.fake.set_price("US30", 44000.0, 44002.5, at=NOW - 30 + k)
    assert await app.bot.record_spreads() >= 1
    profile = app.repo.spread_profile(min_samples=1)
    assert abs(profile["US30"]["all"] - 2.5) < 1e-6
    before = len(app.fake.requests)
    summary = await app.bot.on_bar_close()
    assert "US30" not in str([d for d in getattr(summary, "decisions", [])])
    assert not [r for r in app.fake.requests[before:] if r[0] == "POST"]


async def test_index_has_its_own_subscription_message_and_cannot_be_ordered_by_hand(tmp_path):
    import httpx  # noqa: F401
    from tests.api.test_manual_preview import client
    app = build(tmp_path)
    app.fake.instruments["US30"] = conditions("US30", category="Indices", base="US30", quote="USD", digits=1,
                                              contract="1")
    await app.bot.start()
    messages = app.bot._tick_stream.subscriptions
    measure = [m for m in messages if "US30" in str(m)]
    assert len(measure) == 1 and all("EURUSD" not in str(m) for m in measure)
    for k in range(30):
        await app.fake.set_price("US30", 44000.0, 44002.5, at=NOW - 30 + k)
    before = len(app.fake.requests)
    async with client(app) as http:
        preview = await http.post("/trades/preview", json={"symbol": "US30", "side": "BUY", "sl_distance": 50.0,
                                                           "tp_distance": 100.0})
        order = await http.post("/trades", json={"symbol": "US30", "side": "BUY", "volume": 1.0, "sl": 43900.0,
                                                 "tp": 44200.0})
    assert preview.status_code == 422 and order.status_code == 422
    assert not [r for r in app.fake.requests[before:] if r[0] == "POST"]
