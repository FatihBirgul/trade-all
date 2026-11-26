"""Canliya gecis karari icin deneme modu ozeti: yalnizca sayilar ve nedenler, hesap bilgisi yok."""
import json

import httpx

from tests.app_helpers import NOW, feed_ticks, load_market, restart, started
from tradebot.api.server import create_app
from tradebot.exness import schema

M15 = 900


async def next_bar(app, symbol="XAUUSD"):
    app.advance(M15)
    bid, ask = load_market(app.fake, symbol, app.clock["now"])
    await feed_ticks(app, symbol, bid, ask, app.clock["now"])
    return await app.bot.on_bar_close()


async def public_get(app, path, **params):
    api = create_app(app.bot, clock=lambda: app.clock["now"])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://bot") as http:
        return await http.get(path, params=params)  # token yok: herkese acik


async def test_summary_counts_scans_candidates_and_reasons_without_account_data(tmp_path):
    app = await started(tmp_path, dry_run=True)  # sahte hesap: 10000 USD, hesap no 123456
    first = await app.bot.on_bar_close()
    assert first.would_open == 1 and first.opened == 0 and app.fake.calls("POST", "/positions") == []
    assert sum(first.veto_reasons.values()) == 3 and sum(first.reasons.values()) == 3
    for _ in range(2):
        await next_bar(app)

    response = await public_get(app, "/health/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is True and body["hours"] == 24
    assert body["scans"] == 3 and body["symbols_scanned"] == 12
    assert body["candidates"] == 3 and body["would_open"] == 3 and body["opened"] == 0
    assert body["signals"] == 3 and len(body["samples"]) == 3
    assert sum(body["veto_reasons"].values()) == 9 and sum(body["decisions"].values()) == 9
    assert body["portfolio_blocked"] == 0 and body["errors"] == 0

    sample = body["samples"][-1]
    assert sample["symbol"] == "XAUUSD" and sample["side"] == "BUY" and sample["dry_run"] is True
    assert 0 < sample["risk_pct"] <= 0.5 and sample["stop_pct"] > 0
    # Lot YOK: lot + stop mesafesi + risk yuzdesi birlikte hesap varligini ele verir (inceleme C2).
    assert set(sample) == {"at", "symbol", "side", "strategy_id", "score", "net_rr", "stop_pct", "risk_pct",
                           "dry_run"}
    # Herkese acik cikti: bakiye, varlik, para tutari, hesap numarasi, giris/stop fiyati yok.
    text = response.text
    assert sample["net_rr"] == round(sample["net_rr"], 2)
    for secret in ("10000", "10 000", "account", "risk_amount", "equity", "balance", "currency", "entry",
                   "stop_loss", "take_profit"):
        assert secret not in text, secret


async def test_summary_reports_gate_and_skip_reasons(tmp_path):
    app = await started(tmp_path, dry_run=True)
    await app.bot.on_bar_close()
    # Puan esiginin altinda kalan aday: gozlem
    real_score = app.bot._score
    app.bot._score = lambda result, instrument, settings: (30.0, real_score(result, instrument, settings)[1], None)
    await next_bar(app)
    app.bot._score = real_score
    # Portfoy kapisi: gunluk kayip siniri dolmus gibi
    app.streams[0].go_down()
    await next_bar(app)
    body = (await public_get(app, "/health/summary")).json()
    assert body["scans"] == 2 and body["scans_skipped"] == {"stream_down": 1}
    assert body["observed"] == 1 and body["would_open"] == 1
    assert list(body["observed_reasons"].values()) == [1]
    assert "güven puanı" in next(iter(body["observed_reasons"]))


async def test_summary_window_and_restart(tmp_path):
    app = await started(tmp_path, dry_run=True)
    await app.bot.on_bar_close()
    app.advance(30 * 3600)  # 30 saat sonra: 24 saatlik pencerenin disinda
    assert (await public_get(app, "/health/summary")).json()["scans"] == 0
    assert (await public_get(app, "/health/summary", hours=48)).json()["scans"] == 1
    assert (await public_get(app, "/health/summary", hours=1000)).status_code == 422
    again = restart(app)  # ozet olay kayitlarindan hesaplanir: yeniden baslatmada kaybolmaz
    assert again.bot.scan_summary(48)["scans"] == 1 and again.bot.scan_summary(48)["would_open"] == 1


async def test_live_signals_are_marked_as_not_dry_run(tmp_path):
    app = await started(tmp_path)  # canli
    await app.bot.on_bar_close()
    body = app.bot.scan_summary()
    assert body["dry_run"] is False and body["opened"] == 1 and body["would_open"] == 0
    assert body["samples"][0]["dry_run"] is False


async def test_subscription_ack_is_not_counted_as_an_error(tmp_path):
    """Canli: fiyat akisi her abonelik icin {"id": "ticks-1", "code": 200, "error_message": ""} dondurdu."""
    app = await started(tmp_path)
    ack = {"id": "ticks-1", "code": 200, "error_message": ""}
    await app.bot.on_tick_message(ack)
    await app.bot.on_tick_message({"id": "ticks-0", "code": 200, "error_message": ""})
    assert app.bot.tick_errors == 0 and app.bot.tick_error is None and app.bot.tick_acks == 2
    health = (await public_get(app, "/health")).json()
    assert health["tick_errors"] == 0 and health["tick_error"] is None and health["tick_acks"] == 2
    # Gercek hata hala hata
    await app.bot.on_tick_message({"id": "ticks-2", "code": 4000, "error_message": "MARKET_INSTRUMENT_NOT_FOUND"})
    assert app.bot.tick_errors == 1 and app.bot.tick_error["code"] == 4000
    # Olay akisinda da onay "hata" diye siniflanmaz
    assert schema.parse_ws_event(ack)[0] == "ack"
    assert schema.parse_ws_event({"id": "x", "code": 3000, "error_message": "REQUEST_INVALID"})[0] == "error"
    assert schema.is_ws_ack({"code": True}) is False and schema.is_ws_ack({"code": "200"}) is False


async def test_slow_scan_evaluates_each_symbol_at_its_own_time(tmp_path):
    """Canlida goruldu: mumlar yavas cekilirken fiyat akmaya devam eder. Tarama baslangic saatiyle
    degerlendirilirse sonraki semboller "stale tick" ile elenir ve hic aday cikmaz."""
    app = await started(tmp_path, dry_run=True)
    real_get = app.bot.candles.get

    async def slow_get(symbol, frame, count):
        app.advance(4)  # istek limiti beklemesi
        quote = app.bot.quotes.quote(symbol)
        if quote is not None:
            await feed_ticks(app, symbol, quote["bid"], quote["ask"], app.clock["now"])  # akis surer
        return await real_get(symbol, frame, count)

    app.bot.candles.get = slow_get
    summary = await app.bot.on_bar_close()
    assert summary.scanned == 4
    assert "stale tick" not in summary.veto_reasons, summary.veto_reasons
    assert summary.would_open == 1


async def test_public_reasons_hide_numbers(tmp_path):
    app = await started(tmp_path, dry_run=True)
    app.repo.add_event("info", "scan", "tarama", {"scanned": 1, "veto_reasons": {"spread 0.00123 above 1234.5": 1,
                                                                                 "V2 QC: stale_data": 2}})
    reasons = (await public_get(app, "/health/summary")).json()["veto_reasons"]
    assert reasons == {"spread # above #": 1, "V2 QC: stale_data": 2}


async def test_summary_names_symbols_whose_data_was_rejected_and_where_the_gap_is(tmp_path):
    """Tanilama: hangi sembolun verisi reddedildi, eksik mum nerede. Yalnizca piyasa bilgisi; hesap verisi yok."""
    app = await started(tmp_path, dry_run=True)
    rows = app.fake.candles[("XAUUSD", "H1")]
    hole = rows[-10]["time"]
    app.fake.set_candles("XAUUSD", "H1", [r for r in rows if r["time"] != hole])  # piyasa acikken eksik bir H1 mumu
    summary = await app.bot.on_bar_close()
    assert summary.would_open == 0
    note = summary.data_rejects["XAUUSD"]
    assert note.startswith("missing candle") and "[H1 " in note and ("OPEN]" in note or "CLOSING_SOON]" in note)
    assert note.endswith("(onarım denendi: borsada da yok)")  # borsa da o mumu vermiyor: gercek bosluk
    body = (await public_get(app, "/health/summary")).json()
    assert body["last_data_rejects"]["XAUUSD"] == note
    assert set(body["last_data_rejects"]) <= {"XAUUSD", "EURUSD", "GBPUSD", "BTCUSD"}
    for secret in ("10000", "equity", "balance", "123456"):
        assert secret not in json.dumps(body["last_data_rejects"])
    # Liste her zaman EN SON taramaya aittir: atlanan taramadan sonra da eski liste kalmaz.
    app.repo.add_event("info", "scan", "tarama", {"scanned": 4})
    assert (await public_get(app, "/health/summary")).json()["last_data_rejects"] == {}


def h1_requests(app):
    return [c for c in app.fake.calls("GET", "/candles") if "instrument=XAUUSD&timeframe=H1" in c[1]]


async def test_a_hole_in_the_candle_cache_is_healed_when_the_exchange_has_the_bar(tmp_path):
    """Onbellek yalnizca son mumdan sonrasini ceker; arada kalan bosluk kendiliginden kapanmazdi."""
    app = await started(tmp_path, dry_run=True)
    assert (await app.bot.on_bar_close()).would_open == 1
    hole = app.fake.candles[("XAUUSD", "H1")][-10]["time"]
    deleted = app.bot.candles._db.execute(
        "DELETE FROM candles WHERE symbol = 'XAUUSD' AND tf = 'H1' AND time = ?", (hole,)).rowcount
    assert deleted == 1  # onbellekte bosluk; borsada mum var
    broken = await app.bot.on_bar_close()
    assert broken.would_open == 0 and "onarıldı: mum geldi" in broken.data_rejects["XAUUSD"]
    healed = await app.bot.on_bar_close()
    assert "XAUUSD" not in healed.data_rejects
    assert healed.reasons.get("INSUFFICIENT_DATA", 0) == 0


async def test_a_real_market_gap_is_asked_for_once_not_on_every_scan(tmp_path):
    app = await started(tmp_path, dry_run=True)
    rows = app.fake.candles[("XAUUSD", "H1")]
    hole = rows[-10]["time"]
    app.fake.set_candles("XAUUSD", "H1", [r for r in rows if r["time"] != hole])  # borsada da yok
    first = await app.bot.on_bar_close()
    assert "borsada da yok" in first.data_rejects["XAUUSD"]
    asked = len(h1_requests(app))
    for _ in range(3):
        again = await app.bot.on_bar_close()
        assert "borsada da yok" in again.data_rejects["XAUUSD"]
    assert len(h1_requests(app)) == asked  # ayni bosluk icin yeniden istek yok (istek limiti korunur)


async def test_a_hole_is_healed_even_when_v9_does_not_complain_and_a_failed_request_is_retried(tmp_path):
    """Inceleme: V9 devirdeki tek sessiz M15 mumunu hos gorur; borsada aslinda VAR olan bir mum onbellekte
    eksik kaldiysa onarim V9'un reddini beklememeli. Basarisiz istek "denendi" sayilmaz."""
    from tradebot.exness.errors import ExnessUnavailable

    app = await started(tmp_path, dry_run=True)
    await app.bot.on_bar_close()
    monkey = {"fail": True}
    real_heal = app.bot.candles.heal

    async def flaky(symbol, frame, minute):
        if monkey["fail"]:
            raise ExnessUnavailable("gecici")
        return await real_heal(symbol, frame, minute)

    app.bot.candles.heal = flaky
    app.bot._gaps = lambda instrument: iter([("M15", int(NOW) - 40 * 900, "OPEN")] if instrument.symbol == "XAUUSD" else [])
    await app.bot.on_bar_close()  # V9 reddetmedi (bosluk yapay), yine de onarim denendi ve basarisiz oldu
    assert app.bot._heal_tried == {}
    monkey["fail"] = False
    await app.bot.on_bar_close()  # basarisiz istek yeniden denendi
    assert list(app.bot._heal_tried) == [("XAUUSD", "M15", (int(NOW) - 40 * 900) // 900)]


async def test_outcomes_report_r_results_without_account_data(tmp_path):
    app = await started(tmp_path, dry_run=True)
    assert (await app.bot.on_bar_close()).would_open == 1
    for _ in range(3):
        await next_bar(app)
    response = await public_get(app, "/health/outcomes")
    assert response.status_code == 200
    body = response.json()
    signal = body["signals"][0]
    assert signal["symbol"] == "XAUUSD" and signal["side"] == "BUY" and signal["dry_run"] is True
    assert signal["result"] is not None and signal["result"]["bars"] >= 1
    assert set(signal) == {"at", "symbol", "side", "strategy_id", "score", "dry_run", "result"}
    assert sum(row[1] for row in body["hourly"]) == 4  # dort tarama
    text = response.text
    for secret in ("123456", "10000", "lots", "risk_amount", "entry", "equity", "balance"):
        assert secret not in text
    assert (await public_get(app, "/health/outcomes", hours=1000)).status_code == 422
