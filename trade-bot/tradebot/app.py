"""Servis dongusu: tara -> sinyal -> risk kapisi -> emir -> pozisyon yonetimi.

Zamanlayicilar `run()` icindedir; `on_bar_close`, `manage_tick` ve `heartbeat` tek tek cagrilabilir
oldugu icin testler gercek saat ve ag olmadan tum akisi calistirir.
"""

from __future__ import annotations

import asyncio
import dataclasses
from importlib import metadata
import logging
import math
import json
import os
import re
import sqlite3
import sys
import time
from collections.abc import Callable
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from .config import BotSettings, Settings, strategy_mode
from .execution.executor import Executor
from .execution.reconcile import fetch_all_deals, reconcile, canonical
from . import backtest, forward, week_replica, yeartest
from .store import backup
from .store.repo import Trade
from .exness import schema
from .exness.errors import ExnessAuthError, ExnessError, ExnessRateLimited, ExnessUnavailable
from .exness.schema import Account, AccountState, Instrument
from .exness.stream import Stream
from .manager.manage import MoveSL, NoOp, PartialClose, decide
from .market.candles import CandleStore
from .market.catalog import InstrumentCatalog
from .market.quotes import QuoteBook
from .news.gate import blocking_event
from .risk.portfolio import check_entry
from .signals import custom, v9
from .signals import fusion, scorecard
from .signals.adapter import Candidate, Evaluation, evaluate_all
from .signals.shadow import ShadowBook
from .signals.provider import ExnessV9Provider
from .store.repo import BotState, Repo

log = logging.getLogger(__name__)

FRAMES = ("M15", "H1", "H4")
FRAME_SECONDS = {"M15": 900, "H1": 3600, "H4": 14400}
BAR_SECONDS = 900
BAR_DELAY = 5.0  # mumun broker tarafinda kesinlesmesi icin kapanistan sonra bekleme
MANAGE_INTERVAL = 2.0
HEARTBEAT_INTERVAL = 30.0
RESOLVE_INTERVAL = 10.0
STREAM_ALERT_AFTER = 60.0
QUOTE_MAX_AGE = 60.0
EQUITY_SAMPLE_INTERVAL = 300.0
BALANCE_SYNC_INTERVAL = 300.0  # para yatirma/cekme icin deal gecmisi bu aralikla taranir (olay kacmis olabilir)
BALANCE_SEEN_LOOKBACK = 2 * 86400.0  # taban alinirken "zaten icinde" sayilacak yakin gecmis
BALANCE_HISTORY_DAYS = 29  # gecmis sorgusu sinirinin (30 gun) icinde kalinir
CAPITAL_SEEN = "capital_seen"  # ayar anahtari: deneme modunda ilk okunan varlik kaydedildi mi
BASE_LIVE = "capital_base_live"  # ayar anahtari: sermaye tabani canli moda geciste alindi mi
LOOP_ALERT_AFTER = 5  # bir gorev art arda bu kadar hata verirse kullaniciya haber verilir
LOOP_LOG_EVERY = 100
LOOP_REALERT = 86400.0  # hata surdukce uyari gunde bir yinelenir
LOOP_STREAK_GAP = 3600.0  # duzelen gorev yeniden bozulursa en erken bu kadar sonra yeniden uyarilir
CLOCK_SKEW_LIMIT = 5.0  # V9 fiyat saati "simdi"den bu kadar ilerideyse veriyi reddeder
MAINTENANCE_INTERVAL = 1800.0  # gunluk yedek ve temizlik denetimi (is gunde bir kez yapilir)
RECONCILE_INTERVAL = 300.0  # olay kacirilmis olabilir: broker durumu duzenli olarak yeniden okunur
AUTH_BACKOFF_START = 30.0  # kimlik reddinden sonra yonetim isteklerinin durdugu sure (art arda redde katlanir)
AUTH_BACKOFF_MAX = 300.0
AUTH_ALERT_TTL = 3600.0  # bu sureden sonra yeni bir kimlik reddi yeniden bildirilir
STOP_GRACE = 5.0  # dolumdan sonra SL/TP emrinin gorulmesi icin taninan sure
STOP_RECHECK = 30.0
STOP_VERIFY_RETRY = 15.0  # stop dogrulamasi yapilamadiysa yeniden deneme araligi
STOP_RECHECK_UNKNOWN = 300.0  # seviye bilinmiyorsa (elle mudahale gerekir) daha seyrek kontrol
REARM_LIMIT = 3  # stop bu kadar denemede kurulamazsa pozisyon kapatilir
ATR_MAX_AGE_BARS = 3
TICK_CHUNK = 20
VETO_REASON_CHARS = 80
DATA_DECISIONS = frozenset({"INSUFFICIENT_DATA", "STALE_DATA", "PROVIDER_UNAVAILABLE"})
DATA_REJECTS_MAX = 40
HEAL_PER_SCAN = 4  # tarama basina en cok bu kadar bosluk onarim istegi
HEAL_RETRY = 6 * 3600.0  # borsanin da vermedigi bosluk icin yeniden deneme araligi
# Ileri test (yalnizca deneme modunda, ayri dusuk oncelikli surecte): bkz. backtest.py
SHADOW_CHECK_HOURS = 48.0  # /health/outcomes capraz denetimi: en cok bu kadar eski golge islemler
SHADOW_CHECK_MAX = 120  # ...ve cagri basina en cok bu kadar islem
SWAP_ROLLOVER = 22 * 3600.0  # gun devri (UTC, yaklasik): bu ani gecen pozisyon bir gece tasinmis sayilir
HARD_MAX_RISK_PCT = 5.0  # tek emirde stopta olusacak zararin varliga orani icin MUTLAK tavan (ayar degil)
HARD_MAX_NOTIONAL_X = 50.0  # tek pozisyonun buyuklugu / varlik icin MUTLAK tavan (ayar degil)
BACKTEST_DELAY = 180.0  # acilistan sonra bekleme (sn)
BACKTEST_DAYS = 90  # swing stratejileri: ilk 60 gun ic orneklem, son 30 gun dis orneklem
BACKTEST_V9_DAYS = 60  # V9 pahalidir: son 60 gun (30 gun ic + 30 gun dis orneklem)
BACKTEST_BUDGET = 6 * 3600.0  # V9 asamasinin bir turu icin en uzun sure (sn); tur sonunda ara sonuc yayinlanir
BACKTEST_ROUNDS = 6  # V9 bitmediyse ayni gecmisle art arda en cok bu kadar tur (biten semboller yeniden calismaz)
# Kullanici karari (2026-11-26): backtest SUNUCUDA hesaplanmaz (bot yavaslamasin). Sunucu yalnizca gecmis mumlari
# ceker ve disa aktarir (yalnizca piyasa verisi); hesap GitHub Actions'ta yapilir, sonuc dosyasi sunucuya yuklenir.
BACKTEST_ON_SERVER = False
RESULTS_DIR = Path(os.environ.get("TRADEBOT_RESULTS_DIR", "/opt/tradebot/backtest-results"))  # dagitim kullanicisi yazar
RESULTS_INTERVAL = 60.0  # yuklenen sonuc dosyalarina bakma araligi (sn)
RESULTS_MAX_BYTES = 8_000_000
YEAR_DAYS = 365.0  # yillik backtestin penceresi (bkz. yeartest.py)
YEAR_CHUNK_DAYS = 30.0  # V9 en yeniden eskiye bu buyuklukte parcalarla hesaplanir
YEAR_ROUNDS = 36  # yillik test icin art arda en cok bu kadar tur (tur basina BACKTEST_BUDGET)
YEAR_MAX_AGE = 7 * 86400.0  # tamamlanmis yillik sonuc bundan yeniyse yeniden calismaz
BACKTEST_WINDOW_KEEP = 10 * 86400.0  # yarim kalan is bu kadar eski pencereyle surdurulur (yeniden baslatma sonrasi)
BACKTEST_WORKERS = 0  # 0: islemci sayisi kadar alt surec (hepsi dusuk oncelikli)
BACKTEST_MAX_AGE = 20 * 3600.0  # bundan yeni bir sonuc varsa yeniden calismaz
BACKTEST_FETCH_PAUSE = 0.3  # gecmis mum istekleri arasinda bekleme (sn)
BACKTEST_FETCH_TRIES = 4  # istek siniri asilirsa ayni aralik en cok bu kadar denenir (artan beklemeyle)
BACKTEST_FETCH_FAILURES = 200  # bu kadar aralik alinamazsa is birakilir (surekli hata)
BACKTEST_RATE_PAUSE = 15.0  # istek siniri asilirsa bir kez yinelemeden once bekleme (sn)
BACKTEST_MAJORS = ("EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD")
# Surec her basladiginda (dagitim, cokme, sunucu yeniden acilisi) bu sure boyunca bot YENI islem acmaz; analiz,
# golge kayitlari ve acik pozisyonlarin yonetimi surer. Neden: spread siniri (son 30 dk'nin ornekleri) ve diger
# kisa pencereli olcumler yeniden baslatmadan sonra eksiktir. Kullanici karari (2026-11-26, PR #16 B secenegi).
RESTART_ENTRY_PAUSE = 1800.0
RESTART_PAUSE_REASON = "yeniden başlatmadan sonra 30 dk yeni giriş yok"
SPREAD_STATS_INTERVAL = 300.0  # spread medyani bu aralikla kaydedilir (ileri testin saatlik spread profili)
SPREAD_STATS_KEEP = 30 * 86400.0
PUBLIC_NUMBER = re.compile(r"\d+[.,]\d+|\d{3,}")  # ondalikli ya da 3+ haneli sayilar
SUMMARY_SAMPLES = 5
RATE_PAUSE_LIMIT = 2  # bir taramada 429 sonrasi en cok bu kadar kisa bekleme; sonra tarama birakilir
RATE_PAUSE_DEFAULT = 2.0
RATE_PAUSE_MAX = 10.0


@dataclass
class ScanSummary:
    at: float
    scanned: int = 0
    closed: int = 0  # piyasasi kapali oldugu icin sessizce atlanan semboller
    candidates: int = 0
    opened: int = 0
    blocked: int = 0
    news_blocked: int = 0  # haber penceresi nedeniyle analiz edilmeden atlanan semboller
    observed: int = 0  # guven puani esigin altinda kalan (islem acilmayan) adaylar
    shadowed: int = 0  # golge kipindeki stratejilerin (yalnizca sanal izlenen) adaylari
    errors: int = 0
    skipped: str | None = None
    quoted: int = 0  # taranan sembollerden taze fiyati (tick) olanlar; 0 ise fiyat akisi calismiyor demektir
    candle_retries: int = 0  # ikinci denemede gecen mum istekleri (gecici AUTH_INVALID_API_KEY)
    would_open: int = 0  # deneme modunda tum kapilardan gecen (canlida emir gonderilecek) adaylar
    cost_blocked: int = 0  # maliyet kapisi: spread / stop mesafesi sinirin ustunde (canli ve golge adaylar)
    cost_reasons: dict[str, int] = field(default_factory=dict)  # strateji -> maliyet kapisina takilan aday sayisi
    reasons: dict[str, int] = field(default_factory=dict)
    blocked_reasons: dict[str, int] = field(default_factory=dict)
    veto_reasons: dict[str, int] = field(default_factory=dict)  # aday cikmayan sembollerde V9'un ilk nedeni
    # V9'un VERIYI reddettigi semboller -> neden (+ eksik mumun yeri). Tanilama icindir; yalnizca piyasa bilgisi.
    data_rejects: dict[str, str] = field(default_factory=dict)


def _default_stream_factory(client, path, on_message, name):
    return Stream(client, path, on_message, name=name)


class Bot:
    def __init__(self, settings: Settings, client, repo: Repo, notifier, clock: Callable[[], float] = time.time,
                 *, stream_factory=None, sleep=asyncio.sleep, news=None,
                 restart_pause: float = RESTART_ENTRY_PAUSE):
        self.settings = settings
        self.client = client
        self.repo = repo
        self.notifier = notifier
        self._clock = clock
        self._sleep = sleep
        self.news = news  # NewsCalendar | None (None: haber filtresi yok)
        self._stream_factory = stream_factory or _default_stream_factory
        self.backtest_state = "idle"
        self._restart_pause = float(restart_pause)
        self.entries_from: float | None = None  # bu andan once yeni islem acilmaz (start() belirler)
        self.catalog = InstrumentCatalog(client)
        self.quotes = QuoteBook(clock=clock)
        self.candles = CandleStore(repo.conn, client, self.catalog, clock=clock, sleep=sleep)
        self.account: Account | None = None
        self.provider = ExnessV9Provider(self.catalog, self.candles, self.quotes, lambda: self.account)
        self.executor = Executor(client, repo, notifier, self.catalog, clock=clock,
                                 on_auth_error=self._auth_error, lot_guard=self.lot_guard)
        self.shadow = ShadowBook(repo)
        self.streams: list = []
        self.started = False
        self._details: dict | None = None
        self._tick_stream = None
        self._subscribed: set[str] = set()
        self._connection_alerted = False
        self._daily_blocked = False
        self._account_alerted = False
        self._tick_lead = float("-inf")
        self._clock_alerted = False
        self._skew_beats = 0
        self._loop_failures: dict[str, int] = {}
        self._loop_alerted: dict[str, float] = {}
        self._manage_errors: set[tuple[str, str]] = set()
        self._heal_tried: dict[tuple[str, str, int], float] = {}
        self._last_equity_sample = 0.0
        self._balance_synced_at = 0.0
        self.last_scan: ScanSummary | None = None
        self.tick_errors = 0  # fiyat akisinin dondurdugu hata sayisi (reddedilen abonelik vb.)
        self.tick_error: dict | None = None  # son hata: {"code", "message", "id"}
        self.tick_acks = 0  # sunucunun onayladigi fiyat aboneligi istekleri
        self._limits = schema.Limits()
        self._events_stream = None
        self._event_connections = 0
        self._auth_alerted = False
        self._auth_alerted_at = 0.0
        self._auth_error_at = 0.0
        self._auth_backoff = AUTH_BACKOFF_START
        self._auth_streak = 0  # basarili istek gorulmeden art arda gelen kimlik retleri
        self._results_seen: dict[str, list] = {}  # ice alinan sonuc dosyalarinin (degisim zamani, boyut) izi
        self._auth_blocked_until = 0.0
        self._stop_checked: dict[str, float] = {}
        self._stop_alerted: set[str] = set()
        self._rearm_attempts: dict[str, int] = {}
        self._dry_logged: dict[str, str] = {}

    # ------------------------------------------------------------------ kayit ve bildirim
    async def _record(self, level: str, kind: str, message: str, data: dict | None = None, *,
                      notify: bool = False, title: str | None = None) -> None:
        self.repo.add_event(level, kind, message, data)
        log.log({"error": logging.ERROR, "warning": logging.WARNING}.get(level, logging.INFO), "%s: %s", kind, message)
        if notify and self.notifier is not None:
            try:
                await self.notifier.send(kind, title or kind, message, data)
            except Exception:
                log.exception("bildirim gonderilemedi: %s", kind)

    # ------------------------------------------------------------------ acilis
    async def start(self) -> None:
        """limitler -> katalog -> hesap -> mutabakat -> akislar."""
        v9.load_v9(self.settings.v9_root)
        account_id = self.client.account_id
        await self.client.resolve_host()
        self._limits = schema.parse_limits(await self.client.get(schema.limits_path(account_id)))
        if self._limits.global_rate or self._limits.methods:
            self.client.limiter.configure(global_rate=self._limits.global_rate, methods=self._limits.methods)
        if self._limits.max_candles:
            self.candles.max_candles = self._limits.max_candles
        catalog_errors = await self.catalog.refresh()
        self._details = await self.client.get(schema.account_path(account_id))
        snapshot = schema.parse_snapshot(await self.client.get(schema.snapshot_path(account_id)))
        self._set_account(snapshot.account)
        now = self._clock()
        state = self.repo.bot_state()
        await self._ensure_base(self.repo.get_bot_settings())
        report = await reconcile(self.client, self.repo, self.catalog, clock=self._clock, snapshot=snapshot)
        await self.executor.publish(report)
        self._open_streams()
        await self._refresh_news()
        self.started = True
        self.entries_from = self._clock() + self._restart_pause
        universe = self.catalog.universe(self.repo.get_bot_settings().enabled_symbols)
        dry_run = self.repo.get_bot_settings().dry_run
        pause = (f". İlk {self._restart_pause / 60:.0f} dakika yeni işlem açılmaz (açık pozisyonlar yönetilir)"
                 if self._restart_pause > 0 else "")
        await self._record("info", "bot_started",
                           f"Bot başladı (sürüm {_version()}, {'deneme' if dry_run else 'CANLI'} modu): "
                           f"{len(universe)} sembol izleniyor" + pause,
                           {"universe": len(universe), "catalog_errors": len(catalog_errors), "dry_run": dry_run,
                            "version": _version()})

    def _set_account(self, state: AccountState | None) -> None:
        if state is None or self._details is None:
            return
        try:
            self.account = schema.parse_account(self._details, state)
        except ValueError as exc:
            log.warning("hesap durumu okunamadi: %s", exc)

    def _tick_symbols(self) -> list[str]:
        """Evren + acik islemlerin sembolleri (broker adlariyla). Donusum pariteleri evrenin icindedir."""
        names = {i.broker_symbol for i in self.catalog.universe()}
        for trade in self.repo.open_trades():
            try:
                names.add(self.catalog.get(trade.symbol).broker_symbol)
            except KeyError:
                continue
        return sorted(names)

    def _open_streams(self) -> None:
        account_id = self.client.account_id
        ticks = self._stream_factory(self.client, schema.ticks_ws_path(account_id), self.on_tick_message, "ticks")
        symbols = self._tick_symbols()
        rate = self._limits.tick_subscription_rate
        chunk = max(1, min(TICK_CHUNK, rate[2])) if rate else 10
        ticks.subscription_delay = (rate[1] * chunk / rate[0] * 1.1) if rate else 1.0
        ticks.set_subscriptions([schema.subscribe_ticks(f"ticks-{i // chunk}", symbols[i:i + chunk])
                                 for i in range(0, len(symbols), chunk)])
        self._subscribed = set(symbols)
        events = self._stream_factory(self.client, schema.events_ws_path(account_id), self.on_event_message, "events")
        events.subscription_delay = 0.5
        events.set_subscriptions([schema.subscribe_events("events-tx", "transactions"),
                                  schema.subscribe_events("events-account", "account_state"),
                                  schema.subscribe_events("events-instruments", "instruments", ["all"])])
        self._tick_stream = ticks
        self._events_stream = events
        self._event_connections = getattr(events, "connections", 0)
        self.streams = [ticks, events]

    def streams_up(self) -> bool:
        return bool(self.streams) and all(s.connected for s in self.streams)

    # ------------------------------------------------------------------ akis mesajlari
    async def on_tick_message(self, raw: dict) -> None:
        tick = schema.parse_tick(raw)
        if tick is None:
            # Abonelik yaniti ya da hata: reddedilen abonelik sessiz kalmamali (fiyat hic gelmez).
            if schema.is_ws_ack(raw):
                self.tick_acks += 1  # abonelik onayi (kod 200): hata degil
                return
            code, message = schema.parse_error(raw)
            if code is not None:
                log.warning("fiyat akisi hata dondurdu: %s (kod %s, istek %s)", message, code, raw.get("id"))
                self.tick_errors += 1
                # Son hata /health'te gorunur (kod, sabit hata adi ve bizim gonderdigimiz istek kimligi;
                # hesap bilgisi icermez): reddedilen aboneligin nedeni sunucu gunlugune bakmadan anlasilir.
                request_id = raw.get("id")
                self.tick_error = {"code": code, "message": (message or "")[:80],
                                   "id": request_id[:40] if isinstance(request_id, str) else None}
            return
        # Tick saati sunucu saatinden ilerideyse sunucu saati geri kalmistir (V9 boyle veriyi "bayat" sayar).
        self._tick_lead = max(self._tick_lead, tick.time - self._clock())
        instrument = self.catalog.by_broker(tick.symbol)
        self.quotes.on_tick(dataclasses.replace(tick, symbol=instrument.symbol) if instrument else tick)

    async def on_event_message(self, raw: dict) -> None:
        kind, data = schema.parse_ws_event(raw)
        if kind == "transaction":
            self._set_account(data.account)
            for deal in data.deals:
                await self._apply_balance_deal(deal)  # para yatirma/cekme: tabani kaydirir, K/Z degildir
            await self.executor.on_transaction(data)
        elif kind == "snapshot":
            # Her (yeniden) baglanmada gelir: kacirilan olaylar icin durum buradan toparlanir.
            self._set_account(data.account)
            await self.executor.reconcile(snapshot=data)
        elif kind == "account":
            self._set_account(data)
        elif kind == "instrument":
            self.catalog.update(data)
        elif kind == "error":
            log.warning("olay akisi hata dondurdu: %s", data)

    # ------------------------------------------------------------------ kar/zarar ve limitler
    def _unrealized(self, origin: str) -> float:
        total = 0.0
        for trade in self.repo.open_trades(origin):
            quote = self.quotes.quote(trade.symbol)
            if quote is None:
                continue
            price = quote["bid"] if trade.side == "BUY" else quote["ask"]
            total += self.provider.pnl(trade.symbol, trade.side, trade.volume, trade.entry, price) or 0.0
        return total

    def _day_start(self) -> float:
        return float(int(self._clock() // 86400) * 86400)  # gun siniri UTC 00:00

    def bot_pnl(self, state: BotState | None = None) -> tuple[float, float]:
        """(bugun, toplam): botun gerceklesen + acik kar/zarari."""
        state = state or self.repo.bot_state()
        floating = self._unrealized("bot")
        return (self.repo.bot_realized_pnl(since=self._day_start()) + floating,
                self.repo.realized_pnl("bot", after=state.start_at) + floating)  # taban anindan sonrasi

    async def _halt(self, reason: str) -> None:
        if self.repo.bot_state().halted:
            return
        self.repo.set_bot_state(halted=True, halt_reason=reason)
        await self._record("error", "bot_halted", f"Bot durdu: {reason}. Devam için uygulamadan onay gerekli.",
                           {"reason": reason}, notify=True, title="Bot durdu")

    def _base_is_live(self) -> bool:
        return bool(self.repo.get_setting(BASE_LIVE, False))

    async def _ensure_base(self, settings: BotSettings) -> None:
        """Kayip sinirlarinin tabani (start_capital, start_at).

        - Deneme modunda (ve bot henuz hic canli calismadiysa) taban GECICIdir: guncel varligi izler.
          Deneme modunda bot islemi olmadigi icin bunun kayip olcumune etkisi yoktur.
        - Bot ilk kez canli moda (dry_run=False) gectiginde taban o andaki gercek varliktan alinir ve
          olcum o andan baslar. Sonrasinda taban yalnizca para yatirma/cekme ile ya da kullanicinin
          kayip siniri durmasini bilincli onaylamasiyla degisir; deneme moduna gecip donmek tabani
          sifirlamaz (aksi halde kayip siniri bir dugmeyle silinebilirdi).
        - Varlik bilinmiyorsa ya da pozitif degilse taban kurulmaz: 0 taban hem yeni islemi hem
          sinirlari kalici olarak devre disi birakirdi.
        """
        account = self.account
        if account is None or account.equity <= 0:
            return
        state = self.repo.bot_state()
        now = self._clock()
        if self._base_is_live():
            if state.start_capital is None or state.start_capital <= 0:
                # Taban tumuyle cekilmis ya da bozulmus: guncel varliktan yeniden kurulur. Olcum baslangici
                # KORUNUR; yoksa hesabi bosaltip yeniden doldurmak onceki bot zararlarini silerdi.
                self.repo.set_bot_state(start_capital=account.equity,
                                        start_at=state.start_at if state.start_at is not None else now)
                await self._mark_balance_history_seen()
            return
        if settings.dry_run:
            if state.start_capital != account.equity or state.start_at is None:
                self.repo.set_bot_state(start_capital=account.equity,
                                        start_at=state.start_at if state.start_at is not None else now)
            if not self.repo.get_setting(CAPITAL_SEEN, False):
                # Canliya gecmeden once botun hesapta ilk okudugu (pozitif) varlik kayda gecer.
                self.repo.set_setting(CAPITAL_SEEN, True)
                await self._record(
                    "info", "capital_seen",
                    f"Deneme modu: hesapta okunan ilk varlık {account.equity:.2f} {account.currency} "
                    f"(bakiye {account.balance:.2f}). Kayıp sınırı tabanı canlıya geçişte o andaki "
                    "varlıktan alınacak.",
                    {"equity": account.equity, "balance": account.balance, "currency": account.currency})
            return
        self.repo.set_bot_state(start_capital=account.equity, start_at=now)
        self.repo.set_setting(BASE_LIVE, True)
        self._balance_synced_at = now
        await self._mark_balance_history_seen()
        await self._record(
            "info", "capital_base",
            f"Canlı mod: kayıp sınırları {account.equity:.2f} {account.currency} üzerinden ölçülecek "
            f"(günlük %{settings.risk.daily_loss_pct:g}, toplam %{settings.risk.total_loss_pct:g}).",
            {"start_capital": account.equity, "currency": account.currency}, notify=True,
            title="Canlı mod başladı")

    async def _mark_balance_history_seen(self) -> None:
        """Taban az once guncel varliktan alindi: gecmisteki tum para yatirma/cekme islemleri o varligin
        icindedir. Kimlikleriyle "goruldu, uygulanmadi" diye kaydedilir; boylece broker saati ile sunucu
        saati arasindaki fark yuzunden ayni tutar tabana ikinci kez eklenemez. Gecmis okunamazsa zaman
        karsilastirmasi (deal zamani > taban ani) yine korur."""
        now = self._clock()
        try:
            deals = await fetch_all_deals(self.client, now - BALANCE_SEEN_LOOKBACK)
        except (ExnessError, ValueError) as exc:
            log.warning("taban icin bakiye gecmisi okunamadi: %s", exc)
            return
        for deal in deals:
            if deal.type == schema.DEAL_BALANCE and deal.profit:
                self.repo.apply_balance_op(deal.id, deal.time if deal.time is not None else now, deal.profit,
                                           apply=False)

    async def settings_changed(self) -> None:
        """Ayarlar degisti. Canli moda ilk geciste taban, taze okunan varliktan hemen alinir."""
        settings = self.repo.get_bot_settings()
        if not settings.dry_run and not self._base_is_live() and self.started:
            await self.reconcile_now()  # varlik bayat olmasin (az once para yatirilmis olabilir)
        await self._ensure_base(settings)

    async def _apply_balance_deal(self, deal: schema.Deal) -> None:
        """Para yatirma/cekme bot kari/zarari degildir; canli tabani tutar kadar kaydirir.

        Tabandan onceki (ya da gecici taban donemindeki) islemler yalnizca kaydedilir: tutarlari zaten
        tabanin alindigi varligin icindedir.
        """
        if deal.type != schema.DEAL_BALANCE or not deal.profit:
            return
        state = self.repo.bot_state()
        at = deal.time if deal.time is not None else self._clock()
        apply = (self._base_is_live() and state.start_capital is not None and state.start_at is not None
                 and at > state.start_at)
        new, base = self.repo.apply_balance_op(deal.id, at, deal.profit, apply=apply)
        if not new:
            return
        unit = f" {self.account.currency}" if self.account is not None else ""
        kind = "Para yatırma" if deal.profit > 0 else "Para çekme"
        if base is None:
            # Taban gecici (deneme modu) ya da islem tabandan once: yalnizca kayda gecer.
            await self._record(
                "info", "balance_change",
                f"{kind}: {deal.profit:+.2f}{unit}. Bot kârı/zararı sayılmaz; kayıp sınırı tabanı değişmedi "
                "(taban bu tutarı zaten içeriyor ya da henüz canlıya geçilmedi).",
                {"amount": deal.profit, "deal_id": deal.id, "at": at, "applied": False})
            return
        await self._record(
            "info", "balance_change",
            f"{kind}: {deal.profit:+.2f}{unit}. Kayıp sınırı tabanı {state.start_capital:.2f} → {base:.2f}{unit}; "
            "bu tutar bot kârı/zararı sayılmaz.",
            {"amount": deal.profit, "deal_id": deal.id, "at": at, "applied": True, "start_capital": base},
            notify=True, title=kind)

    async def sync_balance_ops(self) -> None:
        """Deal gecmisinden para yatirma/cekme islemlerini toplar (olay akisi kacirmis olabilir)."""
        state = self.repo.bot_state()
        # Deneme modunda da okunur: islemler tabani degistirmez ama olay olarak kayda gecer.
        if state.start_at is None or self._auth_blocked():
            return
        now = self._clock()
        watermark = float(self.repo.get_setting("balance_synced_at", 0.0) or 0.0)
        since = max(state.start_at, watermark - 600.0, now - BALANCE_HISTORY_DAYS * 86400.0)
        try:
            deals = await fetch_all_deals(self.client, since)
        except ExnessAuthError as exc:
            await self._auth_error(exc)
            return
        except (ExnessError, ValueError) as exc:
            log.warning("bakiye islemleri okunamadi: %s", exc)
            return
        for deal in deals:
            await self._apply_balance_deal(deal)
        self.repo.set_setting("balance_synced_at", now)

    async def _check_limits(self, settings: BotSettings) -> None:
        await self._ensure_base(settings)
        state = self.repo.bot_state()
        capital = state.start_capital
        if not capital or capital <= 0:
            return
        today, total = self.bot_pnl(state)
        if not state.halted and total <= -settings.risk.total_loss_pct / 100.0 * capital:
            await self._halt(f"toplam kayıp sınırı (%{settings.risk.total_loss_pct:g}) aşıldı")
        self._daily_blocked = today <= -settings.risk.daily_loss_pct / 100.0 * capital
        if self._daily_blocked:
            day = datetime.fromtimestamp(self._day_start(), timezone.utc).strftime("%Y-%m-%d")
            if self.repo.get_setting("daily_limit_day") != day:
                self.repo.set_setting("daily_limit_day", day)
                await self._record("warning", "daily_limit",
                                   f"Günlük kayıp sınırı (%{settings.risk.daily_loss_pct:g}) doldu; "
                                   "bugün yeni bot işlemi açılmayacak.",
                                   {"pnl_today": today}, notify=True, title="Günlük limit doldu")

    # ------------------------------------------------------------------ tarama
    def _is_open(self, instrument: Instrument, now: float) -> bool:
        from forex.sessions import broker_status

        if not instrument.trading_hours:
            return False
        status = broker_status(datetime.fromtimestamp(now, timezone.utc), instrument.symbol, True,
                               instrument.trading_hours)
        return status["status"] in ("OPEN", "CLOSING_SOON")

    def _gap_note(self, instrument: Instrument) -> str | None:
        gap = self._gap(instrument)
        return None if gap is None else f"{gap[0]} {datetime.fromtimestamp(gap[1], timezone.utc):%Y-%m-%dT%H:%MZ} {gap[2]}"

    def _gap(self, instrument: Instrument) -> tuple[str, int, str] | None:
        """Mum serisinde, beyan edilen islem saatlerine gore ACIK gorunen ilk eksik dakika -> (cerceve, an, durum)."""
        return next(iter(self._gaps(instrument)), None)

    def _gaps(self, instrument: Instrument):
        """Serideki her bosluk icin, acik saate denk gelen ilk eksik dakika (bosluk basina bir kayit)."""
        from forex.sessions import broker_status

        if not instrument.trading_hours:
            return
        for frame in FRAMES:
            size = FRAME_SECONDS[frame]
            rows = self.candles.cached(instrument.symbol, frame, 256)
            for before, after in zip(rows, rows[1:]):
                for minute in range(before["time"] + size, after["time"], 60):
                    moment = datetime.fromtimestamp(minute, timezone.utc)
                    status = broker_status(moment, "", True, instrument.trading_hours)["status"]
                    if status not in ("CLOSED", "OPENING_SOON"):
                        yield frame, minute, status
                        break

    async def _heal_gaps(self, summary: ScanSummary, scanned: set[str]) -> None:
        """Taranan sembollerin mum serisinde acik saate denk gelen boslugu borsadan yeniden ister (tarama basina sinirli).

        V9'un reddetmesi BEKLENMEZ: V9 gunluk devirdeki tek sessiz M15 mumunu hos gorur; o mum borsada
        aslinda varsa (onbellege alinamamissa) sessizce eksik kalmamali. Mum gelirse bir sonraki taramada
        kullanilir. Borsa da vermiyorsa bosluk gercektir ve HEAL_RETRY suresince yeniden istenmez. Istek
        basarisiz olursa (baglanti, limit) deneme sayilmaz: sonraki taramada yeniden denenir.
        """
        now = self._clock()
        healed = 0
        for symbol in sorted(scanned):
            if healed >= HEAL_PER_SCAN:
                break
            try:
                gaps = list(self._gaps(self.catalog.get(symbol)))
            except KeyError:
                continue
            note = summary.data_rejects.get(symbol)
            # Borsanin da vermedigi (yakin zamanda sorulmus) bosluklar atlanir; siradaki sorulmamis bosluk istenir.
            # Boylece kalici bir devir boslugu, ayni semboldeki sonraki gercek bir eksigi gizlemez.
            fresh = [(frame, minute) for frame, minute, _ in gaps
                     if now - self._heal_tried.get((symbol, frame, minute // FRAME_SECONDS[frame]), float("-inf"))
                     >= HEAL_RETRY]
            if not fresh:
                if gaps and note is not None and "missing candle" in note:
                    summary.data_rejects[symbol] = note + " (onarım denendi: borsada da yok)"
                continue
            frame, minute = fresh[0]
            key = (symbol, frame, minute // FRAME_SECONDS[frame])
            healed += 1
            try:
                filled = await self.candles.heal(symbol, frame, minute)
            except (ExnessError, ValueError) as exc:
                log.warning("mum onarimi basarisiz %s %s: %s", symbol, frame, exc)
                continue
            self._heal_tried[key] = now  # yalnizca kesin yanittan sonra: basarisiz istek yeniden denenir
            if note is not None and "missing candle" in note:
                summary.data_rejects[symbol] = note + (" (onarıldı: mum geldi)" if filled
                                                       else " (onarım denendi: borsada da yok)")
            log.info("mum onarimi %s %s: %s", symbol, frame, "geldi" if filled else "borsada da yok")
        for key in [k for k, at in self._heal_tried.items() if now - at > 2 * HEAL_RETRY]:
            del self._heal_tried[key]

    def _spread(self, symbol: str) -> float:
        quote = self.quotes.quote(symbol)
        return float(quote["spread"]) if quote else 0.0

    def _commission(self, instrument: Instrument, settings: BotSettings) -> float:
        """Lot basina gidis-donus komisyon (hesap para birimi): ayar ile enstrumanin bildirdiginden buyuk olan."""
        derived = 0.0
        if instrument.commission_value and instrument.commission_type in ("per_lot_per_side", "per_lot_per_trade"):
            currency = instrument.commission_currency or "USD"
            bounds = self.provider.rates.bounds(currency, self.account.currency) if self.account else None
            if bounds:
                derived = abs(instrument.commission_value) * 2 * bounds[1]
        return max(settings.commission_per_lot, derived)

    async def _refresh_open_candles(self, already: set[str]) -> None:
        """Iz suren stop icin acik islemlerin M15 mumlari, tarama yapilmasa da guncel kalmali."""
        for trade in self.repo.open_trades():
            if trade.symbol in already:
                continue
            already.add(trade.symbol)
            try:
                self.catalog.get(trade.symbol)
                await self.candles.get(trade.symbol, "M15", 64)
            except (ExnessError, ValueError, KeyError):
                continue

    async def _skip(self, summary: ScanSummary, reason: str) -> ScanSummary:
        summary.skipped = reason
        if reason != "stream_down":
            await self._refresh_open_candles(set())
        await self._record("info", "scan_skipped", f"Tarama yapılmadı: {_SKIP.get(reason, reason)}", {"reason": reason})
        return summary

    async def _auth_error(self, exc: ExnessError) -> None:
        """Kimlik reddi: tek olay + tek bildirim; yonetim istekleri kisa bir sure durur (dongu yok).

        Bekleme 30 sn'den baslar ve art arda retlerde 5 dakikaya kadar katlanir: tek seferlik bir 401
        stop yonetimini dakikalarca durdurmaz. Basarili herhangi bir istek kilidi hemen acar.
        Her ret, kaynagiyla (hangi tur istek) ve o ana kadarki ardisik ret sayisiyla `auth_reject` olarak
        kaydedilir (bildirimsiz): tek seferlik mi, surekli mi sonradan gorulebilsin.
        """
        now = self._clock()
        self._auth_streak += 1
        self._auth_error_at = now
        self._auth_blocked_until = now + self._auth_backoff
        self._auth_backoff = min(self._auth_backoff * 2, AUTH_BACKOFF_MAX)
        try:  # tanilama kaydi; yazilamasa da bekleme kilidi yukarida kuruldu
            self.repo.add_event("warning", "auth_reject", "Exness bir isteği kimlik hatasıyla reddetti",
                                {"code": exc.code, "status": exc.status,
                                 "source": getattr(exc, "source", None) or "okuma", "streak": self._auth_streak})
        except sqlite3.Error:
            log.warning("kimlik reddi kaydedilemedi")
        if self._auth_alerted and now - self._auth_alerted_at < AUTH_ALERT_TTL:
            log.error("kimlik dogrulamasi hala reddediliyor: %s", exc)
            return
        self._auth_alerted, self._auth_alerted_at = True, now
        await self._record(
            "error", "auth_error",
            f"Exness kimlik doğrulaması reddedildi: {exc}. Sunucu saatini (NTP) ve API anahtarını kontrol edin.",
            {"code": exc.code}, notify=True, title="API erişimi reddedildi")

    async def _auth_ok(self) -> None:
        """Retten sonra basarili bir imzali istek goruldu: kilidi ac ve bir kez kaydet."""
        if not self._auth_alerted and self._auth_blocked_until == 0.0:
            return
        if getattr(self.client, "last_ok_at", 0.0) <= self._auth_error_at:
            return
        was_alerted = self._auth_alerted
        self._auth_alerted = False
        self._auth_streak = 0
        self._auth_blocked_until = 0.0
        self._auth_backoff = AUTH_BACKOFF_START
        if was_alerted:
            await self._record("info", "auth_restored", "Exness kimlik doğrulaması yeniden çalışıyor.",
                               {"after_seconds": round(self._clock() - self._auth_error_at, 1)})

    def _auth_blocked(self) -> bool:
        return self._clock() < self._auth_blocked_until

    async def on_bar_close(self, tf: str = "M15") -> ScanSummary:
        summary = await self._scan(tf)
        self.last_scan = summary  # /health icin: son taramanin sayilari (hesap bilgisi icermez)
        return summary

    async def _scan(self, tf: str = "M15") -> ScanSummary:
        now = self._clock()
        summary = ScanSummary(at=now)
        self.repo.set_bot_state(last_scan_at=now)
        await self._check_scorecard()
        settings = self.repo.get_bot_settings()
        await self._check_limits(settings)
        state = self.repo.bot_state()
        if state.halted:
            return await self._skip(summary, "halted")
        if state.stopped:
            return await self._skip(summary, "stopped")
        if not self.streams_up():
            return await self._skip(summary, "stream_down")  # baglanti yokken yeni islem yok (spec §7)
        if self.account is None or not self.account.can_open:
            return await self._skip(summary, "account_blocked")
        if self._daily_blocked:
            return await self._skip(summary, "daily_limit")

        scanned: set[str] = set()
        news_events = self.news.events() if self.news is not None and settings.news.enabled else []
        retries_before = self.candles.transient_rejections
        rate_pauses = 0
        for instrument in self.catalog.universe(settings.enabled_symbols):
            symbol = instrument.symbol
            if not self._is_open(instrument, now):
                summary.closed += 1  # hafta sonu forex gibi: sessizce atla
                continue
            if news_events and blocking_event(instrument, news_events, now=now,
                                              window_minutes=settings.news.window_minutes) is not None:
                summary.news_blocked += 1  # haber penceresi: yeni islem yok (acik islemler stoplariyla surer)
                continue
            try:
                for frame in FRAMES:
                    await self.candles.get(symbol, frame, 256)
                await self._daily_candles(symbol)
            except ExnessAuthError as exc:
                if exc.code == schema.AUTH_INVALID_API_KEY:
                    # Mum servisi iki kez ust uste reddetti. Bu kod canlida piyasa verisi icin gecici olarak
                    # goruldu; pozisyon yonetimini (stop takibi, mutabakat) durdurmak icin yeterli kanit
                    # degil. Tarama birakilir; anahtar gercekten gecersizse diger istekler kilidi kurar.
                    summary.errors += 1
                    summary.skipped = "market_data_rejected"
                    await self._record("warning", "market_data_rejected",
                                       f"Mum verisi reddedildi; tarama yarıda kesildi ({exc})", {"code": exc.code})
                    return summary
                await self._auth_error(exc)
                summary.skipped = "auth_error"
                return summary
            except ExnessRateLimited as exc:
                # Limit asildi. Reddedilen istek YINELENMEZ (bu sembol bu mumda atlanir); kisa bir beklemeden
                # sonra siradaki sembollerle devam edilir. Art arda olursa tarama birakilir: dongu yok.
                summary.errors += 1
                rate_pauses += 1
                if rate_pauses > RATE_PAUSE_LIMIT:
                    summary.skipped = "rate_limited"
                    await self._record("warning", "rate_limited",
                                       f"İstek limiti doldu; tarama yarıda kesildi ({exc})")
                    return summary
                if rate_pauses == 1:
                    await self._record("warning", "rate_limited",
                                       f"İstek limiti doldu; {symbol} bu mumda atlandı, tarama sürüyor ({exc})")
                await self._sleep(min(max(exc.retry_after or RATE_PAUSE_DEFAULT, 0.5), RATE_PAUSE_MAX))
                continue
            except (ExnessError, ValueError) as exc:
                summary.errors += 1
                log.warning("mumlar alinamadi %s: %s", symbol, exc)
                continue
            scanned.add(symbol)
            # Mumlar istek limitiyle cekilir: soguk taramada 30 sembol ~1 dakika surer. Degerlendirme ANI tarama
            # baslangici degil, simdidir; yoksa canli akistan gelen fiyat "gelecekten" gorunur ve V9 bayat der.
            now = self._clock()
            age = self.quotes.age(symbol)
            if age is not None and age <= QUOTE_MAX_AGE:
                summary.quoted += 1
            await self._auth_ok()
            modes = {s: strategy_mode(settings, s) for s in v9.builtin_strategy_ids()}
            results = evaluate_all(self.provider, symbol, equity=self.account.equity, risk_pct=settings.risk.risk_pct,
                                   commission_per_lot=self._commission(instrument, settings), modes=modes, now=now)
            summary.scanned += 1
            await asyncio.sleep(0)  # analiz islemciyi tutar; pozisyon yonetimine sira ver
            for result in results:
                if result.candidate is None:
                    summary.reasons[result.decision] = summary.reasons.get(result.decision, 0) + 1
                    veto = (result.reasons[0] if result.reasons else result.decision)[:VETO_REASON_CHARS]
                    summary.veto_reasons[veto] = summary.veto_reasons.get(veto, 0) + 1
                    if result.decision in DATA_DECISIONS and len(summary.data_rejects) < DATA_REJECTS_MAX:
                        note = self._gap_note(instrument) if "missing candle" in veto else None
                        summary.data_rejects[symbol] = PUBLIC_NUMBER.sub("#", veto) + (f" [{note}]" if note else "")
                    log.info("aday yok %s: %s (%s)", symbol, result.decision, "; ".join(result.reasons))
                    continue
                summary.candidates += 1
                await self._consider(result, instrument, settings, summary)
            # V9 disindaki (yeni) stratejiler: varsayilan golge. Canliya alinmis olanlar ayni kapilardan gecer.
            custom_modes = {s: strategy_mode(settings, s) for s in custom.strategy_ids()}
            v9_report = next((r.report for r in results if r.report is not None), None)
            try:
                extra = custom.evaluate(self.provider, instrument, equity=self.account.equity,
                                        risk_pct=settings.risk.risk_pct, modes=custom_modes, now=self._clock(),
                                        report=v9_report, v9_decisions=tuple(r.decision for r in results),
                                        commission_per_lot=self._commission(instrument, settings))
            except Exception:  # noqa: BLE001 - yeni stratejilerdeki bir hata taramayi (ve golge sonuclarini) dusurmemeli
                log.exception("yeni stratejiler degerlendirilemedi: %s", symbol)
                summary.errors += 1
                extra = []
            for result in extra:
                summary.candidates += 1
                await self._consider(result, instrument, settings, summary)

        for symbol in self.shadow.open_symbols():  # sanal islemleri kapanmis mumlarla sonuclandir
            try:
                self.catalog.get(symbol)
                if symbol not in scanned:
                    await self.candles.get(symbol, "M15", 128)
                    scanned.add(symbol)
                # Acilisindan bu yana kapanan BUTUN mumlar gerekir: uzun kesintiden sonra yalnizca son 128 muma
                # bakilirsa stopa/hedefe degen mum pencerenin disinda kalir ve sonuc yanlis kaydedilir.
                self.shadow.resolve(symbol, self.candles.cached(symbol, "M15", self.shadow.bars_needed(symbol, now)),
                                    now)
            except (ExnessError, ValueError, KeyError):
                continue
        await self._refresh_open_candles(scanned)
        await self._heal_gaps(summary, scanned)
        summary.candle_retries = self.candles.transient_rejections - retries_before
        if summary.candle_retries:
            log.warning("tarama: %d mum istegi ilk denemede reddedildi, ikincide gecti", summary.candle_retries)
        await self._record(
            "info", "scan",
            f"Tarama: {summary.scanned} sembol, {summary.candidates} aday, {summary.opened} emir"
            + (f", {summary.closed} kapalı" if summary.closed else "")
            + (f", {summary.news_blocked} haber penceresinde" if summary.news_blocked else ""),
            dataclasses.asdict(summary))
        return summary

    def _with_tp2(self, candidate: Candidate, instrument: Instrument, settings: BotSettings) -> Candidate:
        multiple = settings.manage.tp2_r
        if abs(multiple - 3.0) < 1e-9:
            return candidate  # V9 plani zaten 3R
        sign = 1.0 if candidate.side == "BUY" else -1.0
        raw = candidate.entry + sign * multiple * abs(candidate.entry - candidate.stop_loss)
        quantum = Decimal(str(instrument.tick_size))
        units = (Decimal(str(raw)) / quantum).to_integral_value(rounding=ROUND_CEILING if sign > 0 else ROUND_FLOOR)
        return dataclasses.replace(candidate, take_profit_2=float(units * quantum))

    def _score(self, result: Evaluation, instrument: Instrument, settings: BotSettings):
        """(puan, oylar, carpan). Guven puani kapaliyken ya da rapor yokken tam risk (1.0)."""
        if not settings.fusion.enabled or result.report is None:
            return None, None, 1.0
        votes = fusion.collect_votes(result.report, result.candidate.side, now=self._clock(), kind=instrument.kind)
        value = fusion.score(votes, settings.fusion.weights)
        return value, {v.module: v.value for v in votes}, fusion.risk_multiplier(value, settings.fusion)

    async def _observe(self, candidate: Candidate, summary: ScanSummary, *, score: float | None, votes: dict | None,
                       reason: str) -> None:
        """Islem acilmayan aday: "gozlem" olarak kaydedilir (spec §6.2), emir gonderilmez."""
        summary.observed += 1
        await self._record(
            "info", "signal_observed",
            f"{candidate.symbol} {candidate.side} gözlem olarak kaydedildi: {reason}",
            {"symbol": candidate.symbol, "side": candidate.side, "strategy_id": candidate.strategy_id,
             "setup_id": candidate.setup_id, "score": score, "votes": votes, "reason": reason})

    async def _consider(self, result: Evaluation, instrument: Instrument, settings: BotSettings,
                        summary: ScanSummary) -> None:
        candidate = result.candidate
        if self.executor.already_submitted(candidate):
            return  # ayni mum ikinci kez tarandi
        # Maliyet kapisi: giris anindaki GERCEK spread stop mesafesinin `max_spread_stop_pct`'inden buyukse islem
        # yok. Canli adaylara da golge kayitlarina da uygulanir (karne ayni kuralla olussun). Spread bilinmiyorsa
        # aday gecmez.
        spread_r = self._spread_r(candidate) if self.quotes.quote(candidate.symbol) is not None else None
        if spread_r is None or spread_r * 100.0 > settings.risk.max_spread_stop_pct:
            summary.cost_blocked += 1
            summary.cost_reasons[candidate.strategy_id] = summary.cost_reasons.get(candidate.strategy_id, 0) + 1
            log.info("aday maliyet kapisina takildi %s %s %s: spread/stop %s", candidate.symbol, candidate.side,
                     candidate.strategy_id, spread_r)
            return
        score, votes, multiplier = self._score(result, instrument, settings)
        if result.mode == "shadow":
            # Golge kipindeki strateji: sinyali ve sanal sonucu izle, gercek emir gonderme.
            reason = "paused" if candidate.strategy_id in scorecard.paused(self.repo) else "shadow"
            if self.shadow.open(candidate, reason, score, self._clock(), self._spread(candidate.symbol)):
                summary.shadowed += 1
            return
        if multiplier is None:
            self.shadow.open(candidate, "low_score", score, self._clock(), self._spread(candidate.symbol))
            await self._observe(candidate, summary, score=score, votes=votes,
                                reason=f"güven puanı {score:.0f} < {settings.fusion.min_score:g}")
            return
        if multiplier < 1.0:
            lots = fusion.scale_lots(candidate.lots, multiplier, instrument)
            if lots is None:
                await self._observe(candidate, summary, score=score, votes=votes,
                                    reason=f"puan {score:.0f} için azaltılmış lot en küçük lotun altında")
                return
            candidate = dataclasses.replace(candidate, lots=lots,
                                            risk_amount=candidate.risk_amount * lots / candidate.lots)
        if self.entry_paused():
            summary.blocked += 1
            summary.blocked_reasons[RESTART_PAUSE_REASON] = summary.blocked_reasons.get(RESTART_PAUSE_REASON, 0) + 1
            log.info("aday engellendi %s %s: %s", candidate.symbol, candidate.side, RESTART_PAUSE_REASON)
            return
        state = self.repo.bot_state()
        today, total = self.bot_pnl(state)
        # Islem satiri ancak dolum olayiyla olusur. Ayni taramada gonderilmis ama henuz dolmamis
        # emirler de acik sayilir; yoksa tek mumda birden cok aday limitleri asar.
        in_flight = [Trade(position_id="pending:" + o["idempotency_key"], origin="bot",
                           symbol=o["payload"].get("symbol") or "", side=o["payload"].get("side") or "BUY",
                           volume=0.0, entry=o["payload"].get("entry") or 0.0)
                     for o in self.executor.pending_opens("bot")]
        verdict = check_entry(candidate, open_bot=self.repo.open_trades("bot") + in_flight, bot_pnl_today=today,
                              bot_pnl_total=total, start_capital=state.start_capital,
                              halted=state.halted or state.stopped, settings=settings.risk,
                              instruments=self.catalog.as_mapping())
        if verdict.should_halt:
            await self._halt(verdict.reason)
        if not verdict.allowed:
            summary.blocked += 1
            summary.blocked_reasons[verdict.reason] = summary.blocked_reasons.get(verdict.reason, 0) + 1
            log.info("aday engellendi %s %s: %s", candidate.symbol, candidate.side, verdict.reason)
            return
        candidate = self._with_tp2(candidate, instrument, settings)
        equity = self.account.equity if self.account is not None else 0.0
        data = {**dataclasses.asdict(candidate), "dry_run": settings.dry_run, "score": score, "votes": votes,
                # Varliga oranla risk (%): tutarin kendisi bakiyeyi ele verir, oran vermez.
                "risk_pct": round(candidate.risk_amount / equity * 100.0, 4) if equity > 0 else None,
                # Giristeki spread'in stop mesafesine orani: islemin pesin maliyeti (R cinsinden).
                "spread_r": self._spread_r(candidate)}
        text = (f"{candidate.symbol} {candidate.side} {candidate.lots:g} lot @ {candidate.entry:g}, "
                f"SL {candidate.stop_loss:g}, TP {candidate.take_profit_2:g} ({candidate.strategy_id})")
        if settings.dry_run:
            summary.would_open += 1
            await self._record("info", "signal", "[dry-run] " + text, data)  # kaydet, emir gonderme
            return
        await self._record("info", "signal", text, data)
        try:
            key = await self.executor.open(candidate, "bot", score=score, votes=votes)
        except ValueError as exc:  # istek kurulamadi (or. hacim sinir disi): bu adayi birak, taramaya devam
            await self._record("warning", "signal_invalid", f"{candidate.symbol} emri kurulamadı: {exc}",
                               {"symbol": candidate.symbol})
            return
        order = self.repo.get_order(key)
        if order is not None and order["state"] != "REJECTED":
            summary.opened += 1

    # ------------------------------------------------------------------ pozisyon yonetimi
    def _atr(self, symbol: str) -> float | None:
        from forex.core import atr

        bars = self.candles.cached(symbol, "M15", 64)
        if len(bars) < 15 or self._clock() - (bars[-1]["time"] + BAR_SECONDS) > ATR_MAX_AGE_BARS * BAR_SECONDS:
            return None  # mumlar bayat: eski oynaklikla stop izletme
        return atr(bars)

    def _cost_per_unit(self, instrument: Instrument, settings: BotSettings) -> float:
        """Basa bas seviyesine eklenecek fiyat mesafesi: komisyonun fiyat karsiligi + 1 tick."""
        cost = instrument.tick_size
        commission = self._commission(instrument, settings)
        if commission > 0 and self.account is not None and instrument.contract_size > 0:
            bounds = self.provider.rates.bounds(instrument.currency_profit, self.account.currency)
            if bounds:
                cost += commission / (instrument.contract_size * bounds[0])
        return cost

    def _rearm_level(self, trade: Trade) -> float | None:
        """Eksik stop icin seviye: broker'in en son onayladigi SL ile ilk planlanan SL'den iyi olani.

        Basa basa ya da kara cekilmis bir stop kaybolduysa ilk (-1R) seviyeye geri donulmez.
        Kullanici stopu elle degistirdiyse onun son degeri esas alinir (bot gevsetmez, sikilastirmaz).
        """
        buy = trade.side == "BUY"
        initial = None
        if trade.initial_risk_r_price:
            initial = trade.entry - trade.initial_risk_r_price if buy else trade.entry + trade.initial_risk_r_price
        if trade.last_sl is not None and (trade.user_sl_override or initial is None):
            return trade.last_sl
        if trade.last_sl is None:
            return initial
        return max(trade.last_sl, initial) if buy else min(trade.last_sl, initial)

    async def _guard_stop(self, trade: Trade, quote: dict, now: float) -> bool:
        """Broker'da onaylanmis SL'i olmayan pozisyonu yakalar. True: bu turda baska islem yapma.

        Her bot pozisyonunun broker tarafinda SL'i olmalidir. Once broker'dan dogrulanir; dogrulama
        yapilamadiysa HICBIR sey gonderilmez (yanlis bilgiyle stop ezmek ya da pozisyon kapatmak, stopsuz
        beklemekten kotudur). Gercekten yoksa stop (ve planlanan TP) yeniden kurulur; fiyat seviyeyi
        gectiyse ya da stop tekrar tekrar kurulamiyorsa pozisyon kapatilir.
        """
        position_id = trade.position_id
        if trade.sl is not None and trade.sltp_order_id:
            self._rearm_attempts.pop(position_id, None)
            self._stop_alerted.discard(position_id)
            return False
        interval = STOP_RECHECK if self._rearm_level(trade) is not None else STOP_RECHECK_UNKNOWN
        if now - trade.opened_at < STOP_GRACE or now - self._stop_checked.get(position_id, 0.0) < interval:
            return True
        report = await self.executor.reconcile()  # goruntu SL/TP emirlerini de getirir
        if report is None:
            # Dogrulanamadi: hicbir sey gonderilmez ve kisa bir sure sonra yeniden denenir. Her yonetim
            # turunda (2 sn) denemek, 429 almis bir istegi dongude yinelemek olurdu.
            self._stop_checked[position_id] = now - interval + STOP_VERIFY_RETRY
            return True
        self._stop_checked[position_id] = now
        fresh = self.repo.get_trade(position_id)
        if fresh is None or not fresh.is_open or (fresh.sl is not None and fresh.sltp_order_id):
            return True
        data = {"position_id": position_id, "symbol": fresh.symbol}
        first = position_id not in self._stop_alerted
        self._stop_alerted.add(position_id)
        level = self._rearm_level(fresh)
        if level is None:
            if first:
                await self._record("error", "sl_missing",
                                   f"{fresh.symbol} {fresh.side}: broker'da stop yok ve seviye bilinmiyor. "
                                   "Uygulamadan SL koyun ya da pozisyonu kapatın.", data, notify=True,
                                   title="Stop eksik")
            return True
        buy = fresh.side == "BUY"
        price = quote["bid"] if buy else quote["ask"]
        attempts = self._rearm_attempts.get(position_id, 0)
        if ((price <= level) if buy else (price >= level)) or attempts >= REARM_LIMIT:
            if await self.executor.close(position_id, user=True) is not None:
                reason = "fiyat stop seviyesini geçti" if attempts < REARM_LIMIT else "stop kurulamıyor"
                await self._record("error", "sl_missing",
                                   f"{fresh.symbol} {fresh.side}: broker'da stop yok ve {reason}; pozisyon kapatılıyor.",
                                   {**data, "attempts": attempts}, notify=True, title="Stop eksik")
            return True
        if await self.executor.modify(position_id, sl=level, tp=fresh.planned_tp) is not None:
            self._rearm_attempts[position_id] = attempts + 1
            if first:
                await self._record("error", "sl_missing",
                                   f"{fresh.symbol} {fresh.side}: broker'da stop bulunamadı; {level:g} seviyesine "
                                   "yeniden kuruluyor.", {**data, "sl": level}, notify=True, title="Stop eksik")
        return True

    async def manage_tick(self) -> None:
        settings = self.repo.get_bot_settings()
        now = self._clock()
        await self._auth_ok()
        if self._auth_blocked():
            return  # kimlik reddi suruyor: reddedilecek istekleri gonderme
        failed: Exception | None = None
        for listed in self.repo.open_trades():
            try:
                await self._manage_one(listed, settings, now)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - bir islemdeki hata digerlerinin stop yonetimini durdurmamali
                failed = exc
                # Ilk gorulusunde (ve hata turu degisince) tam iz; sonrasi dongu sayacinda (her 2 sn'de bir iz yazilmaz).
                seen = (listed.position_id, type(exc).__name__)
                if seen not in self._manage_errors:
                    self._manage_errors.add(seen)
                    log.exception("stop yonetimi hatasi: pozisyon %s", listed.position_id)
        if failed is None:
            self._manage_errors.clear()
        else:
            raise failed  # dongu sayaci ve "gorev hata veriyor" uyarisi icin (diger islemler yonetildikten SONRA)

    async def _manage_one(self, listed: Trade, settings: BotSettings, now: float) -> None:
        # Onceki pozisyonun istegi beklenirken bu islem bir olayla degismis ya da kapanmis olabilir.
        trade = self.repo.get_trade(listed.position_id)
        if trade is None or not trade.is_open:
            return
        try:
            instrument = self.catalog.get(trade.symbol)
        except KeyError:
            return
        quote = self.quotes.quote(trade.symbol)
        if quote is None or now - quote["time"] > QUOTE_MAX_AGE:
            return  # bayat fiyatla stop tasima
        if (trade.origin == "bot" or trade.manage) and await self._guard_stop(trade, quote, now):
            return
        if not trade.manage:
            return
        if not trade.partial_done and trade.initial_volume and trade.volume < trade.initial_volume - 1e-9:
            trade.partial_done = True  # kismi kapama gerceklesmis (olay ya da mutabakat hacmi guncelledi)
            self.repo.update_trade(trade.position_id, partial_done=True)
        actions = decide(trade, bid=quote["bid"], ask=quote["ask"], atr_m15=self._atr(trade.symbol),
                         cost_per_unit=self._cost_per_unit(instrument, settings), instrument=instrument,
                         settings=settings.manage)
        if settings.dry_run:
            # Dry-run: bot hicbir emir gondermez; ne yapacagi yalnizca loglanir.
            described = repr(actions)
            if actions and self._dry_logged.get(trade.position_id) != described:
                self._dry_logged[trade.position_id] = described
                log.info("[dry-run] %s %s icin gonderilmeyen yonetim adimi: %s", trade.symbol, trade.side, described)
            return
        for action in actions:
            if isinstance(action, NoOp):
                if action.reason == "partial_skipped":
                    self.repo.update_trade(trade.position_id, partial_done=True)
                continue
            if isinstance(action, MoveSL):
                # Basa bas isareti ve bildirimi, broker degisikligi onaylayinca yurutucu tarafindan yapilir.
                await self.executor.modify(trade.position_id, sl=action.price, stage=action.stage)
            elif isinstance(action, PartialClose):
                await self.executor.close(trade.position_id, volume=action.volume)
            break  # pozisyon basina bir seferde tek istek; sonucu gelince devam edilir

    async def reconcile_now(self) -> bool:
        """Broker durumunu REST ile yeniden okur (kacirilan olaylar icin). Basariliysa True."""
        if self._auth_blocked():
            return False
        report = await self.executor.reconcile()
        if report is not None:
            # Hesap swap'siz (kullanici teyidi 2026-11-26). Broker bu statuyu geri alabilir: gece tasinan bir
            # pozisyonda swap ilk kez sifirdan farkli gorulurse bir kez bildirilir (yalnizca okuma).
            for key in self._observe_swaps(report.positions):
                symbol, _, side = key.partition("|")
                await self._record(
                    "warning", "swap_charged",
                    f"{symbol} {side}: gece taşınan pozisyonda swap (gecelik faiz) uygulanmış görünüyor. Hesabın "
                    "swap'sız statüsünü Exness'te kontrol edin.", {"symbol": symbol, "side": side},
                    notify=True, title="Swap uygulanıyor")
            try:
                # Hesap ayarlari (durum, kaldirac) calisirken degisebilir: marjin kisiti, yalnizca-kapat kipi.
                # Yalnizca acilista okunursa bot bunu emir reddedilene kadar ogrenemezdi. Mutabakat basarili
                # olduktan SONRA okunur: kimlik/baglanti hatalarinin ele alinisi mutabakat yolunda kalir.
                fresh = await self.client.get(schema.account_path(self.client.account_id))
                schema.parse_account(fresh, report.account)  # bicimi bozuk yanit eskisinin yerine GECMEZ
                self._details = fresh
            except (ExnessError, ValueError, TypeError, KeyError) as exc:
                log.warning("hesap ayarlari yenilenemedi: %s", exc)
            self._set_account(report.account)
            blocked = self.account is not None and not self.account.can_open
            if blocked and not self._account_alerted:
                self._account_alerted = True
                await self._record("warning", "account_blocked",
                                   "Hesap yeni işleme kapalı; bot yeni işlem açmıyor, açık işlemler yönetiliyor.",
                                   notify=True, title="Hesap yeni işleme kapalı")
            elif not blocked and self._account_alerted:
                self._account_alerted = False
                await self._record("info", "account_open", "Hesap yeniden yeni işleme açık.")
        return report is not None

    async def resolve_orders(self) -> None:
        if not self._auth_blocked():
            await self.executor.resolve_unknown()

    async def _refresh_news(self) -> None:
        """Takvimi gerektiginde yeniler. Alinamamasi botu durdurmaz; 24 saati asarsa gunde bir kez uyarilir."""
        if self.news is None:
            return
        try:
            if self.news.due():
                await self.news.refresh()
        except Exception:  # takvim kaynagi botun calismasini hicbir kosulda bozmamali
            log.exception("haber takvimi yenilenemedi")
        if self.news.stale() and self.repo.get_bot_settings().news.enabled:
            day = datetime.fromtimestamp(self._clock(), timezone.utc).strftime("%Y-%m-%d")
            if self.repo.get_setting("news_warned_day") != day:
                self.repo.set_setting("news_warned_day", day)
                missing = self.news.never_fetched()
                await self._record(
                    "warning", "news_unavailable",
                    ("Haber takvimi hiç alınamadı. Bot çalışmaya devam ediyor ama haber penceresi koruması "
                     "ÇALIŞMIYOR: önemli haberlerde de işlem açılabilir." if missing else
                     "Haber takvimi 24 saattir alınamıyor. Bot çalışmaya devam ediyor ama haber penceresi "
                     "koruması güncel değil."),
                    {"never_fetched": missing}, notify=True, title="Haber takvimi alınamıyor")

    async def _check_scorecard(self) -> None:
        """Karnesi bozulan stratejiyi duraklatir: golge kipine alir (izlenir, emir acmaz) ve bir kez bildirir."""
        settings = self.repo.get_bot_settings()
        for strategy_id, stats in scorecard.strategies_to_pause(self.repo, settings):
            settings.strategy_modes[strategy_id] = "shadow"
            self.repo.set_bot_settings(settings)  # kalici: yeniden baslatmada da duraklatilmis kalir
            scorecard.mark_paused(self.repo, strategy_id, self._clock(), stats)
            await self._record(
                "error", "strategy_paused",
                f"{strategy_id} duraklatıldı: {stats['trades']} işlemde ortalama {stats['avg_r']:+.2f}R. "
                "Strateji gölgede izlenmeye devam ediyor; uygulamadan yeniden açabilirsiniz.",
                {"strategy_id": strategy_id, "trades": stats["trades"], "avg_r": stats["avg_r"]},
                notify=True, title="Strateji duraklatıldı")

    # ------------------------------------------------------------------ kalp atisi
    async def heartbeat(self) -> None:
        now = self._clock()
        self.repo.set_bot_state(heartbeat_at=now)
        await self._refresh_news()
        await self._check_scorecard()
        if self.account is not None and now - self._last_equity_sample >= EQUITY_SAMPLE_INTERVAL:
            self._last_equity_sample = now
            self.repo.add_equity(now, self.account.balance, self.account.equity)
        down = max((s.disconnected_for() for s in self.streams), default=0.0)
        if down > STREAM_ALERT_AFTER and not self._connection_alerted:
            self._connection_alerted = True
            await self._record("error", "connection_lost",
                               f"Exness bağlantısı {int(down)} saniyedir yok; yeni işlem açılmıyor.",
                               {"seconds": down}, notify=True, title="Bağlantı koptu")
        elif self._connection_alerted and self.streams_up():
            self._connection_alerted = False
            await self._record("info", "connection_restored", "Exness bağlantısı geri geldi.")
        lead, self._tick_lead = self._tick_lead, float("-inf")  # son kalp atisindan beri gorulen en buyuk fark
        # Tek bir ileri tarihli tick uyari uretmez: fark art arda iki kalp atisinda surmeli.
        self._skew_beats = self._skew_beats + 1 if lead > CLOCK_SKEW_LIMIT else 0
        if self._skew_beats >= 2 and not self._clock_alerted:
            self._clock_alerted = True
            await self._record("warning", "clock_skew",
                               f"Sunucu saati fiyat akışının {lead:.0f} sn gerisinde; analiz veriyi bayat sayabilir. "
                               "Sunucuda saat eşitlemesini kontrol edin (timedatectl status).",
                               {"seconds": round(lead, 1)}, notify=True, title="Sunucu saati kaymış")
        elif self._clock_alerted and float("-inf") < lead < CLOCK_SKEW_LIMIT / 2:
            self._clock_alerted = False
            await self._record("info", "clock_ok", "Sunucu saati yeniden fiyat akışıyla uyumlu.")
        if now - self._balance_synced_at >= BALANCE_SYNC_INTERVAL:
            self._balance_synced_at = now
            await self.sync_balance_ops()
        await self._check_limits(self.repo.get_bot_settings())
        connections = getattr(self._events_stream, "connections", 0)
        await self._auth_ok()
        if connections != self._event_connections and await self.reconcile_now():
            # Olay akisi yeniden baglandi: arada kacirilan olaylar icin durum broker'dan toparlandi.
            # Basarisiz olursa sayac guncellenmez; bir sonraki kalp atisinda yeniden denenir.
            self._event_connections = connections
        if self._tick_stream is not None:
            missing = [s for s in self._tick_symbols() if s not in self._subscribed]
            if missing:
                self._subscribed.update(missing)
                await self._tick_stream.subscribe(schema.subscribe_ticks(f"ticks-extra-{int(now)}", missing))

    def scan_summary(self, hours: float = 24.0) -> dict:
        """Son `hours` saatin taramalarinin ozeti: yalnizca sayilar ve nedenler.

        Herkese acik uctan da verilir; bu yuzden hesap numarasi, bakiye, varlik ya da para tutari ICERMEZ.
        Ornek adaylarda lot ve riskin varliga orani (%) vardir; mutlak tutarlar yalnizca yetkili API'dedir.
        """
        now = self._clock()
        since = now - max(0.25, min(float(hours), 168.0)) * 3600.0
        out = {"hours": round((now - since) / 3600.0, 2), "dry_run": self.repo.get_bot_settings().dry_run,
               "scans": 0, "scans_skipped": {}, "symbols_scanned": 0, "candidates": 0, "would_open": 0, "opened": 0,
               "observed": 0, "shadowed": 0, "news_blocked": 0, "portfolio_blocked": 0, "errors": 0,
               "cost_blocked": 0, "cost_by_strategy": {},
               "max_spread_stop_pct": self.repo.get_bot_settings().risk.max_spread_stop_pct,
               "decisions": {}, "veto_reasons": {}, "portfolio_reasons": {}, "observed_reasons": {}, "samples": [],
               "last_data_rejects": {}}

        def add(target: dict, source: object) -> None:
            for key, count in (source.items() if isinstance(source, dict) else ()):
                if isinstance(count, int):
                    # Herkese acik: neden metinlerindeki sayilar (fiyat/tutar olabilir) gizlenir.
                    text = PUBLIC_NUMBER.sub("#", str(key))[:VETO_REASON_CHARS]
                    target[text] = target.get(text, 0) + count

        # Guvenlik tanilamasi: kapanan islemlerde broker tarafinda stop/hedef GORULDU mu (tutar, lot, fiyat yok).
        # `stop_seen`: broker'in onayladigi bir stop seviyesi kaydedildi; `sltp_order`: stop/hedef emri eslestirildi.
        out["positions"] = {
            "sl_missing_events": len(self.repo.events_since(since, ("sl_missing",))),
            "closed": [{"origin": t.origin, "symbol": t.symbol, "side": t.side, "held_s": round(t.closed_at - t.opened_at),
                        "stop_seen": t.last_sl is not None or t.sl is not None, "sltp_order": bool(t.sltp_order_id),
                        "target_seen": t.tp2 is not None or t.planned_tp is not None}
                       for t in reversed(self.repo.closed_trades(since=since, limit=10))]}
        # Olculen gecelik faiz (yillik %, eksi = maliyet; tutar yok). Bos ise henuz gece tasinan pozisyon olmadi.
        observed = self.repo.get_setting("swap_observed", {})
        out["swap_observed"] = observed if isinstance(observed, dict) else {}
        # Broker'in enstruman kosullarinda bildirdigi swap (gece basina puan; [alis, satis]; eksi = maliyet).
        # Piyasa bilgisidir. Swap'siz hesapta uygulanmayabilir: gercekte uygulanan `swap_observed`dadir.
        out["swap_listed"] = {i.symbol: [i.swap_long, i.swap_short] for i in self.catalog.universe()
                              if i.swap_long is not None or i.swap_short is not None}
        # Kimlik retleri (tanilama): an, tur, kod, kaynak, ardisik ret sayisi / duzelme suresi. Tutar ya da kimlik yok.
        out["auth"] = [
            {"at": round(event["at"]), "kind": event["kind"],
             **{key: (event["data"] or {}).get(key) for key in ("code", "status", "source", "streak", "after_seconds")
                if isinstance(event["data"], dict) and event["data"].get(key) is not None}}
            for event in self.repo.events_since(since, ("auth_error", "auth_reject", "auth_restored",
                                                        "market_data_rejected"))][-40:]
        for event in self.repo.events_since(since, ("scan", "scan_skipped", "signal", "signal_observed")):
            data = event["data"] if isinstance(event["data"], dict) else {}
            if event["kind"] == "scan":
                out["scans"] += 1
                for key, field_name in (("symbols_scanned", "scanned"), ("candidates", "candidates"),
                                        ("would_open", "would_open"), ("opened", "opened"), ("observed", "observed"),
                                        ("shadowed", "shadowed"), ("news_blocked", "news_blocked"),
                                        ("portfolio_blocked", "blocked"), ("errors", "errors"),
                                        ("cost_blocked", "cost_blocked")):
                    value = data.get(field_name)
                    out[key] += value if isinstance(value, int) else 0
                add(out["decisions"], data.get("reasons"))
                add(out["veto_reasons"], data.get("veto_reasons"))
                rejects = data.get("data_rejects")  # en son taramaninki kalir
                out["last_data_rejects"] = ({str(k)[:16]: str(v)[:160] for k, v in rejects.items()}
                                            if isinstance(rejects, dict) else {})
                add(out["portfolio_reasons"], data.get("blocked_reasons"))
                add(out["cost_by_strategy"], data.get("cost_reasons"))
            elif event["kind"] == "scan_skipped":
                add(out["scans_skipped"], {data.get("reason") or "?": 1})
            elif event["kind"] == "signal_observed":
                add(out["observed_reasons"], {data.get("reason") or "?": 1})
            elif event["kind"] == "signal":
                entry, stop = data.get("entry"), data.get("stop_loss")
                distance = (round(abs(entry - stop) / entry * 100.0, 4)
                            if isinstance(entry, (int, float)) and isinstance(stop, (int, float)) and entry else None)
                out["samples"].append({
                    "at": event["at"], "symbol": data.get("symbol"), "side": data.get("side"),
                    # Lot YOK: lot + stop mesafesi + risk yuzdesi birlikte varligi ele verir. Lot yetkili API'dedir.
                    "strategy_id": data.get("strategy_id"),
                    "score": round(data["score"], 1) if isinstance(data.get("score"), (int, float)) else None,
                    "net_rr": round(data["net_rr"], 2) if isinstance(data.get("net_rr"), (int, float)) else None,
                    "stop_pct": distance, "risk_pct": data.get("risk_pct"),
                    "dry_run": data.get("dry_run")})
        out["signals"] = len(out["samples"])
        out["samples"] = out["samples"][-SUMMARY_SAMPLES:]
        return out

    async def _backtest_history(self, instruments: list[Instrument], start: float, now: float, path: Path,
                                long_start: float | None = None) -> int:
        """Gecmis mumlari ceker ve sembol sembol dosyaya yazar (bellekte biriktirmez) -> mum sayisi.

        `long_start`: yillik backtest icin butun zaman dilimlerinde daha eski baslangic. Broker o kadar geriye
        vermiyorsa verdigi kadari yazilir; kapsam sonucta ayrica raporlanir."""
        total = failures = 0
        for instrument in instruments:
            rows: list[tuple] = []
            for tf, duration in forward.DURATIONS.items():
                step = (self.candles.max_candles - 1) * duration
                begin = min(start, long_start if long_start is not None else start) - forward.WARMUP_DAYS[tf] * 86400
                if instrument.symbol in week_replica.SYMBOLS and tf in ("H4", "D1"):
                    # WEEK TRADE'in 2 yillik yeniden uretimi icin bu alti sembolde uzun gecmis (isinma payiyla).
                    begin = min(begin, week_replica.START - forward.WARMUP_DAYS[tf] * 86400)
                cursor = int(begin // duration) * duration
                while cursor < now:
                    request = schema.candles_path(self.client.account_id, instrument.broker_symbol, tf, cursor,
                                                  min(now, cursor + step))
                    payload = None
                    for attempt in range(BACKTEST_FETCH_TRIES):
                        try:
                            payload = await self.candles._fetch(request)
                            break
                        except ExnessRateLimited:
                            await self._sleep(BACKTEST_RATE_PAUSE * (attempt + 1))  # salt-okuma: beklenip yinelenir
                        except ExnessError as exc:
                            # Tek bir aralik alinamadi (or. broker o kadar eski veriyi vermiyor): is durmaz, kapsam
                            # sonucta eksik gorunur.
                            log.info("gecmis araligi alinamadi %s %s: %s", instrument.symbol, tf, type(exc).__name__)
                            break
                    if payload is None:
                        failures += 1
                        if failures > BACKTEST_FETCH_FAILURES:
                            raise RuntimeError("gecmis cekilemiyor")
                        cursor += step
                        await self._sleep(BACKTEST_FETCH_PAUSE)
                        continue
                    for r in schema.parse_candles(payload):
                        if r["time"] + duration <= now:
                            rows.append((instrument.symbol, tf, r["time"], r["open"], r["high"], r["low"],
                                         r["close"], float(r.get("volume") or r.get("tick_volume") or 0.0)))
                    cursor += step
                    await self._sleep(BACKTEST_FETCH_PAUSE)
            await asyncio.to_thread(backtest.write_history, path, rows)
            total += len(rows)
        return total

    async def _backtest_spawn(self, job: Path, module: str = "tradebot.forward") -> int:
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", module, str(job),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        return await process.wait()

    async def backtest_once(self) -> dict | None:
        """Ileri test (forward.py, son 90 gun) ve yillik backtest (yeartest.py, 1 ay / 6 ay / 1 yil).

        Yalnizca deneme modunda. Gecmisi bu surec ceker (ayni istemci, yavas); oynatma ayri, dusuk oncelikli
        sureclerdedir. Once ileri testin A asamasi yayinlanir (dakikalar); sonra yillik test turlar halinde surer ve
        her tur sonunda ara sonuc yayinlanir. Yarim kalan is sonraki acilista kaldigi yerden surer (gecmis dosyasi
        ve biten parcalar saklanir). Hicbir hata botu etkilemez. Donus: ileri testin ozeti.
        """
        now = self._clock()
        previous = self.repo.get_setting("yeartest_result")
        fresh = (isinstance(previous, dict) and previous.get("version") == yeartest.VERSION
                 and bool(previous.get("complete"))
                 and now - float(previous.get("finished_at") or 0) < YEAR_MAX_AGE)
        # Disa aktarim kipinde "taze sonuc" denetimi yoktur: her acilista is tanimi yeniden yazilir (gecmis, ayni
        # pencere icin yeniden cekilmez). Boylece yuklenmis bir sonuc yeni pencerenin disa aktarilmasini engellemez.
        if ((fresh and BACKTEST_ON_SERVER) or not self.repo.get_bot_settings().dry_run or self.account is None
                or str(self.repo.db_path) == ":memory:" or self.backtest_state == "running"):
            return None
        self.backtest_state = "running"
        folder = Path(self.repo.db_path).parent / "backtest"
        history = folder / "history.db"
        complete = kept_history = False
        try:
            # Spread: olculmus saatlik medyanlar; olcumu olmayan sembolde su anki 30 dk medyani (yoksa anlik spread).
            profile = {symbol: {"hours": {str(hour): value for hour, value in entry["hours"].items()},
                                "all": entry["all"]} for symbol, entry in self.repo.spread_profile().items()}
            bounds: dict[str, list[float]] = {}
            for instrument in self.catalog.universe():
                symbol = instrument.symbol
                if symbol not in profile:
                    limit, quote = self.quotes.max_spread(symbol), self.quotes.quote(symbol)
                    if limit is None and quote is None:
                        continue
                    profile[symbol] = {"hours": {}, "all": limit / 3.0 if limit is not None else float(quote["spread"])}
                rate = self.provider._bounds(instrument, self.account)
                if rate is None:
                    profile.pop(symbol, None)  # hesap para birimine cevrilemeyen sembol olculmez
                    continue
                bounds[symbol] = [rate[0], rate[1]]
            instruments = sorted((i for i in self.catalog.universe() if i.symbol in profile),
                                 key=lambda i: (i.symbol not in BACKTEST_MAJORS, i.kind != "forex", i.symbol))
            end = float(int(now // 86400) * 86400)  # gun basi
            folder.mkdir(parents=True, exist_ok=True)
            # Yarim kalan isin penceresi saklanir: sonraki gunlerde yeniden baslayan surec ayni pencereyle surer
            # (biten parcalar yeniden hesaplanmaz). Tamamlanmis isten sonra yeni pencere acilir.
            pin = folder / "window.json"
            try:
                pinned = json.loads(pin.read_text())
            except (OSError, ValueError):
                pinned = {}
            finished = (isinstance(previous, dict) and bool(previous.get("complete"))
                        and previous.get("to") == pinned.get("end"))
            if (pinned.get("version") == yeartest.VERSION and isinstance(pinned.get("end"), float)
                    and 0 <= end - pinned["end"] <= BACKTEST_WINDOW_KEEP and not finished):
                end = pinned["end"]
            pin.write_text(json.dumps({"version": yeartest.VERSION, "end": end}))
            start = end - BACKTEST_DAYS * 86400.0
            year_start = end - YEAR_DAYS * 86400.0
            job, result, year_result = folder / "job.json", folder / "result.json", folder / "year.json"
            # Gecmis (bir yil, ~3000 istek) ayni pencere icin bir kez cekilir; yeniden baslatmada yeniden cekilmez.
            marker = folder / "history.json"
            wanted = {"end": end, "year_start": year_start, "symbols": [i.symbol for i in instruments], "format": 2}
            try:
                kept = json.loads(marker.read_text())
            except (OSError, ValueError):
                kept = {}
            if history.exists() and {k: kept.get(k) for k in wanted} == wanted:
                bars = int(kept.get("bars") or 0)
            else:
                # Once is tanimi kaldirilir: gecmis yeniden cekilirken eski tanim "hazir" gorunmesin.
                (folder / "export.json").unlink(missing_ok=True)
                history.unlink(missing_ok=True)
                marker.unlink(missing_ok=True)
                bars = await self._backtest_history(instruments, start, end, history, year_start)
                marker.write_text(json.dumps({**wanted, "bars": bars}))
            manage = self.repo.get_bot_settings().manage
            spec = {
                "instruments": backtest.job_instruments(instruments), "spreads": profile, "bounds": bounds,
                # Sozlesme hesabi icin yalnizca para birimi gerekir; bakiye/varlik sabit bir sayidir (yazilmaz).
                # Kaldirac da yazilmaz (hesap bilgisi): is dosyasi sunucu disina aktarilabilir.
                "account": {"currency": self.account.currency, "balance": 10_000.0, "equity": 10_000.0,
                            "margin": 0.0, "margin_free": 10_000.0, "leverage": None,
                            "can_open": True, "can_trade": True},
                "rules": {"be_at_r": manage.be_at_r if manage.be_enabled else None,
                          "partial_at_r": manage.partial_at_r if manage.partial_enabled else None,
                          "partial_fraction": manage.partial_fraction,
                          "trail_atr_mult": manage.trail_atr_mult if manage.trail_enabled else None},
                "start": start, "end": end, "split": start + (end - start) * 2.0 / 3.0,
                "v9_start": end - BACKTEST_V9_DAYS * 86400.0,
                "year_start": year_start, "chunk_days": YEAR_CHUNK_DAYS, "year_result": str(year_result),
                "v9_ids": sorted(v9.builtin_strategy_ids()),
                "workers": BACKTEST_WORKERS or (os.cpu_count() or 1),
                "max_spread_stop_pct": self.repo.get_bot_settings().risk.max_spread_stop_pct,
                "history": str(history), "result": str(result)}
            if not BACKTEST_ON_SERVER:
                # Hesap sunucuda yapilmaz: is tanimi (yalnizca piyasa verisi ve ayarlar) disa aktarima hazirlanir.
                export = {key: value for key, value in spec.items() if key not in ("history", "result", "year_result")}
                draft = folder / "export.json.new"
                draft.write_text(json.dumps({**export, "bars": bars, "ready": True, "version": yeartest.VERSION}))
                os.replace(draft, folder / "export.json")
                self.backtest_state = "exported"
                kept_history = True
                return None
            # 1) Ileri testin A asamasi (swing + WEEK TRADE yeniden uretimi): dakikalar icinde yayinlanir. V9'un
            #    eski 60 gunluk asamasi artik calismaz; V9 yillik testin icinde olculur.
            job.write_text(json.dumps({**spec, "deadline": time.time() + BACKTEST_BUDGET, "skip_v9": True}))
            result.unlink(missing_ok=True)
            code = await self._backtest_spawn(job)
            if code != 0 or not result.exists():
                raise RuntimeError(f"alt surec {code}")
            summary = json.loads(result.read_text())
            summary["bars"] = bars
            summary["finished_at"] = self._clock()
            self.repo.set_setting("backtest_result", summary)
            # 2) Yillik backtest: turlar halinde; her tur sonunda ara sonuc yayinlanir.
            for _ in range(max(1, YEAR_ROUNDS)):
                job.write_text(json.dumps({**spec, "deadline": time.time() + BACKTEST_BUDGET}))
                year_result.unlink(missing_ok=True)
                code = await self._backtest_spawn(job, "tradebot.yeartest")
                if code != 0 or not year_result.exists():
                    raise RuntimeError(f"yillik alt surec {code}")
                year = json.loads(year_result.read_text())
                year["finished_at"] = self._clock()  # botun saati (tazelik denetimi bununla yapilir)
                self.repo.set_setting("yeartest_result", year)
                progress = year.get("progress") or {}
                log.info("yillik backtest turu bitti: V9 parca %s/%s", progress.get("v9_chunks_done"),
                         progress.get("v9_chunks_total"))
                complete = bool(year.get("complete"))
                if complete:
                    break
            self.backtest_state = "done" if complete else "partial"
            return summary
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - olcum isi botu asla etkilemez
            self.backtest_state = "failed: " + type(exc).__name__
            log.warning("backtest tamamlanamadi: %s", type(exc).__name__, exc_info=log.isEnabledFor(logging.DEBUG))
            return None
        finally:
            (folder / "job.json").unlink(missing_ok=True)
            if complete and not kept_history:  # yarim kalan is icin gecmis dosyasi saklanir (yeniden cekilmesin)
                history.unlink(missing_ok=True)
                (folder / "history.json").unlink(missing_ok=True)

    def export_job(self) -> dict | None:
        """Disa aktarilacak is tanimi (piyasa verisi + ayarlar; hesap verisi yok). Hazir degilse None."""
        try:
            data = json.loads((Path(self.repo.db_path).parent / "backtest" / "export.json").read_text())
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) and data.get("ready") else None

    def export_history_path(self) -> Path | None:
        path = Path(self.repo.db_path).parent / "backtest" / "history.db"
        return path if self.export_job() is not None and path.exists() else None

    async def import_results(self) -> list[str]:
        """Disarida hesaplanip `RESULTS_DIR`e yuklenen sonuc dosyalarini ice alir -> alinanlarin adlari.

        Klasore yalnizca dagitim kullanicisi (kodu da dagitan kimlik) yazabilir; bot oradan yalnizca okur. Dosya
        degismediyse yeniden okunmaz. Surumu ya da bicimi uymayan dosya alinmaz."""
        taken = []
        for name, key, version in (("year.json", "yeartest_result", yeartest.VERSION),
                                   ("forward.json", "backtest_result", forward.VERSION)):
            path = RESULTS_DIR / name
            try:
                stat = path.stat()
                mark = [stat.st_mtime, stat.st_size]
                if stat.st_size > RESULTS_MAX_BYTES or self._results_seen.get(name) == mark:
                    continue
                data = await asyncio.to_thread(lambda: json.loads(path.read_text()))
            except (OSError, ValueError):
                continue
            self._results_seen[name] = mark
            if not isinstance(data, dict) or data.get("version") != version:
                log.warning("sonuc dosyasi alinmadi (surum/bicim uymuyor): %s", name)
                continue
            if name == "year.json" and not yeartest.well_formed(data, self._clock()):
                log.warning("sonuc dosyasi alinmadi (bicim bozuk): %s", name)
                continue
            # Dosyanin kendi bitis zamani korunur (yeniden baslatmada ayni dosya "yeni sonuc" sayilmasin).
            try:
                finished = min(float(data.get("finished_at") or 0.0), self._clock())
            except (TypeError, ValueError):
                finished = 0.0
            data["finished_at"] = finished or self._clock()
            data["imported"] = True
            current = self.repo.get_setting(key)
            if (isinstance(current, dict) and current.get("imported") and current.get("to") == data.get("to")
                    and current.get("finished_at") == data["finished_at"]):
                continue  # ayni sonuc zaten ice alinmis
            self.repo.set_setting(key, data)
            taken.append(name)
            await self._record("info", "backtest_imported", f"Backtest sonucu yüklendi ({name})", {"file": name})
        if taken:
            self.backtest_state = "imported"
        return taken

    def yeartest_report(self, full: bool = False) -> dict:
        """Yillik backtestin son sonucu. `full` degilse sembol tablolari ve egriler cikarilir (herkese acik uc)."""
        result = self.repo.get_setting("yeartest_result")
        result = result if isinstance(result, dict) else None
        try:
            return {"state": self.backtest_state, "result": result if full else yeartest.public(result)}
        except (KeyError, AttributeError, TypeError):
            return {"state": self.backtest_state, "result": None}

    def backtest_report(self) -> dict:
        """Herkese acik: son ileri testin ozeti (yalnizca sayilar ve R)."""
        result = self.repo.get_setting("backtest_result")
        return {"state": self.backtest_state, "result": result if isinstance(result, dict) else None}

    async def _once_after(self, delay: float, action) -> None:
        await self._sleep(delay)
        await action()

    def _observe_swaps(self, positions: list) -> list[str]:
        """Gecelik faiz (swap) OLCUMU, yalnizca okuma: en az bir gece tasinmis acik pozisyonlarda broker'in bildirdigi
        birikmis swap, pozisyon buyuklugune ve gece sayisina oranlanip yillik yuzde olarak saklanir (eksi = maliyet,
        0 = swap yok). Tutar saklanmaz; hicbir karari etkilemez. API'de enstruman bazinda swap orani olmadigi icin
        gercek deger ancak boyle ogrenilir.

        Donus: swap'in ILK KEZ sifirdan farkli goruldugu "SEMBOL|YON" anahtarlari (bildirim icin). Ayni anahtar
        sifira donup yeniden sifirdan farkli olursa yeniden doner."""
        now = self._clock()
        charged: list[str] = []
        try:
            seen = self.repo.get_setting("swap_observed", {})
            seen = dict(seen) if isinstance(seen, dict) else {}
            changed = False
            for position in positions:
                try:  # tek bir pozisyondaki sorun digerlerinin olcumunu dusurmez
                    if (position.closed or position.swap is None or not position.opened_at
                            or not position.open_price or not position.volume):
                        continue  # swap alani yoksa olcum yapilmaz ("0" sayilmaz)
                    nights = (int((now - SWAP_ROLLOVER) // 86400)
                              - int((position.opened_at - SWAP_ROLLOVER) // 86400))
                    if nights < 1:
                        continue
                    symbol = canonical(self.catalog, position.symbol)
                    notional = abs(self.provider.loss_for(symbol, "BUY", position.volume, position.open_price, 0.0))
                    if notional <= 0:
                        continue
                    rate = float(position.swap) / notional / nights * 365.0 * 100.0
                except Exception as exc:  # noqa: BLE001
                    log.info("swap olcumu yapilamadi: %s", type(exc).__name__)
                    continue
                key = f"{symbol}|{position.side}"
                before = seen.get(key) if isinstance(seen.get(key), dict) else None
                if position.swap and (before is None or before.get("zero", True)):
                    charged.append(key)
                seen[key] = {"at": round(now), "nights": nights, "rate_pct_year": round(rate, 3),
                             "zero": not position.swap}
                changed = True
            if changed:
                self.repo.set_setting("swap_observed", seen)
        except Exception as exc:  # noqa: BLE001 - olcum, mutabakati ve stop korumasini asla etkilememeli
            log.info("swap olcumu yapilamadi: %s", type(exc).__name__)
            return []
        return charged

    def lot_guard(self, symbol: str, side: str, lots: float, entry: float | None, stop: float | None) -> None:
        """Mutlak lot tavani: bakiye ve sembole gore. Asilirsa ValueError (emir kurulmaz).

        Ayarlardan BAGIMSIZ, degistirilemeyen son kontrol; bot emirleri ve elle acilan emirler icin aynidir:
        - stopta olusacak zarar varligin %`HARD_MAX_RISK_PCT`'inden buyuk olamaz,
        - pozisyonun toplam buyuklugu (hesap para biriminde) varligin `HARD_MAX_NOTIONAL_X` katini asamaz.
        Varlik ya da kur bilinmiyorsa emir gonderilmez. Normal boyutlandirma (risk %0,25-1) bu tavanin cok
        altindadir; tavan yalnizca yanlis girilmis/hesaplanmis bir lotu (or. 10 lot) durdurur."""
        equity = float(self.account.equity) if self.account is not None else 0.0
        if equity <= 0 or not math.isfinite(equity):
            raise ValueError("hesap varlığı bilinmiyor; emir gönderilmez")
        if entry is None:  # fiyat verilmediyse (piyasa emri) anlik fiyat kullanilir
            quote = self.quotes.quote(symbol)
            entry = None if quote is None else float(quote["ask" if side == "BUY" else "bid"])
        if entry is None or stop is None or lots is None or not lots > 0:
            raise ValueError("lot tavanı denetlenemedi (giriş, stop ya da lot eksik)")
        try:
            loss = -self.provider.loss_for(symbol, side, lots, entry, stop)
            notional = abs(self.provider.loss_for(symbol, "BUY", lots, entry, 0.0))
        except (LookupError, KeyError):
            raise ValueError("lot tavanı denetlenemedi (kur yok)") from None
        if not math.isfinite(loss) or loss <= 0:
            raise ValueError("lot tavanı denetlenemedi (stop girişin yanlış tarafında)")
        if loss > equity * HARD_MAX_RISK_PCT / 100.0:
            raise ValueError(f"lot mutlak üst sınırı aşıyor: stopta zarar varlığın %{HARD_MAX_RISK_PCT:g}'inden fazla")
        if notional > equity * HARD_MAX_NOTIONAL_X:
            raise ValueError(f"lot mutlak üst sınırı aşıyor: pozisyon varlığın {HARD_MAX_NOTIONAL_X:g} katından büyük")

    def entry_paused(self) -> bool:
        """Surec yeni basladi mi (RESTART_ENTRY_PAUSE dolmadi mi)? Doluncaya kadar yeni islem acilmaz."""
        if self._restart_pause <= 0:
            return False
        return self.entries_from is None or self._clock() < self.entries_from

    async def _daily_candles(self, symbol: str) -> None:
        """Gunluk mumlar (swing stratejilerinin yonu ve gunluk ATR'si icin). Yeni bir gunluk mum kapanmadikca ag
        istegi yapilmaz. Bu ikincil bir veridir: gecici bir hatada V9 taramasi etkilenmez; onbellekteki gunluk veri
        bayatladiysa swing stratejileri o sembolde sinyal uretmez (bkz. custom.evaluate)."""
        try:
            await self.candles.get(symbol, "D1", 120)
        except (ExnessRateLimited, ExnessAuthError):
            raise  # istek siniri ve kimlik hatasi taramanin kendi kurallarina gore ele alinir (yutulmaz)
        except ExnessError as exc:
            log.info("gunluk mumlar alinamadi %s: %s", symbol, type(exc).__name__)

    async def record_spreads(self) -> int:
        """Her sembolun son 5 dakikalik spread medyanini kaydeder -> yazilan satir sayisi. Yalnizca olcumdur:
        hicbir kapiyi etkilemez; yazilamazsa sessizce gecer."""
        now = self._clock()
        slot = int(now // SPREAD_STATS_INTERVAL) * SPREAD_STATS_INTERVAL
        rows = []
        for instrument in self.catalog.universe():
            found = self.quotes.recent_median(instrument.symbol, SPREAD_STATS_INTERVAL)
            if found is not None:
                rows.append((instrument.symbol, slot, found[0], found[1]))
        try:
            self.repo.add_spread_stats(rows, now - SPREAD_STATS_KEEP)
        except sqlite3.Error as exc:
            log.warning("spread olcumu yazilamadi: %s", type(exc).__name__)
            return 0
        return len(rows)

    def _spread_r(self, candidate: Candidate) -> float | None:
        spread, risk = self._spread(candidate.symbol), abs(candidate.entry - candidate.stop_loss)
        return round(spread / risk, 4) if spread is not None and risk > 0 else None

    def dryrun_outcomes(self, hours: float = 48.0) -> dict:
        """Deneme modundaki "acilirdi" sinyallerinin ve sanal islemlerin sonucu + saatlik veri sagligi.

        Herkese acik uctan verilir: yalnizca sembol, yon, strateji, puan, zaman ve R cinsinden sonuc. Lot, tutar,
        bakiye ICERMEZ. Benzetim yaklasiktir (bkz. signals/outcome.py).
        """
        from .signals import outcome

        now = self._clock()
        since = now - max(1.0, min(float(hours), 168.0)) * 3600.0
        manage = self.repo.get_bot_settings().manage
        rules = {"be_at_r": manage.be_at_r if manage.be_enabled else None,
                 "partial_at_r": manage.partial_at_r if manage.partial_enabled else None,
                 "partial_fraction": manage.partial_fraction,
                 "trail_atr_mult": manage.trail_atr_mult if manage.trail_enabled else None}
        signals, hourly = [], {}
        for event in self.repo.events_since(since, ("scan", "scan_skipped", "signal")):
            data = event["data"] if isinstance(event["data"], dict) else {}
            if event["kind"] != "signal":
                row = hourly.setdefault(int(event["at"] // 3600 * 3600), {"scans": 0, "skipped": 0, "stale": 0,
                                                                          "insufficient": 0})
                if event["kind"] == "scan_skipped":
                    row["skipped"] += 1
                    continue
                row["scans"] += 1
                reasons = data.get("reasons") if isinstance(data.get("reasons"), dict) else {}
                row["stale"] += int(reasons.get("STALE_DATA") or 0)
                row["insufficient"] += int(reasons.get("INSUFFICIENT_DATA") or 0)
                continue
            item = {"at": event["at"], "symbol": data.get("symbol"), "side": data.get("side"),
                    "strategy_id": data.get("strategy_id"),
                    "score": round(data["score"], 1) if isinstance(data.get("score"), (int, float)) else None,
                    "dry_run": data.get("dry_run"), "result": None}
            try:
                levels = [float(data[k]) for k in ("entry", "stop_loss", "take_profit_1", "take_profit_2")]
                count = min(1500, int((now - event["at"]) // 900) + 40)
                bars = self.candles.cached(str(data["symbol"]), "M15", count)
                item["result"] = outcome.simulate(str(data["side"]), *levels, event["at"], bars, **rules)
                item.update(outcome.shape(str(data["side"]), levels[0], levels[1], event["at"], bars))
                spread = self._spread(str(data["symbol"]))
                item["spread_r"] = data.get("spread_r")  # giristeki (eski kayitlarda yok)
                item["spread_now_r"] = (round(spread / abs(levels[0] - levels[1]), 3)
                                        if spread is not None and levels[0] != levels[1] else None)
            except (KeyError, TypeError, ValueError):
                pass
            signals.append(item)
        shadows, check, checked = [], {"agree": 0, "differ": 0, "unknown": 0, "sl_first_bar": 0, "mfe_ge_1r": 0}, 0
        for r in self.repo.conn.execute(
                "SELECT symbol, side, strategy_id, reason, score, opened_at, closed_at, result_r, "
                "entry, sl, tp, spread FROM shadow_trades WHERE opened_at >= ? ORDER BY opened_at DESC", (since,)):
            item = {"symbol": r[0], "side": r[1], "strategy_id": r[2], "reason": r[3],
                    "score": round(r[4], 1) if r[4] is not None else None, "opened_at": r[5], "closed_at": r[6],
                    "result_r": round(r[7], 3) if r[7] is not None else None,
                    "stop_pct": round(abs(r[8] - r[9]) / r[8] * 100.0, 4) if r[8] else None,
                    "target_r": round(abs(r[10] - r[8]) / abs(r[8] - r[9]), 2) if r[8] != r[9] else None,
                    "spread_r": round(r[11] / abs(r[8] - r[9]), 3) if r[11] is not None and r[8] != r[9] else None}
            # Capraz denetim: ayni islem, golge izleyiciden BAGIMSIZ ikinci hesapla ve onbellekteki gercek mumlarla
            # yeniden sonuclandirilir. Iki sonuc ayni olmali; MFE/MAE islemin nasil gittigini gosterir.
            try:
                # Herkese acik uc olay dongusunde calisir: yalnizca son `SHADOW_CHECK_HOURS` saatte acilan en cok
                # `SHADOW_CHECK_MAX` islem yeniden hesaplanir (islem basi ~1 ms).
                if now - r[5] > SHADOW_CHECK_HOURS * 3600.0 or checked >= SHADOW_CHECK_MAX:
                    raise ValueError("capraz denetim kapsami disinda")
                checked += 1
                count = min(1500, int((now - r[5]) // 900) + 40)
                bars = self.candles.cached(str(r[0]), "M15", count)
                if not bars or bars[0]["time"] > r[5] + 900:
                    raise ValueError("mum gecmisi yetersiz")
                again = outcome.simulate_fixed(str(r[1]), float(r[8]), float(r[9]), float(r[10]), float(r[5]), bars,
                                               spread_at=lambda moment, fixed=float(r[11] or 0.0): fixed)
                item.update({"check_r": again["r"], "mfe_r": again["mfe_r"], "mae_r": again["mae_r"],
                             "bars": again["bars"]})
                if r[7] is not None:
                    same = again["r"] is not None and abs(again["r"] - r[7]) < 0.01
                    check["agree" if same else "differ"] += 1
                    check["sl_first_bar"] += int(again["first"] == "SL" and again["bars"] == 1)
                    check["mfe_ge_1r"] += int(again["mfe_r"] >= 1.0)
            except (TypeError, ValueError):
                check["unknown"] += int(r[7] is not None)
            shadows.append(item)
        shadows.reverse()  # eskiden yeniye (denetim en yenilerden baslar)
        return {"hours": round((now - since) / 3600.0, 2), "rules": rules, "signals": signals, "shadows": shadows,
                "shadow_check": check,
                "hourly": [[hour, *row.values()] for hour, row in sorted(hourly.items())]}

    def quoted_now(self) -> int:
        """Evrende su an taze (QUOTE_MAX_AGE icinde) fiyati olan sembol sayisi."""
        count = 0
        for instrument in self.catalog.universe():
            age = self.quotes.age(instrument.symbol)
            if age is not None and age <= QUOTE_MAX_AGE:
                count += 1
        return count

    def status(self) -> dict:
        state = self.repo.bot_state()
        settings = self.repo.get_bot_settings()
        day = self._day_start()
        bot_today = self.repo.realized_pnl("bot", since=day) + self._unrealized("bot")
        manual_today = self.repo.realized_pnl("manual", since=day) + self._unrealized("manual")
        account = self.account
        return {
            "currency": account.currency if account else None,
            "balance": account.balance if account else None,
            "equity": account.equity if account else None,
            "margin_free": account.margin_free if account else None,
            "pnl_today": {"bot": bot_today, "manual": manual_today, "total": bot_today + manual_today},
            "open_bot": len(self.repo.open_trades("bot")), "open_manual": len(self.repo.open_trades("manual")),
            "halted": state.halted, "halt_reason": state.halt_reason, "stopped": state.stopped,
            "dry_run": settings.dry_run, "start_capital": state.start_capital,
            "last_scan_at": state.last_scan_at, "heartbeat_at": state.heartbeat_at,
            "stream_connected": self.streams_up(), "started": self.started,
            # Uygulama kalp atisinin bayatligini telefon saatine degil bu degere gore olcer.
            "server_time": self._clock(),
        }

    # ------------------------------------------------------------------ zamanlayicilar
    async def _start_with_backoff(self) -> None:
        """Acilis basarisiz olursa surec cokup yeniden baslamaz (istek dongusu olmasin); bekleyip dener."""
        delay = 10.0
        alerted = False
        while True:
            try:
                await self.start()
                return
            except ExnessAuthError as exc:
                if not alerted:
                    alerted = True
                    await self._auth_error(exc)
                delay = 300.0
            except (ExnessError, ValueError) as exc:
                log.error("acilis basarisiz: %s", exc)
                if not alerted:
                    alerted = True
                    await self._record("error", "startup_failed", f"Bot başlatılamadı: {exc}",
                                       notify=True, title="Bot başlatılamadı")
            await self._sleep(delay)
            delay = min(delay * 2, 300.0)

    async def maintenance(self) -> dict | None:
        """Gunde bir kez: SQLite yedegi, eski tarama gurultusunun silinmesi, WAL'in kisaltilmasi.

        Islem yolunu bloklamaz (yedek ayri is parcaciginda, ayri baglantiyla) ve asla dusurmez: hata olursa
        olay + bildirim, bot calismaya devam eder. Ayni gun ikinci kez calismaz; basarisiz gun yeniden denenir.
        """
        now = self._clock()
        today = backup.backup_day(now)
        if self.repo.get_setting("maintenance_day") == today or str(self.repo.db_path) == ":memory:":
            return None
        try:
            result = await asyncio.to_thread(backup.backup_database, self.repo.db_path, now)
        except Exception as exc:  # noqa: BLE001 - bakim hatasi botu durdurmamali
            failures = int(self.repo.get_setting("maintenance_failures", 0)) + 1
            self.repo.set_setting("maintenance_failures", failures)
            # Ilk hatada ve sonra gunde bir kez haber ver; her yarim saatte bildirim yagdirma.
            if self.repo.get_setting("maintenance_alert_day") != today:
                self.repo.set_setting("maintenance_alert_day", today)
                await self._record("warning", "backup_failed", f"Günlük yedek alınamadı: {type(exc).__name__}",
                                   {"failures": failures}, notify=True, title="Yedek alınamadı")
            log.error("yedek alinamadi: %s", type(exc).__name__)  # hata metni dosya yolu icerebilir: yazilmaz
            return None
        pruned = 0
        try:
            pruned = backup.prune_noise(self.repo.conn, now)
            self.repo.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.Error as exc:  # yedek alindi; temizlik yarin yeniden denenir
            log.warning("bakim temizligi tamamlanamadi: %s", type(exc).__name__)
        self.repo.set_setting("maintenance_day", today)
        self.repo.set_setting("maintenance_failures", 0)
        self.repo.set_setting("last_backup_at", now)
        data = {"bytes": result["bytes"], "seconds": result["seconds"], "removed": result["removed"], "pruned": pruned}
        await self._record("info", "backup_done", f"Günlük yedek alındı ({result['bytes'] // 1024} KB)", data)
        return data

    async def _every(self, interval: float, action, name: str) -> None:
        while True:
            await self._sleep(interval)
            try:
                await action()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # tek bir turun hatasi donguyu durdurmamali
                await self._loop_failed(name, exc)
            else:
                self._loop_ok(name)

    def _loop_ok(self, name: str) -> None:
        """Gorev basarili calisti: hata sayaci sifirlanir. Onceki uyari LOOP_STREAK_GAP'ten eskiyse unutulur,
        boylece yeni bir hata dizisi 24 saati beklemeden yeniden haber verir (surekli gidip gelen gorev ise
        her seferinde bildirim yagdirmaz)."""
        self._loop_failures.pop(name, None)
        alerted = self._loop_alerted.get(name)
        if alerted is not None and self._clock() - alerted >= LOOP_STREAK_GAP:
            del self._loop_alerted[name]

    async def _loop_failed(self, name: str, exc: Exception) -> None:
        """Bir zamanlayici gorevinin art arda hatalarini sayar; surerse kullaniciya haber verir (gunde bir yineler)."""
        failures = self._loop_failures.get(name, 0) + 1
        self._loop_failures[name] = failures
        if failures <= 3 or failures % LOOP_LOG_EVERY == 0:  # surekli hata gunlugu doldurmasin
            log.error("%s dongusunde hata (%d. kez art arda): %s", name, failures, type(exc).__name__, exc_info=exc)
        now = self._clock()
        if failures >= LOOP_ALERT_AFTER and now - self._loop_alerted.get(name, float("-inf")) >= LOOP_REALERT:
            self._loop_alerted[name] = now
            try:
                await self._record("error", "loop_failing",
                                   f"Botun '{name}' görevi art arda {failures} kez hata verdi "
                                   f"({type(exc).__name__}). Sunucu günlüğüne bakın.",
                                   {"task": name, "failures": failures}, notify=True,
                                   title="Bot görevi hata veriyor")
            except Exception:  # kayit da yazilamiyorsa (disk dolu) dongu yine de surer
                log.exception("dongu hatasi kaydedilemedi: %s", name)

    def failing_loops(self) -> dict[str, int]:
        """Su an art arda hata veren gorevler -> hata sayisi (/health icin; hesap bilgisi icermez)."""
        return {name: count for name, count in self._loop_failures.items() if count >= LOOP_ALERT_AFTER}

    async def _bar_loop(self) -> None:
        while True:
            now = self._clock()
            boundary = (int(now // BAR_SECONDS) + 1) * BAR_SECONDS + BAR_DELAY
            await self._sleep(max(0.5, boundary - now))
            try:
                await self.on_bar_close()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                await self._loop_failed("tarama", exc)
            else:
                self._loop_ok("tarama")

    async def run(self) -> None:
        await self._start_with_backoff()
        await asyncio.gather(
            *(stream.run() for stream in self.streams),
            self._bar_loop(),
            self._every(MANAGE_INTERVAL, self.manage_tick, "yonetim"),
            self._every(HEARTBEAT_INTERVAL, self.heartbeat, "kalp atisi"),
            self._every(RESOLVE_INTERVAL, self.resolve_orders, "emir cozumleme"),
            self._every(RECONCILE_INTERVAL, self.reconcile_now, "mutabakat"),
            self._every(MAINTENANCE_INTERVAL, self.maintenance, "bakim"),
            self._every(SPREAD_STATS_INTERVAL, self.record_spreads, "spread olcumu"),
            self._once_after(BACKTEST_DELAY, self.backtest_once),
            self._every(RESULTS_INTERVAL, self.import_results, "sonuc ice alma"),
        )


def _version() -> str:
    try:
        return metadata.version("tradebot")
    except metadata.PackageNotFoundError:
        return "?"


_SKIP = {"halted": "bot durduruldu (toplam kayıp sınırı)", "stopped": "kullanıcı durdurdu",
         "stream_down": "Exness bağlantısı yok", "account_blocked": "hesap yeni işleme kapalı",
         "daily_limit": "günlük kayıp sınırı doldu", "market_data_rejected": "mum verisi reddedildi"}
