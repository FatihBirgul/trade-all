"""Telefon uygulamasi icin fixture uretir: GERCEK sunucu kodunun (FastAPI + Bot) verdigi yanitlar.

Borsa sahtedir (tests/fakes/exness.py); hesap sahte bir 10000 USD hesabidir. Yanit sekilleri sunucunun
kendi kodundan gelir, elle yazilmaz: sunucu degisince bu betik yeniden calistirilir ve uygulama testleri
gercek sekle karsi kosar.

    cd trade-bot && .venv/bin/python tools/capture_app_fixtures.py ../trade-bot-app/fixtures
"""
import asyncio
import json
import sys
import tempfile
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.app_helpers import feed_ticks, load_market, started  # noqa: E402
from tradebot.api.auth import create_pair_code, issue_token  # noqa: E402
from tradebot.api.server import create_app  # noqa: E402

M15 = 900
GETS = {"health": "/health", "summary": "/health/summary?hours=24", "status": "/status", "positions": "/positions", "settings": "/settings",
        "reports_day": "/reports?period=day", "reports_week": "/reports?period=week",
        "reports_month": "/reports?period=month", "scorecard": "/scorecard", "strategies": "/strategies",
        "news": "/news", "events": "/events?newest=true&limit=100", "symbols": "/symbols"}


async def next_bar(app):
    app.advance(M15)
    bid, ask = load_market(app.fake, "XAUUSD", app.clock["now"])
    await feed_ticks(app, "XAUUSD", bid, ask, app.clock["now"])
    summary = await app.bot.on_bar_close()
    await app.fake.flush()
    return summary


async def dry_idle(folder, **account):
    """Bugunku uretim durumu: deneme modu, taramalar yapiliyor, pozisyon ve kapanmis islem yok."""
    app = await started(folder, dry_run=True, **account)
    await app.bot.on_bar_close()
    for _ in range(3):
        await next_bar(app)
    await app.bot.heartbeat()
    return app


async def live_active(folder, **account):
    """Canli: bir bot islemi karla kapandi, bir bot islemi ve bir elle islem acik."""
    app = await started(folder, **account)
    await app.bot.on_bar_close()
    await app.fake.flush()
    trade = app.repo.open_trades("bot")[0]
    risk = trade.initial_risk_r_price
    for multiple in (1, 2):
        price = round(trade.entry + multiple * risk, 2)
        await app.fake.set_price("XAUUSD", price, round(price + 0.2, 2))
        await app.bot.manage_tick()
        await app.fake.flush()
    await app.fake.set_price("XAUUSD", trade.tp2, trade.tp2 + 0.2)
    await app.fake.flush()
    await next_bar(app)  # yeni bot islemi
    opened = app.repo.open_trades("bot")
    if opened:
        entry = opened[0].entry
        await app.bot.executor.open_manual("XAUUSD", "BUY", 0.01, sl=round(entry - 2 * risk, 2),
                                           tp=round(entry + 4 * risk, 2))
        await app.fake.flush()
    await app.bot.heartbeat()
    return app


async def capture(app, target: Path):
    target.mkdir(parents=True, exist_ok=True)
    token = issue_token(app.repo, now=app.clock["now"])
    api = create_app(app.bot, clock=lambda: app.clock["now"])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://bot") as http:
        auth = {"Authorization": f"Bearer {token}"}
        for name, path in GETS.items():
            response = await http.get(path, headers=auth)
            response.raise_for_status()
            (target / f"{name}.json").write_text(json.dumps(response.json(), indent=1, ensure_ascii=False) + "\n")
        code = create_pair_code(app.repo, now=app.clock["now"])
        paired = await http.post("/pair", json={"code": code})
        (target / "pair.json").write_text(json.dumps({"token": "t" * len(paired.json()["token"])}) + "\n")
        symbols = (await http.get("/symbols", headers=auth)).json()
        rows = symbols.get("symbols") if isinstance(symbols, dict) else symbols
        first = next(row for row in rows if row.get("quoted") and row.get("bid"))  # fiyati olan ilk sembol
        distance = round(first["bid"] * 0.002, first["digits"])
        preview = await http.post("/trades/preview", headers=auth,
                                  json={"symbol": first["symbol"], "side": "BUY", "sl_distance": distance,
                                        "tp_distance": distance * 2})
        (target / "trade_preview.json").write_text(
            json.dumps({"status": preview.status_code, "body": preview.json()}, indent=1, ensure_ascii=False) + "\n")
        unauthorized = await http.get("/status")
        (target / "unauthorized.json").write_text(
            json.dumps({"status": unauthorized.status_code, "body": unauthorized.json()}, ensure_ascii=False) + "\n")


async def main(out: Path):
    # Cent hesap (USC; 100 USC = 1 USD): gercek hesap boyledir. `cent_idle` gercek hesabin buyuklugunde (3000 USC),
    # deneme modunda. `cent_active` islem acilabilsin diye buyuk bir cent hesaptir (en kucuk lot kucuk hesaba sigmaz).
    scenarios = (("dry_idle", dry_idle, {}), ("live_active", live_active, {}),
                 ("cent_idle", dry_idle, {"currency": "USC", "balance": 3_000.0}),
                 ("cent_active", live_active, {"currency": "USC", "balance": 300_000.0}))
    for name, build, account in scenarios:
        with tempfile.TemporaryDirectory() as folder:
            app = await build(Path(folder), **account)
            await capture(app, out / name)
            app.repo.close()
            print(name, "ok")


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1])))
