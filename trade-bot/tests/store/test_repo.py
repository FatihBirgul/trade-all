import sqlite3
from datetime import datetime, timezone

import pytest

from tradebot.config import BotSettings
from tradebot.store.repo import Repo, Trade


def ts(*args):
    return datetime(*args, tzinfo=timezone.utc).timestamp()


def trade(position_id, origin="bot", **extra):
    values = dict(position_id=position_id, origin=origin, symbol="EURUSD", side="BUY", volume=0.1, entry=1.1,
                  sl=1.09, tp1=1.12, tp2=1.13, initial_risk_r_price=0.01, opened_at=ts(2026, 12, 14, 10))
    values.update(extra)
    return Trade(**values)


@pytest.fixture
def repo(tmp_path):
    return Repo(tmp_path / "bot.db")


def test_migrations_idempotent(tmp_path):
    path = tmp_path / "bot.db"
    first = Repo(path)
    first.upsert_trade(trade("1"))
    first.set_setting("x", {"a": 1})
    first.close()
    second = Repo(path)
    second = Repo(path)
    assert [t.position_id for t in second.open_trades()] == ["1"]
    assert second.get_setting("x") == {"a": 1}
    assert second.conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"


def test_trade_roundtrip_and_upsert_by_position(repo):
    saved = repo.upsert_trade(trade("1", strategy_id="fx_trend_momentum_v6", setup_id="s1", sltp_order_id="77"))
    assert saved.id is not None
    loaded = repo.get_trade("1")
    assert loaded == saved and loaded.manage is True and loaded.user_sl_override is False
    loaded.sl, loaded.volume, loaded.be_done = 1.1001, 0.05, True
    again = repo.upsert_trade(loaded)
    assert again.id == saved.id and repo.get_trade("1").sl == 1.1001 and repo.get_trade("1").be_done is True
    assert len(repo.open_trades()) == 1
    assert repo.get_trade("404") is None


def test_setup_id_unique(repo):
    repo.upsert_trade(trade("1", setup_id="s1"))
    with pytest.raises(sqlite3.IntegrityError):
        repo.upsert_trade(trade("2", setup_id="s1"))
    repo.upsert_trade(trade("3"))  # setup_id'siz (manual) islemler serbest
    repo.upsert_trade(trade("4"))
    assert repo.trade_by_setup("s1").position_id == "1" and repo.trade_by_setup("zz") is None


def test_origin_is_checked(repo):
    with pytest.raises(sqlite3.IntegrityError):
        repo.upsert_trade(trade("1", origin="robot"))


def test_open_trades_filters_origin_and_closed(repo):
    repo.upsert_trade(trade("1"))
    repo.upsert_trade(trade("2", origin="manual"))
    repo.upsert_trade(trade("3"))
    repo.close_trade("3", close_price=1.12, closed_at=ts(2026, 12, 14, 12))
    assert [t.position_id for t in repo.open_trades()] == ["1", "2"]
    assert [t.position_id for t in repo.open_trades("bot")] == ["1"]
    assert [t.position_id for t in repo.open_trades("manual")] == ["2"]
    closed = repo.get_trade("3")
    assert closed.closed_at == ts(2026, 12, 14, 12) and closed.close_price == 1.12 and closed.volume == 0.0


def test_realized_is_deduplicated_by_deal(repo):
    repo.upsert_trade(trade("1"))
    assert repo.add_realized("1", "d1", ts(2026, 12, 14, 11), 5.0) is True
    assert repo.add_realized("1", "d1", ts(2026, 12, 14, 11), 5.0) is False  # WS + mutabakat ayni deal'i getirir
    assert repo.add_realized("1", "d2", ts(2026, 12, 14, 12), -2.0) is True
    assert repo.get_trade("1").pnl == pytest.approx(3.0)
    assert repo.add_realized("404", "d9", ts(2026, 12, 14, 12), 1.0) is False


def test_bot_realized_pnl_excludes_manual(repo):
    repo.upsert_trade(trade("1"))
    repo.upsert_trade(trade("2", origin="manual"))
    repo.add_realized("1", "d1", ts(2026, 12, 13, 23, 59), -10.0)
    repo.add_realized("1", "d2", ts(2026, 12, 14, 0, 1), -4.0)
    repo.add_realized("2", "d3", ts(2026, 12, 14, 9), -100.0)
    assert repo.bot_realized_pnl() == pytest.approx(-14.0)
    assert repo.bot_realized_pnl(since=ts(2026, 12, 14)) == pytest.approx(-4.0)
    assert repo.bot_realized_pnl(since=ts(2026, 12, 15)) == 0.0
    assert repo.realized_pnl("manual") == pytest.approx(-100.0)


def test_pnl_by_period_groups_utc_days(repo):
    repo.upsert_trade(trade("1", strategy_id="a"))
    repo.upsert_trade(trade("2", origin="manual"))
    repo.upsert_trade(trade("3", strategy_id="b", symbol="XAUUSD"))
    repo.add_realized("1", "d1", ts(2026, 12, 13, 23, 59, 59), 10.0)
    repo.add_realized("1", "d2", ts(2026, 12, 14, 0, 0, 0), -4.0)
    repo.add_realized("2", "d3", ts(2026, 12, 14, 9), 7.0)
    repo.add_realized("3", "d4", ts(2026, 12, 21, 9), 1.0)
    days = repo.pnl_by_period("day", "bot")
    assert [(d["period"], d["pnl"]) for d in days] == [("2026-12-13", 10.0), ("2026-12-14", -4.0), ("2026-12-21", 1.0)]
    assert [(d["period"], d["pnl"]) for d in repo.pnl_by_period("day", "manual")] == [("2026-12-14", 7.0)]
    assert [(d["period"], d["pnl"]) for d in repo.pnl_by_period("day", "all")][1] == ("2026-12-14", 3.0)
    weeks = repo.pnl_by_period("week", "all")
    assert [(w["period"], w["pnl"]) for w in weeks] == [("2026-W50", 10.0), ("2026-W51", 3.0), ("2026-W52", 1.0)]
    months = repo.pnl_by_period("month", "all")
    assert [(m["period"], m["pnl"]) for m in months] == [("2026-12", 14.0)]
    with pytest.raises(ValueError):
        repo.pnl_by_period("year", "all")


def test_orders_state_machine(repo):
    assert repo.insert_order("bot-s1", kind="open", setup_id="s1", origin="bot", payload={"v": 1}) is True
    assert repo.insert_order("bot-s1", kind="open", setup_id="s1", origin="bot", payload={"v": 2}) is False
    order = repo.get_order("bot-s1")
    assert (order["state"], order["payload"], order["kind"]) == ("PENDING", {"v": 1}, "open")
    repo.update_order_state("bot-s1", "ACKED", operation_id="789")
    assert repo.order_by_operation("789")["idempotency_key"] == "bot-s1"
    assert [o["idempotency_key"] for o in repo.orders_in(["ACKED", "UNKNOWN"])] == ["bot-s1"]
    repo.update_order_state("bot-s1", "FILLED", position_id="2001")
    assert repo.get_order("bot-s1")["position_id"] == "2001" and repo.orders_in(["ACKED"]) == []
    with pytest.raises(sqlite3.IntegrityError):
        repo.update_order_state("bot-s1", "DONE")
    assert repo.get_order("nope") is None


def test_events_and_paging(repo):
    first = repo.add_event("info", "trade_opened", "EURUSD BUY", {"symbol": "EURUSD"}, at=100.0)
    second = repo.add_event("error", "order_rejected", "red", at=101.0)
    assert second > first
    events = repo.events()
    assert [e["kind"] for e in events] == ["trade_opened", "order_rejected"]
    assert events[0]["data"] == {"symbol": "EURUSD"} and events[1]["data"] is None
    assert [e["id"] for e in repo.events(after=first)] == [second]
    assert [e["id"] for e in repo.events(limit=1, newest=True)] == [second]


def test_settings_and_bot_settings(repo):
    assert repo.get_setting("missing", 5) == 5
    assert repo.get_bot_settings() == BotSettings()
    changed = BotSettings(dry_run=False, enabled_symbols={"EURUSD"})
    repo.set_bot_settings(changed)
    assert repo.get_bot_settings() == changed


def test_bot_state_defaults_and_updates(repo):
    state = repo.bot_state()
    assert (state.halted, state.stopped, state.halt_reason, state.start_capital, state.last_scan_at) == \
        (False, False, None, None, None)
    repo.set_bot_state(start_capital=3000.0, start_at=10.0)
    repo.set_bot_state(halted=True, halt_reason="toplam kayip siniri")
    state = repo.bot_state()
    assert (state.halted, state.halt_reason, state.start_capital, state.start_at) == \
        (True, "toplam kayip siniri", 3000.0, 10.0)
    with pytest.raises(ValueError):
        repo.set_bot_state(nope=1)


def test_equity_series(repo):
    repo.add_equity(10.0, 3000.0, 3001.0)
    repo.add_equity(20.0, 3000.0, 2990.0)
    assert repo.equity_series(since=15.0) == [{"at": 20.0, "balance": 3000.0, "equity": 2990.0}]
    assert len(repo.equity_series()) == 2


def test_closed_trades_listing(repo):
    repo.upsert_trade(trade("1"))
    repo.upsert_trade(trade("2"))
    repo.close_trade("1", close_price=1.2, closed_at=50.0)
    repo.close_trade("2", close_price=1.0, closed_at=60.0)
    assert [t.position_id for t in repo.closed_trades(limit=10)] == ["2", "1"]
    assert [t.position_id for t in repo.closed_trades(since=55.0)] == ["2"]


def test_settings_written_by_older_or_newer_versions_still_load(tmp_path):
    """Eski kayitta yeni alanlar yoktur (varsayilan: acik). Daha yeni bir surumun yazdigi taninmayan alanlar
    (surum geri alindiginda) botu dusurmez; baska her bozuk deger yine hata verir."""
    import pytest
    from pydantic import ValidationError

    from tradebot.config import BotSettings
    from tradebot.store.repo import Repo

    repo = Repo(tmp_path / "bot.db")
    old = BotSettings().model_dump(mode="json")
    for key in ("be_enabled", "partial_enabled", "trail_enabled"):
        old["manage"].pop(key)
    repo.set_setting("bot_settings", old)
    loaded = repo.get_bot_settings()
    assert loaded.manage.be_enabled and loaded.manage.partial_enabled and loaded.manage.trail_enabled

    newer = BotSettings(dry_run=True).model_dump(mode="json")
    newer["manage"]["gelecekteki_anahtar"] = False
    newer["gelecekteki_bolum"] = {"x": 1}
    newer["risk"]["risk_pct"] = 0.75
    repo.set_setting("bot_settings", newer)
    tolerant = repo.get_bot_settings()
    assert tolerant.risk.risk_pct == 0.75 and tolerant.dry_run is True  # bilinen degerler korunur

    broken = BotSettings().model_dump(mode="json")
    broken["risk"]["risk_pct"] = 9.0  # sinir disi: sessizce duzeltilmez
    broken["manage"]["gelecekteki_anahtar"] = False
    repo.set_setting("bot_settings", broken)
    with pytest.raises(ValidationError):
        repo.get_bot_settings()
