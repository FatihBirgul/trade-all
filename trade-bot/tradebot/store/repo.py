"""Botun kalici durumu: islemler, emirler, olaylar, ayarlar."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from ..config import BotSettings
from .db import connect, transaction

log = logging.getLogger(__name__)

Origin = Literal["bot", "manual"]
_TRADE_BOOLS = ("user_sl_override", "manage", "be_done", "partial_done")
_STATE_FIELDS = ("halted", "halt_reason", "stopped", "start_capital", "start_at", "last_scan_at",
                 "heartbeat_at")


@dataclass
class Trade:
    """`trades` satirinin birebir karsiligi. `pnl` o ana kadar gerceklesen toplamdir."""

    position_id: str
    origin: str
    symbol: str  # kanonik ad
    side: str
    volume: float  # kalan hacim
    entry: float
    sl: float | None = None
    tp1: float | None = None
    tp2: float | None = None
    initial_risk_r_price: float | None = None  # |giris - ilk SL| (fiyat cinsinden 1R)
    strategy_id: str | None = None
    setup_id: str | None = None
    score: float | None = None
    opened_at: float = 0.0
    closed_at: float | None = None
    close_price: float | None = None
    pnl: float = 0.0
    user_sl_override: bool = False
    manage: bool = True
    initial_volume: float | None = None
    sltp_order_id: str | None = None
    be_done: bool = False
    partial_done: bool = False
    risk_amount: float | None = None
    last_sl: float | None = None  # broker'in en son onayladigi SL; emir iptal olsa da kalir
    planned_tp: float | None = None  # planlanan TP; broker'daki kaybolursa yeniden kurulur
    votes_json: str | None = None  # giristeki modul oylari: {"modul": 1 | 0 | -1}
    id: int | None = None

    @property
    def is_open(self) -> bool:
        return self.closed_at is None


@dataclass(frozen=True)
class BotState:
    halted: bool  # toplam kayip siniri: bilincli onayla devam edilir
    halt_reason: str | None
    stopped: bool  # kullanicinin acil durdurmasi
    start_capital: float | None
    start_at: float | None
    last_scan_at: float | None
    heartbeat_at: float | None = None  # servis dongusunun son canlilik isareti


_TRADE_COLUMNS = [f.name for f in fields(Trade) if f.name != "id"]


def _trade(row: sqlite3.Row) -> Trade:
    values = {name: row[name] for name in _TRADE_COLUMNS}
    for name in _TRADE_BOOLS:
        values[name] = bool(values[name])
    return Trade(id=row["id"], **values)


class Repo:
    def __init__(self, db_path: Path | str, *, clock: Callable[[], float] = time.time):
        self.db_path = db_path
        self.conn = connect(db_path)
        self._clock = clock

    def close(self) -> None:
        self.conn.close()

    # ---------------------------------------------------------------- islemler
    def upsert_trade(self, trade: Trade) -> Trade:
        values = asdict(trade)
        values.pop("id")
        for name in _TRADE_BOOLS:
            values[name] = int(bool(values[name]))
        columns = ", ".join(_TRADE_COLUMNS)
        marks = ", ".join(":" + name for name in _TRADE_COLUMNS)
        updates = ", ".join(f"{name} = excluded.{name}" for name in _TRADE_COLUMNS if name != "position_id")
        self.conn.execute(
            f"INSERT INTO trades ({columns}) VALUES ({marks}) "
            f"ON CONFLICT (position_id) DO UPDATE SET {updates}", values)
        saved = self.get_trade(trade.position_id)
        assert saved is not None
        trade.id = saved.id
        return saved

    def get_trade(self, position_id: str) -> Trade | None:
        row = self.conn.execute("SELECT * FROM trades WHERE position_id = ?", (str(position_id),)).fetchone()
        return _trade(row) if row else None

    def trade_by_setup(self, setup_id: str) -> Trade | None:
        row = self.conn.execute("SELECT * FROM trades WHERE setup_id = ?", (setup_id,)).fetchone()
        return _trade(row) if row else None

    def open_trades(self, origin: Origin | None = None) -> list[Trade]:
        sql = "SELECT * FROM trades WHERE closed_at IS NULL"
        args: tuple = ()
        if origin is not None:
            sql, args = sql + " AND origin = ?", (origin,)
        return [_trade(r) for r in self.conn.execute(sql + " ORDER BY id", args)]

    def closed_trades(self, *, since: float | None = None, limit: int = 200) -> list[Trade]:
        rows = self.conn.execute(
            "SELECT * FROM trades WHERE closed_at IS NOT NULL AND closed_at >= ? ORDER BY closed_at DESC LIMIT ?",
            (since if since is not None else 0.0, int(limit)))
        return [_trade(r) for r in rows]

    def close_trade(self, position_id: str, *, close_price: float | None, closed_at: float | None = None) -> None:
        self.conn.execute(
            "UPDATE trades SET closed_at = ?, close_price = ?, volume = 0 WHERE position_id = ? AND closed_at IS NULL",
            (closed_at if closed_at is not None else self._clock(), close_price, str(position_id)))

    def update_trade(self, position_id: str, **changes: Any) -> bool:
        """Yalnizca verilen alanlari, yalnizca islem hala aciksa gunceller.

        Bellekteki eski bir `Trade` nesnesini geri yazmak yerine kullanilir: araya giren bir olay
        islemi kapatmis ya da degistirmis olabilir.
        """
        unknown = set(changes) - set(_TRADE_COLUMNS)
        if unknown or not changes:
            raise ValueError("gecersiz islem alani: " + ", ".join(sorted(unknown)))
        for name in _TRADE_BOOLS:
            if name in changes:
                changes[name] = int(bool(changes[name]))
        assignments = ", ".join(f"{name} = ?" for name in changes)
        cursor = self.conn.execute(
            f"UPDATE trades SET {assignments} WHERE position_id = ? AND closed_at IS NULL",
            [*changes.values(), str(position_id)])
        return cursor.rowcount == 1

    def reopen_trade(self, position_id: str, volume: float) -> None:
        """Yanlislikla kapatilmis sayilan (broker'da hala acik) islemi yeniden acar."""
        self.conn.execute(
            "UPDATE trades SET closed_at = NULL, close_price = NULL, volume = ? WHERE position_id = ?",
            (float(volume), str(position_id)))

    def add_realized(self, position_id: str, deal_id: str, at: float, pnl: float) -> bool:
        """Kapanis deal'ini bir kez kaydeder; yeni kayitsa True."""
        trade = self.get_trade(position_id)
        if trade is None:
            return False
        with transaction(self.conn):
            cursor = self.conn.execute(
                "INSERT OR IGNORE INTO realized (deal_id, trade_id, at, pnl) VALUES (?, ?, ?, ?)",
                (str(deal_id), trade.id, float(at), float(pnl)))
            if cursor.rowcount == 0:
                return False
            self.conn.execute(
                "UPDATE trades SET pnl = (SELECT COALESCE(SUM(pnl), 0) FROM realized WHERE trade_id = ?) "
                "WHERE id = ?", (trade.id, trade.id))
        return True

    def realized_pnl(self, origin: Origin | None = None, since: float | None = None, *,
                     after: float | None = None) -> float:
        """`since` dahil (>=), `after` haric (>) alt sinirdir."""
        sql = "SELECT COALESCE(SUM(r.pnl), 0) FROM realized r JOIN trades t ON t.id = r.trade_id WHERE r.at >= ?"
        args: list = [since if since is not None else 0.0]
        if after is not None:
            sql += " AND r.at > ?"
            args.append(after)
        if origin is not None:
            sql += " AND t.origin = ?"
            args.append(origin)
        return float(self.conn.execute(sql, args).fetchone()[0])

    def bot_realized_pnl(self, since: float | None = None) -> float:
        return self.realized_pnl("bot", since)

    def pnl_by_period(self, period: Literal["day", "week", "month"],
                      origin: Literal["bot", "manual", "all"] = "all", *, since: float | None = None) -> list[dict]:
        if period not in ("day", "week", "month"):
            raise ValueError("period day, week ya da month olmali")
        sql = ("SELECT r.at, r.pnl, r.trade_id FROM realized r JOIN trades t ON t.id = r.trade_id "
               "WHERE r.at >= ?")
        args: list = [since if since is not None else 0.0]
        if origin != "all":
            sql += " AND t.origin = ?"
            args.append(origin)
        buckets: dict[str, dict] = {}
        for at, pnl, trade_id in self.conn.execute(sql + " ORDER BY r.at", args):
            moment = datetime.fromtimestamp(at, timezone.utc)
            if period == "day":
                key = moment.strftime("%Y-%m-%d")
            elif period == "month":
                key = moment.strftime("%Y-%m")
            else:
                iso = moment.isocalendar()
                key = f"{iso.year}-W{iso.week:02d}"
            bucket = buckets.setdefault(key, {"period": key, "pnl": 0.0, "trades": set()})
            bucket["pnl"] += pnl
            bucket["trades"].add(trade_id)
        return [{"period": b["period"], "pnl": round(b["pnl"], 10), "trades": len(b["trades"])}
                for b in buckets.values()]

    # ---------------------------------------------------------------- emirler
    def insert_order(self, idempotency_key: str, *, kind: str, payload: dict, setup_id: str | None = None,
                     origin: str = "bot", position_id: str | None = None) -> bool:
        """Yeni emir kaydi; ayni anahtar zaten varsa False (yeniden gonderilmez)."""
        now = self._clock()
        cursor = self.conn.execute(
            "INSERT OR IGNORE INTO orders (idempotency_key, setup_id, kind, origin, state, position_id, "
            "payload_json, created_at, updated_at) VALUES (?, ?, ?, ?, 'PENDING', ?, ?, ?, ?)",
            (idempotency_key, setup_id, kind, origin, position_id, json.dumps(payload), now, now))
        return cursor.rowcount == 1

    def update_order_state(self, idempotency_key: str, state: str, *, operation_id: str | None = None,
                           position_id: str | None = None, error: str | None = None) -> None:
        self.conn.execute(
            "UPDATE orders SET state = ?, operation_id = COALESCE(?, operation_id), "
            "position_id = COALESCE(?, position_id), error = COALESCE(?, error), updated_at = ? "
            "WHERE idempotency_key = ?",
            (state, operation_id, position_id, error, self._clock(), idempotency_key))

    @staticmethod
    def _order(row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        order = dict(row)
        order["payload"] = json.loads(order.pop("payload_json"))
        return order

    def get_order(self, idempotency_key: str) -> dict | None:
        return self._order(self.conn.execute(
            "SELECT * FROM orders WHERE idempotency_key = ?", (idempotency_key,)).fetchone())

    def order_by_operation(self, operation_id: str) -> dict | None:
        return self._order(self.conn.execute(
            "SELECT * FROM orders WHERE operation_id = ?", (str(operation_id),)).fetchone())

    def orders_for_position(self, position_id: str, kind: str | None = None, limit: int = 20) -> list[dict]:
        """Pozisyona ait emirler, yeniden eskiye."""
        sql, args = "SELECT * FROM orders WHERE position_id = ?", [str(position_id)]
        if kind is not None:
            sql += " AND kind = ?"
            args.append(kind)
        rows = self.conn.execute(sql + " ORDER BY created_at DESC, rowid DESC LIMIT ?", args + [int(limit)])
        return [self._order(r) for r in rows]

    def orders_in(self, states: Iterable[str]) -> list[dict]:
        states = list(states)
        marks = ", ".join("?" for _ in states)
        rows = self.conn.execute(
            f"SELECT * FROM orders WHERE state IN ({marks}) ORDER BY created_at, idempotency_key", states)
        return [self._order(r) for r in rows]

    # ---------------------------------------------------------------- olaylar
    def add_event(self, level: str, kind: str, message: str, data: dict | None = None, *,
                  at: float | None = None) -> int:
        cursor = self.conn.execute(
            "INSERT INTO events (at, level, kind, message, data_json) VALUES (?, ?, ?, ?, ?)",
            (at if at is not None else self._clock(), level, kind, message,
             json.dumps(data) if data is not None else None))
        return int(cursor.lastrowid)

    def events(self, *, after: int = 0, limit: int = 200, newest: bool = False) -> list[dict]:
        order = "DESC" if newest else "ASC"
        rows = self.conn.execute(
            f"SELECT * FROM events WHERE id > ? ORDER BY id {order} LIMIT ?", (int(after), int(limit))).fetchall()
        return [{"id": r["id"], "at": r["at"], "level": r["level"], "kind": r["kind"], "message": r["message"],
                 "data": json.loads(r["data_json"]) if r["data_json"] else None} for r in rows]

    def events_since(self, since: float, kinds: tuple[str, ...]) -> list[dict]:
        """`since` anindan sonraki, verilen turlerdeki olaylar (eskiden yeniye)."""
        marks = ",".join("?" for _ in kinds)
        rows = self.conn.execute(
            f"SELECT * FROM events WHERE at >= ? AND kind IN ({marks}) ORDER BY id", (float(since), *kinds)).fetchall()
        return [{"id": r["id"], "at": r["at"], "level": r["level"], "kind": r["kind"], "message": r["message"],
                 "data": json.loads(r["data_json"]) if r["data_json"] else None} for r in rows]

    # ---------------------------------------------------------------- ayarlar ve durum
    def apply_balance_op(self, deal_id: str, at: float, amount: float, *, apply: bool) -> tuple[bool, float | None]:
        """Para yatirma/cekme deal'ini bir kez kaydeder -> (yeni mi, yeni taban).

        `apply` ise tutar sermaye tabanina eklenir ve yeni taban doner; degilse taban None'dir. Deal daha
        once islenmisse (False, None). Kayit ile taban guncellemesi tek islemdedir: ayrilamaz.
        """
        with transaction(self.conn):
            cursor = self.conn.execute(
                "INSERT OR IGNORE INTO balance_ops (deal_id, at, amount, applied) VALUES (?, ?, ?, ?)",
                (deal_id, float(at), float(amount), 1 if apply else 0))
            if cursor.rowcount == 0:
                return False, None
            if not apply:
                return True, None
            row = self.conn.execute("SELECT start_capital FROM bot_state WHERE id = 1").fetchone()
            base = max((row[0] or 0.0) + float(amount), 0.0)
            self.conn.execute("UPDATE bot_state SET start_capital = ? WHERE id = 1", (base,))
            return True, base

    def balance_ops(self) -> list[dict]:
        rows = self.conn.execute("SELECT deal_id, at, amount, applied FROM balance_ops ORDER BY at").fetchall()
        return [{"deal_id": r[0], "at": r[1], "amount": r[2], "applied": bool(r[3])} for r in rows]

    def get_setting(self, key: str, default: Any = None) -> Any:
        row = self.conn.execute("SELECT value_json FROM settings WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_setting(self, key: str, value: Any) -> None:
        self.conn.execute(
            "INSERT INTO settings (key, value_json) VALUES (?, ?) "
            "ON CONFLICT (key) DO UPDATE SET value_json = excluded.value_json", (key, json.dumps(value)))

    def append_spreads(self, samples: dict[str, list[tuple[float, float]]], cutoff: float,
                       account_id: str = "") -> None:
        """Yeni spread orneklerini ekler, `cutoff`tan eskileri siler (tek islem)."""
        rows = [(symbol, float(at), float(spread)) for symbol, items in samples.items() for at, spread in items]
        with transaction(self.conn):
            if self.get_setting("spread_ticks_account", "") != account_id:
                self.conn.execute("DELETE FROM spread_ticks")  # baska hesabin spread profili kullanilmaz
                self.set_setting("spread_ticks_account", account_id)
            self.conn.executemany("INSERT INTO spread_ticks (symbol, at, spread) VALUES (?, ?, ?)", rows)
            self.conn.execute("DELETE FROM spread_ticks WHERE at < ?", (float(cutoff),))

    def load_spreads(self, since: float, account_id: str = "") -> dict[str, list[tuple[float, float]]]:
        """`since`ten yeni ornekler. Baska bir hesap icin saklanmissa hic yuklenmez."""
        if self.get_setting("spread_ticks_account", "") != account_id:
            return {}
        out: dict[str, list[tuple[float, float]]] = {}
        for symbol, at, spread in self.conn.execute(
                "SELECT symbol, at, spread FROM spread_ticks WHERE at >= ? ORDER BY at", (float(since),)):
            out.setdefault(symbol, []).append((at, spread))
        return out

    def get_bot_settings(self) -> BotSettings:
        raw = self.get_setting("bot_settings")
        if raw is None:
            return BotSettings()
        try:
            return BotSettings.model_validate(raw)
        except ValidationError as exc:
            # Daha yeni bir surumun yazdigi, bu surumun tanimadigi alanlar (surum geri alindiginda olur) botu
            # dusurmemeli: yalnizca TANINMAYAN alanlar atilir. Baska her dogrulama hatasi aynen yukselir.
            extras = [error["loc"] for error in exc.errors() if error["type"] == "extra_forbidden"]
            if not extras or len(extras) != len(exc.errors()):
                raise
            for path in extras:
                node = raw
                for key in path[:-1]:
                    node = node[key]
                node.pop(path[-1], None)
            log.warning("ayarlarda taninmayan alanlar yok sayildi: %s", [".".join(map(str, p)) for p in extras])
            return BotSettings.model_validate(raw)

    def set_bot_settings(self, settings: BotSettings) -> None:
        self.set_setting("bot_settings", settings.model_dump(mode="json"))

    def bot_state(self) -> BotState:
        row = self.conn.execute("SELECT * FROM bot_state WHERE id = 1").fetchone()
        return BotState(halted=bool(row["halted"]), halt_reason=row["halt_reason"], stopped=bool(row["stopped"]),
                        start_capital=row["start_capital"], start_at=row["start_at"],
                        last_scan_at=row["last_scan_at"], heartbeat_at=row["heartbeat_at"])

    def set_bot_state(self, **changes: Any) -> None:
        unknown = set(changes) - set(_STATE_FIELDS)
        if unknown:
            raise ValueError("bilinmeyen durum alani: " + ", ".join(sorted(unknown)))
        for name in ("halted", "stopped"):
            if name in changes:
                changes[name] = int(bool(changes[name]))
        if changes:
            assignments = ", ".join(f"{name} = ?" for name in changes)
            self.conn.execute(f"UPDATE bot_state SET {assignments} WHERE id = 1", list(changes.values()))

    def add_equity(self, at: float, balance: float, equity: float) -> None:
        self.conn.execute("INSERT OR REPLACE INTO equity (at, balance, equity) VALUES (?, ?, ?)",
                          (float(at), float(balance), float(equity)))

    def equity_series(self, since: float | None = None) -> list[dict]:
        rows = self.conn.execute("SELECT at, balance, equity FROM equity WHERE at >= ? ORDER BY at",
                                 (since if since is not None else 0.0,))
        return [{"at": r[0], "balance": r[1], "equity": r[2]} for r in rows]

    def realized_rows(self, origin: Origin | None = None) -> list[tuple[float, float]]:
        """(zaman, tutar) sirali gerceklesen kar/zarar kayitlari."""
        sql = "SELECT r.at, r.pnl FROM realized r JOIN trades t ON t.id = r.trade_id"
        args: tuple = ()
        if origin is not None:
            sql, args = sql + " WHERE t.origin = ?", (origin,)
        return [(row[0], row[1]) for row in self.conn.execute(sql + " ORDER BY r.at, r.rowid", args)]

    # ---------------------------------------------------------------- API erisimi ve cihazlar
    def add_token(self, token_hash: str, label: str | None = None, *, at: float | None = None) -> None:
        self.conn.execute("INSERT OR IGNORE INTO api_tokens (token_hash, created_at, label) VALUES (?, ?, ?)",
                          (token_hash, at if at is not None else self._clock(), label))

    def has_token(self, token_hash: str) -> bool:
        return self.conn.execute("SELECT 1 FROM api_tokens WHERE token_hash = ?", (token_hash,)).fetchone() is not None

    def clear_tokens(self) -> int:
        return self.conn.execute("DELETE FROM api_tokens").rowcount

    def add_pair_code(self, code_hash: str, expires_at: float) -> None:
        self.conn.execute("INSERT OR REPLACE INTO pair_codes (code_hash, expires_at, used) VALUES (?, ?, 0)",
                          (code_hash, float(expires_at)))

    def take_pair_code(self, code_hash: str, now: float) -> bool:
        """Kodu tek seferlik kullanir; gecerliyse True."""
        cursor = self.conn.execute(
            "UPDATE pair_codes SET used = 1 WHERE code_hash = ? AND used = 0 AND expires_at >= ?",
            (code_hash, float(now)))
        return cursor.rowcount == 1

    def clear_pair_codes(self) -> None:
        self.conn.execute("DELETE FROM pair_codes")

    def add_device(self, expo_token: str) -> None:
        self.conn.execute("INSERT OR IGNORE INTO devices (expo_token, created_at) VALUES (?, ?)",
                          (expo_token, self._clock()))

    def remove_device(self, expo_token: str) -> None:
        self.conn.execute("DELETE FROM devices WHERE expo_token = ?", (expo_token,))

    def devices(self) -> list[str]:
        return [row[0] for row in self.conn.execute("SELECT expo_token FROM devices ORDER BY created_at, expo_token")]
