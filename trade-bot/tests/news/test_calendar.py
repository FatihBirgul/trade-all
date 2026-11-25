import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from tradebot.news.calendar import FF_URL, REFRESH_SECONDS, STALE_SECONDS, NewsCalendar, parse_calendar
from tradebot.store.repo import Repo

RAW = json.loads((Path(__file__).parent / "fixtures" / "ff_calendar_thisweek.json").read_text())


def ts(*args):
    return datetime(*args, tzinfo=timezone.utc).timestamp()


def make(tmp_path, responder, now=ts(2026, 11, 25, 12)):
    clock = {"now": now}
    repo = Repo(tmp_path / "bot.db", clock=lambda: clock["now"])
    requests = []

    def handle(request):
        requests.append(request)
        return responder(request)

    calendar = NewsCalendar(repo, transport=httpx.MockTransport(handle), clock=lambda: clock["now"])
    return calendar, repo, requests, clock


def test_parse_keeps_valid_and_skips_malformed():
    events = parse_calendar(RAW)
    assert [(e.currency, e.impact) for e in events] == [("JPY", "holiday"), ("AUD", "high"), ("EUR", "high"),
                                                        ("GBP", "medium"), ("USD", "high")]  # zamana gore sirali
    assert {e.title for e in events} == {"Non-Farm Employment Change", "ECB Press Conference", "Retail Sales m/m",
                                         "Bank Holiday", "RBA Rate Statement"}
    assert parse_calendar({"not": "a list"}) == [] and parse_calendar(None) == []


def test_event_times_are_normalised_to_utc():
    by_title = {e.title: e for e in parse_calendar(RAW)}
    assert by_title["Non-Farm Employment Change"].at == ts(2026, 11, 27, 13, 30)  # 08:30 -05:00
    assert by_title["ECB Press Conference"].at == ts(2026, 11, 26, 12, 45)  # 13:45 +01:00
    assert by_title["RBA Rate Statement"].at == ts(2026, 11, 25, 3, 30)  # Z
    assert "Ofsetsiz kayit" not in by_title  # saat dilimi belirsiz kayit kullanilmaz


async def test_refresh_caches_and_survives_restart(tmp_path):
    calendar, repo, requests, clock = make(tmp_path, lambda r: httpx.Response(200, json=RAW))
    assert calendar.events() == [] and calendar.age() is None and calendar.due() is True
    assert await calendar.refresh() is True
    assert str(requests[0].url) == FF_URL and len(calendar.events()) == 5
    assert calendar.age() == 0 and calendar.due() is False
    clock["now"] += REFRESH_SECONDS - 1
    assert calendar.due() is False
    clock["now"] += 2
    assert calendar.due() is True

    again = NewsCalendar(repo, transport=httpx.MockTransport(lambda r: httpx.Response(500)), clock=lambda: clock["now"])
    assert len(again.events()) == 5  # yeniden baslatmada SQLite'tan gelir


async def test_failed_refresh_keeps_last_good_calendar(tmp_path):
    state = {"ok": True}

    def responder(request):
        if state["ok"]:
            return httpx.Response(200, json=RAW)
        return httpx.Response(429, text="slow down")
    calendar, _, requests, clock = make(tmp_path, responder)
    await calendar.refresh()
    state["ok"] = False
    clock["now"] += REFRESH_SECONDS + 1
    assert await calendar.refresh() is False
    assert len(calendar.events()) == 5 and calendar.age() == REFRESH_SECONDS + 1
    assert calendar.due() is False  # basarisiz denemeden sonra hemen yeniden denenmez
    clock["now"] += 901
    assert calendar.due() is True
    assert calendar.stale() is False
    clock["now"] += STALE_SECONDS
    assert calendar.stale() is True


async def test_garbage_response_is_a_failure_not_an_empty_calendar(tmp_path):
    state = {"body": RAW}
    calendar, _, _, clock = make(tmp_path, lambda r: httpx.Response(200, json=state["body"]))
    await calendar.refresh()
    for body in ({"error": "x"}, [], "<html>"):
        state["body"] = body
        clock["now"] += REFRESH_SECONDS + 1000
        assert await calendar.refresh() is False
        assert len(calendar.events()) == 5


async def test_never_fetched_calendar_is_stale_at_once(tmp_path):
    """Hic alinamamis takvim 'eski' degil yoktur: koruma calismaz ve bu hemen gorulmelidir
    (24 saat beklemeden; servis her gun yeniden baslasa da)."""
    def boom(request):
        raise httpx.ConnectError("no route")
    calendar, _, _, clock = make(tmp_path, boom)
    assert calendar.stale() is True and calendar.never_fetched() is True
    assert await calendar.refresh() is False
    assert calendar.stale() is True


async def test_corrupt_stored_event_does_not_break_reading(tmp_path):
    calendar, repo, _, _ = make(tmp_path, lambda request: httpx.Response(200, json=[]))
    repo.set_setting("news_calendar", {"fetched_at": 1.0, "events": [
        {"currency": "USD", "title": "NFP", "at": 5.0, "impact": "high"},
        {"currency": "USD", "title": "eksik alan"},
        {"currency": "EUR", "title": "fazla alan", "at": 6.0, "impact": "high", "yeni": 1}, "bozuk"]})
    assert [e.title for e in calendar.events()] == ["NFP"]