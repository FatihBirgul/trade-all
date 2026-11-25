from dataclasses import dataclass, field

from tests.fakes.exness import FakeExness
from tradebot.execution.executor import Executor
from tradebot.exness import schema
from tradebot.market.catalog import InstrumentCatalog
from tradebot.signals.adapter import Candidate
from tradebot.store.repo import Repo


class RecordingNotifier:
    def __init__(self):
        self.sent = []

    async def send(self, kind, title, body, data=None):
        self.sent.append((kind, title, body, data))

    def kinds(self):
        return [item[0] for item in self.sent]


@dataclass
class World:
    fake: FakeExness
    repo: Repo
    catalog: InstrumentCatalog
    notifier: RecordingNotifier
    executor: Executor
    clock: dict = field(default_factory=dict)

    def advance(self, seconds):
        self.clock["now"] += seconds


async def make_world(tmp_path, **fake_args) -> World:
    clock = {"now": 1_800_000_000.0}
    fake = FakeExness(clock=lambda: clock["now"], **fake_args)
    repo = Repo(tmp_path / "bot.db", clock=lambda: clock["now"])
    catalog = InstrumentCatalog(fake)
    await catalog.refresh()
    notifier = RecordingNotifier()
    executor = Executor(fake, repo, notifier, catalog, clock=lambda: clock["now"])

    async def on_event(raw):
        kind, event = schema.parse_ws_event(raw)
        if kind == "transaction":
            await executor.on_transaction(event)

    fake.event_listeners.append(on_event)
    await fake.set_price("EURUSD", 1.1000, 1.1002)
    await fake.set_price("XAUUSD", 2000.00, 2000.20)
    await fake.set_price("BTCUSD", 60000.0, 60010.0)
    return World(fake, repo, catalog, notifier, executor, clock)


def candidate(symbol="EURUSD", side="BUY", setup="setup000000000000000001", lots=0.10, entry=1.1002,
              sl=1.0972, tp1=1.1062, tp2=1.1092):
    return Candidate(symbol=symbol, side=side, entry=entry, stop_loss=sl, take_profit_1=tp1, take_profit_2=tp2,
                     lots=lots, strategy_id="fx_trend_momentum_v6", setup_id=setup, net_rr=2.0,
                     analysis_id="a" * 64, risk_amount=30.0)
