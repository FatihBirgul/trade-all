"""Servis dongusu testleri icin ortak kurulum: FakeExness + sahte akislar + V9 fixture verisi."""
from dataclasses import dataclass, field

from tests.exness.test_client import settings
from tests.execution.helpers import RecordingNotifier
from tests.fakes.exness import FakeExness
from tests.fakes.streams import stream_factory
from tests.signals.helpers import v9_fixtures
from tradebot.app import Bot
from tradebot.config import BotSettings
from tradebot.store.repo import Repo

NOW = 1_800_000_000  # 2027-01-15 Cuma 08:00 UTC
SATURDAY = NOW + 86_400


@dataclass
class App:
    bot: Bot
    fake: FakeExness
    repo: Repo
    notifier: RecordingNotifier
    streams: list
    clock: dict = field(default_factory=dict)
    path: object = None

    def advance(self, seconds):
        self.clock["now"] += seconds

    def kinds(self):
        return [e["kind"] for e in self.repo.events()]


def load_market(fake, symbol, now, direction="BUY"):
    """V9 fixture mumlarini `now` anina kaydirarak sembole yukler; son kapanisi dondurur."""
    data = v9_fixtures().fixture(direction, frames=("M15", "H1", "H4")).data["XAUUSD"]
    shift = now - NOW
    for timeframe, rows in data["candles"].items():
        fake.set_candles(symbol, timeframe, [{**row, "time": row["time"] + shift} for row in rows])
    return data["quote"]["bid"], data["quote"]["ask"]


async def feed_ticks(app_or_fake, symbol, bid, ask, now, count=120):
    fake = getattr(app_or_fake, "fake", app_or_fake)
    for i in range(count):
        await fake.set_price(symbol, bid, ask, at=now - count + i)


def build(tmp_path, *, now=NOW, dry_run=False, fake=None, clock=None, news=None, **fake_args) -> App:
    clock = clock or {"now": float(now)}
    fake = fake or FakeExness(clock=lambda: clock["now"], **fake_args)
    repo = Repo(tmp_path / "bot.db", clock=lambda: clock["now"])
    if repo.get_setting("bot_settings") is None:
        repo.set_bot_settings(BotSettings(dry_run=dry_run))
    notifier = RecordingNotifier()
    factory = stream_factory(fake)
    calendar = news(repo, lambda: clock["now"]) if news is not None else None
    bot = Bot(settings(), fake, repo, notifier, clock=lambda: clock["now"], stream_factory=factory, news=calendar)
    return App(bot, fake, repo, notifier, factory.created, clock, tmp_path)


async def started(tmp_path, *, symbol="XAUUSD", direction="BUY", now=NOW, **kwargs) -> App:
    """Baslatilmis bot + `symbol` icin aday uretecek piyasa verisi."""
    app = build(tmp_path, now=now, **kwargs)
    bid, ask = load_market(app.fake, symbol, now, direction)
    await app.bot.start()
    # Canli modda ilk acilis "sermaye tabani alindi" bildirimini uretir; testler sonrasina bakar.
    app.notifier.sent[:] = [item for item in app.notifier.sent if item[0] != "capital_base"]
    await feed_ticks(app, symbol, bid, ask, now)
    return app


def restart(app: App) -> App:
    """Servis yeniden baslamis gibi: ayni broker ve ayni veritabani dosyasi, yeni surec durumu."""
    app.fake.event_listeners.clear()
    app.fake.tick_listeners.clear()
    app.repo.close()
    return build(app.path, fake=app.fake, clock=app.clock)
