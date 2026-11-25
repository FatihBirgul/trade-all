"""Gunluklerde ve olay kayitlarinda sir bulunmaz: API anahtari, ozel anahtar, erisim anahtari, eslestirme kodu."""
import json
import logging

import httpx

from tests.app_helpers import started
from tests.exness.test_client import KEY, settings
from tradebot.api import auth
from tradebot.api.server import create_app


async def test_a_full_session_writes_no_secret_to_logs_or_events(tmp_path, caplog):
    caplog.set_level(logging.DEBUG)
    app = await started(tmp_path)
    code = auth.create_pair_code(app.repo, now=app.clock["now"])
    api = create_app(app.bot, clock=lambda: app.clock["now"])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://bot") as http:
        paired = await http.post("/pair", json={"code": code})
        assert paired.status_code == 200
        token = paired.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        assert (await http.get("/status", headers=headers)).status_code == 200
        assert (await http.get("/status", headers={"Authorization": "Bearer yanlis-" + "x" * 40})).status_code == 401
        await http.post("/trades", headers=headers,
                        json={"symbol": "XAUUSD", "side": "BUY", "sl_distance": 5.0, "lots": 0.01})
        body = (await http.get("/settings", headers=headers)).json()
        await http.put("/settings", headers=headers, json=body)
    await app.bot.on_bar_close()
    await app.fake.flush()
    await app.bot.manage_tick()
    await app.bot.heartbeat()
    await app.bot.maintenance()

    written = caplog.text + json.dumps(app.repo.events(limit=500), default=str)
    assert len(caplog.records) > 5  # gercekten gunluk yazildi
    api_key = settings().exness_api_key.get_secret_value()
    private_lines = [line for line in KEY.splitlines() if line and not line.startswith("-----")]
    for secret in (api_key, token, code, *private_lines):
        assert secret not in written, secret[:6] + "…"
    assert "Bearer " not in written and "PRIVATE KEY" not in written
