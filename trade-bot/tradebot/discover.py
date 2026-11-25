"""Salt-okuma API kesif betigi.

    python -m tradebot.discover [--out KLASOR] [--seconds 30]

Yalnizca GET istekleri ve WebSocket dinleme yapar; emir gondermez. Yanitlari JSON olarak yazar ve
zip'ler. API anahtari, ozel anahtar ve imza basliklari hicbir dosyaya yazilmaz.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import zipfile
from collections import Counter
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path

from .config import Settings, load_settings
from .exness import schema
from .exness.client import ExnessClient
from .exness.errors import ExnessError

SAMPLE_PREFIXES = ("EURUSD", "XAUUSD", "BTCUSD")
SAMPLE_TIMEFRAMES = ("M15", "H1", "H4")

WsListen = Callable[[ExnessClient, str, list[dict], float], Awaitable[list]]


async def listen_ws(client: ExnessClient, path: str, subscriptions: list[dict], seconds: float) -> list:
    """Akisa baglanir, abone olur ve `seconds` boyunca gelen mesajlari toplar."""
    from websockets.asyncio.client import connect

    url, headers = await client.ws_endpoint(path)
    messages: list = []
    async with connect(url, additional_headers=headers, open_timeout=15) as socket:
        for message in subscriptions:
            await socket.send(json.dumps(message))
        deadline = time.monotonic() + seconds
        while (remaining := deadline - time.monotonic()) > 0 and len(messages) < 2000:
            try:
                raw = await asyncio.wait_for(socket.recv(), timeout=remaining)
            except asyncio.TimeoutError:
                break
            try:
                messages.append(json.loads(raw))
            except (ValueError, TypeError):
                messages.append({"_unparsed": str(raw)[:500]})
    return messages


def _write(folder: Path, name: str, data) -> None:
    target = folder / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8")


async def run(settings: Settings, out_root: Path | None = None, *, client: ExnessClient | None = None,
              seconds: float = 30.0, ws_listen: WsListen = listen_ws, now: float | None = None) -> Path:
    now = time.time() if now is None else now
    stamp = datetime.fromtimestamp(now, timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = (out_root or settings.db_path.parent / "discovery") / stamp
    folder.mkdir(parents=True, exist_ok=True)
    client = client or ExnessClient(settings)
    account_id = client.account_id
    errors: dict[str, str] = {}
    summary: dict = {"started_at": stamp, "errors": errors}

    async def fetch(name: str, path: str):
        try:
            data = await client.get(path)
        except (ExnessError, ValueError) as exc:
            errors[name] = f"{type(exc).__name__}: {exc}"
            return None
        _write(folder, name + ".json", data)
        return data

    try:
        try:
            summary["access_point"] = await client.resolve_host()
        except ExnessError as exc:
            errors["access_point"] = f"{type(exc).__name__}: {exc}"
            _write(folder, "summary.json", summary)
            return folder

        account = await fetch("account", schema.account_path(account_id))
        limits_raw = await fetch("limits", schema.limits_path(account_id))
        limits = schema.parse_limits(limits_raw)
        if limits.global_rate or limits.methods:
            client.limiter.configure(global_rate=limits.global_rate, methods=limits.methods)
        summary["limits"] = {"global_rate": limits.global_rate, "max_candles": limits.max_candles,
                             "history_range_days": limits.history_range_days,
                             "history_age_days": limits.history_age_days}
        snapshot = await fetch("snapshot", schema.snapshot_path(account_id))
        if account and snapshot:
            try:
                parsed = schema.parse_account(account, snapshot.get("account_state"))
                summary["account"] = {"currency": parsed.currency, "can_open": parsed.can_open,
                                      "leverage": parsed.leverage}
            except ValueError as exc:
                errors["account_parse"] = str(exc)

        names = schema.parse_instrument_names(await fetch("instruments", schema.instruments_path(account_id)))
        summary["instrument_count"] = len(names)
        kinds: Counter = Counter()
        categories: Counter = Counter()
        universe: list[str] = []
        for name in names:
            try:
                path = schema.instrument_path(account_id, name)
            except ValueError as exc:
                errors[f"conditions/{name}"] = str(exc)
                continue
            raw = await fetch(f"conditions/{name}", path)
            if raw is None:
                continue
            categories[str(raw.get("category"))] += 1
            try:
                instrument = schema.parse_instrument(raw)
            except ValueError as exc:
                errors[f"parse/{name}"] = str(exc)
                continue
            kinds[instrument.kind] += 1
            if instrument.kind != "other" and instrument.tradable:
                universe.append(name)
        summary.update(kinds=dict(kinds), categories=dict(categories), universe=universe)

        samples = [next((n for n in names if n.upper().startswith(prefix)), None) for prefix in SAMPLE_PREFIXES]
        samples = [s for s in samples if s]
        summary["samples"] = samples
        for symbol in samples:
            for timeframe in SAMPLE_TIMEFRAMES:
                await fetch(f"candles/{symbol}_{timeframe}",
                            schema.candles_path(account_id, symbol, timeframe, now, count=-20))
        await fetch("deals", schema.deals_path(account_id, start=now - 86400, end=now, limit=200))

        for name, path, subscriptions in (
            ("ws_ticks", schema.ticks_ws_path(account_id), [schema.subscribe_ticks("discover-ticks", samples)]),
            ("ws_events", schema.events_ws_path(account_id),
             [schema.subscribe_events("discover-tx", "transactions"),
              schema.subscribe_events("discover-acc", "account_state")]),
        ):
            if name == "ws_ticks" and not samples:
                continue
            try:
                messages = await ws_listen(client, path, subscriptions, seconds if name == "ws_ticks" else 8.0)
                _write(folder, name + ".json", messages)
                summary[name + "_messages"] = len(messages)
            except Exception as exc:  # kesif betigi: her hata kaydedilir, sirlar hata metninde yer almaz
                errors[name] = f"{type(exc).__name__}: {exc}"
    finally:
        _write(folder, "summary.json", summary)
        await client.aclose()
    return folder


def make_zip(folder: Path) -> Path:
    archive = folder.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for item in sorted(folder.rglob("*.json")):
            bundle.write(item, item.relative_to(folder.parent))
    return archive


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Exness API salt-okuma kesfi")
    parser.add_argument("--out", type=Path, default=None, help="cikti kok klasoru")
    parser.add_argument("--seconds", type=float, default=30.0, help="tick dinleme suresi")
    args = parser.parse_args(argv)
    try:
        settings = load_settings()
    except ValueError as exc:
        print(f"Ayar hatasi: {exc}", file=sys.stderr)
        return 2
    folder = asyncio.run(run(settings, args.out, seconds=args.seconds))
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    archive = make_zip(folder)
    print(f"Kesif tamam: {folder}")
    print(f"Zip: {archive}")
    print(f"Enstruman: {summary.get('instrument_count')}  Evren: {len(summary.get('universe', []))}"
          f"  Hata: {len(summary.get('errors', {}))}")
    for name, message in summary.get("errors", {}).items():
        print(f"  ! {name}: {message}")
    return 0 if not summary.get("errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())
