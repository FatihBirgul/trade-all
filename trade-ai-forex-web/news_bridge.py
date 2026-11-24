from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from threading import Lock
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from xml.etree import ElementTree as ET
import re

from fastapi import FastAPI

app = FastAPI(title="Trade AI News - Read Only")

FEED = "https://www.federalreserve.gov/feeds/press_all.xml"
lock = Lock()
cache = None
cache_until = datetime.min.replace(tzinfo=timezone.utc)

PATTERN = re.compile(
    r"fomc|federal open market|monetary policy|"
    r"interest rate|discount rate|federal reserve issues",
    re.I
)


def read_feed():
    now = datetime.now(timezone.utc)
    items = []
    seen = set()
    successful = []
    failed = []

    feeds = [
        (FEED, "Basin Aciklamalari"),
        (
            "https://www.federalreserve.gov/feeds/speeches.xml",
            "Fed Konusmalari"
        )
    ]

    speech_pattern = re.compile(
        r"economic outlook|labor market|monetary policy|"
        r"inflation|employment|interest rate|fomc|"
        r"economic projections|economic conditions",
        re.I
    )

    for feed_url, feed_type in feeds:
        try:
            request = Request(
                feed_url,
                headers={"User-Agent": "Mozilla/5.0 TradeAI-RSS-Reader"}
            )

            with urlopen(request, timeout=12) as response:
                final = urlparse(response.geturl())
                if (
                    final.scheme != "https" or
                    final.hostname != "www.federalreserve.gov"
                ):
                    raise ValueError("Untrusted RSS redirect")

                data = response.read(1000001)

            if len(data) > 1000000:
                raise ValueError("RSS too large")

            if (
                b"<!doctype" in data.lower() or
                b"<!entity" in data.lower()
            ):
                raise ValueError("Unsafe XML")

            root = ET.fromstring(data)

            if root.tag != "rss":
                raise ValueError("Invalid RSS")

            for entry in root.findall("./channel/item"):
                title = (entry.findtext("title") or "").strip()
                category = (entry.findtext("category") or "").strip()
                link = (entry.findtext("link") or "").strip()
                date = (entry.findtext("pubDate") or "").strip()

                if feed_type == "Fed Konusmalari":
                    if not speech_pattern.search(title):
                        continue
                elif (
                    category != "Monetary Policy" and
                    not PATTERN.search(title)
                ):
                    continue

                parsed = urlparse(link)
                if (
                    parsed.scheme != "https" or
                    parsed.hostname != "www.federalreserve.gov"
                ):
                    continue

                try:
                    published = parsedate_to_datetime(date)
                    if published.tzinfo is None:
                        continue
                    published = published.astimezone(timezone.utc)
                except (ValueError, TypeError, IndexError):
                    continue

                if not title or published > now or link in seen:
                    continue

                seen.add(link)

                items.append({
                    "id": link,
                    "title": title,
                    "url": link,
                    "published_at": published.isoformat(),
                    "category": category,
                    "source": (
                        "Federal Reserve Board - Konusmalar"
                        if feed_type == "Fed Konusmalari"
                        else "Federal Reserve Board"
                    )
                })

            successful.append(feed_type)

        except Exception:
            failed.append(feed_type)

    if not successful:
        raise ValueError("All official feeds unavailable")

    items.sort(
        key=lambda x: x["published_at"],
        reverse=True
    )

    return {
        "data_status": "OK",
        "provider": "Federal Reserve Board RSS",
        "retrieved_at": now.isoformat(),
        "items": items[:10],
        "sources_ok": successful,
        "sources_failed": failed,
        "directional_permission": False
    }


@app.get("/api/news")
def news():
    global cache, cache_until

    with lock:
        now = datetime.now(timezone.utc)

        if cache is not None and now < cache_until:
            return cache

        try:
            result = read_feed()
            cache = result
            cache_until = now + timedelta(minutes=5)
            return result
        except Exception:
            return {
                "data_status": "DATA_UNAVAILABLE",
                "provider": "Federal Reserve Board RSS",
                "retrieved_at": None,
                "items": [],
                "directional_permission": False,
                "reason": "Official news feed unavailable"
            }
# TRADE_AI_FED_CALENDAR_V1
from html.parser import HTMLParser
from calendar import monthrange


class _FedCalendarParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.rows = []

    def handle_starttag(self, tag, attrs):
        if tag != "div":
            return
        classes = (dict(attrs).get("class") or "").split()
        row = {"time": [], "title": [], "day": []} if "row" in classes else None
        fields = (
            ("time", "col-xs-2"),
            ("title", "col-xs-7"),
            ("day", "col-xs-3"),
        )
        field = next((k for k, token in fields if token in classes), None)
        self.stack.append((row, field))

    def handle_data(self, data):
        row = next((r for r, _ in reversed(self.stack) if r is not None), None)
        field = next((f for _, f in reversed(self.stack) if f), None)
        if row is not None and field:
            row[field].append(data)

    def handle_endtag(self, tag):
        if tag != "div" or not self.stack:
            return
        row, _ = self.stack.pop()
        if row is not None:
            self.rows.append({
                k: " ".join(" ".join(v).split())
                for k, v in row.items()
            })


_FED_EVENTS = {
    "FOMC Press Conference": ("FOMC Basin Toplantisi", "HIGH"),
    "FOMC Minutes": ("FOMC Toplanti Tutanaklari", "HIGH"),
    "FOMC Meeting": ("FOMC Toplantisi", "HIGH"),
    "Beige Book": ("Fed Beige Book", "MEDIUM"),
}

_calendar_lock = Lock()
_calendar_cache = None
_calendar_until = datetime.min.replace(tzinfo=timezone.utc)


def _fed_eastern_tz(year, month, day):
    from datetime import date

    march_sunday = 8 + (6 - date(year, 3, 8).weekday()) % 7
    november_sunday = 1 + (6 - date(year, 11, 1).weekday()) % 7

    summer = (
        (3, march_sunday) <= (month, day) < (11, november_sunday)
    )

    return timezone(timedelta(hours=-4 if summer else -5))


def _fed_month_events(year, month):
    months = (
        "january", "february", "march", "april",
        "may", "june", "july", "august",
        "september", "october", "november", "december",
    )

    month_name = months[month - 1]
    source = (
        f"https://www.federalreserve.gov/newsevents/"
        f"{year}-{month_name}.htm"
    )

    request = Request(
        source,
        headers={"User-Agent": "Mozilla/5.0 TradeAI-Calendar-Reader"}
    )

    with urlopen(request, timeout=12) as response:
        final = urlparse(response.geturl())
        if (
            final.scheme != "https"
            or final.hostname != "www.federalreserve.gov"
        ):
            raise ValueError("Untrusted calendar redirect")

        content = response.read(300001)

    if len(content) > 300000:
        raise ValueError("Calendar too large")

    html = content.decode("utf-8", errors="replace")

    if (
        "cal-nojs__rowTitle" not in html
        or f"{month_name} {year}" not in html.lower()
    ):
        raise ValueError("Unexpected calendar page")

    parser = _FedCalendarParser()
    parser.feed(html)

    result = []

    for row in parser.rows:
        time_match = re.fullmatch(
            r"(\d{1,2}):(\d\d)\s*([ap])\.m\.",
            row["time"],
            re.I,
        )

        if not time_match or not re.fullmatch(r"\d{1,2}", row["day"]):
            continue

        day = int(row["day"])

        if day < 1 or day > monthrange(year, month)[1]:
            continue

        name = next(
            (
                name for name in _FED_EVENTS
                if re.search(
                    r"\b" + re.escape(name) + r"\b",
                    row["title"],
                    re.I,
                )
            ),
            None,
        )

        if name is None:
            continue

        hour, minute, ampm = time_match.groups()
        hour = int(hour) % 12 + (12 if ampm.lower() == "p" else 0)

        eastern = datetime(
            year, month, day, hour, int(minute),
            tzinfo=_fed_eastern_tz(year, month, day),
        )

        tr_time = eastern.astimezone(timezone(timedelta(hours=3)))
        tr_title, impact = _FED_EVENTS[name]

        result.append({
            "id": f"fed-{year}-{month:02d}-{day:02d}-{hour:02d}{minute}-{name.replace(' ', '-')}",
            "title": name,
            "title_tr": tr_title,
            "impact": impact,
            "scheduled_at": eastern.astimezone(timezone.utc).isoformat(),
            "scheduled_at_tr": tr_time.isoformat(),
            "source_url": source,
        })

    return result, source


@app.get("/api/calendar")
def fed_calendar():
    global _calendar_cache, _calendar_until

    with _calendar_lock:
        now = datetime.now(timezone.utc)

        if _calendar_cache is not None and now < _calendar_until:
            return _calendar_cache

        year, month = now.year, now.month
        months = [
            (year, month),
            (year + (month == 12), month % 12 + 1),
        ]

        items, successful, failed = [], [], []

        for yy, mm in months:
            try:
                records, source = _fed_month_events(yy, mm)
                items.extend(records)
                successful.append(source)
            except Exception:
                failed.append(f"{yy}-{mm:02d}")

        if not successful:
            return {
                "data_status": "DATA_UNAVAILABLE",
                "items": [],
                "sources_failed": failed,
                "scope": "FED_ONLY_NO_CPI_NFP",
                "directional_permission": False,
            }

        upcoming = []

        for item in sorted(items, key=lambda x: x["scheduled_at"]):
            delta = (
                datetime.fromisoformat(item["scheduled_at"]) - now
            ).total_seconds() / 60

            if delta < -30:
                continue

            item["minutes_until"] = round(delta)
            item["news_risk_warning"] = (
                item["impact"] == "HIGH"
                and -30 <= delta <= 120
            )

            upcoming.append(item)

        _calendar_cache = {
            "data_status": "OK" if not failed else "PARTIAL",
            "provider": "Federal Reserve Board Calendar",
            "retrieved_at": now.isoformat(),
            "items": upcoming[:20],
            "sources_ok": successful,
            "sources_failed": failed,
            "scope": "FED_ONLY_NO_CPI_NFP",
            "directional_permission": False,
            "warning_is_advisory_only": True,
        }

        _calendar_until = now + timedelta(minutes=1)

        return _calendar_cache

# TRADE_AI_BLS_FALLBACK_2026
# Official BLS release schedule checked 2026-11-11.
# Static fallback, NOT an automatically refreshed BLS feed.

_BLS_FALLBACK = [
    (2026, 11, 13, "PPI - Uretici Enflasyonu"),
    (2026, 12, 4, "NFP - Tarim Disi Istihdam"),
    (2026, 12, 10, "CPI - Tuketici Enflasyonu"),
    (2026, 12, 15, "PPI - Uretici Enflasyonu"),
]


@app.get("/api/calendar/combined")
def combined_calendar():
    now = datetime.now(timezone.utc)
    fed = fed_calendar()
    items = list(fed.get("items", []))

    for year, month, day, title in _BLS_FALLBACK:
        eastern = datetime(
            year, month, day, 8, 30,
            tzinfo=timezone(timedelta(hours=-5))
        )

        utc = eastern.astimezone(timezone.utc)

        if utc < now - timedelta(minutes=30):
            continue

        turkey = utc.astimezone(
            timezone(timedelta(hours=3))
        )

        items.append({
            "id": f"bls-{year}-{month:02d}-{day:02d}-{title.split(' ')[0]}",
            "title": title,
            "title_tr": title,
            "impact": "HIGH",
            "scheduled_at": utc.isoformat(),
            "scheduled_at_tr": turkey.isoformat(),
            "source_url": (
                f"https://www.bls.gov/schedule/"
                f"{year}/{month:02d}_sched_list.htm"
            ),
            "source_status": "STATIC_VERIFIED_NOT_LIVE",
            "verified_on": "2026-11-11",
            "news_risk_warning": (
                -30 <= (utc - now).total_seconds() / 60 <= 120
            ),
        })

    items.sort(key=lambda x: x["scheduled_at"])

    return {
        "data_status": "PARTIAL",
        "provider": "Federal Reserve + BLS Static Fallback",
        "retrieved_at": now.isoformat(),
        "items": items[:30],
        "sources_ok": fed.get("sources_ok", []),
        "sources_failed": fed.get("sources_failed", []),
        "scope": "FED_LIVE_BLS_STATIC_2026",
        "bls_live": False,
        "bls_verified_on": "2026-11-11",
        "warning_is_advisory_only": True,
        "directional_permission": False,
    }
