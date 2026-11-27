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
