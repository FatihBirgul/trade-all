"""Servis dongusu: tara -> sinyal -> risk kapisi -> emir -> pozisyon yonetimi.

Zamanlayicilar `run()` icindedir; `on_bar_close`, `manage_tick` ve `heartbeat` tek tek cagrilabilir
oldugu icin testler gercek saat ve ag olmadan tum akisi calistirir.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from .config import BotSettings, Settings, strategy_mode
from .execution.executor import Executor
from .execution.reconcile import fetch_all_deals, reconcile
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
from .signals import v9
from .signals import fusion, scorecard
from .signals.adapter import Candidate, Evaluation, evaluate_all
from .signals.shadow import ShadowBook
from .signals.provider import ExnessV9Provider
from .store.repo import BotState, Repo

log = logging.getLogger(__name__)

FRAMES = ("M15", "H1", "H4")
BAR_SECONDS = 900
BAR_DELAY = 5.0  # mumun broker tarafinda kesinlesmesi icin kapanistan sonra bekleme
MANAGE_INTERVAL = 2.0
HEARTBEAT_INTERVAL = 30.0
RESOLVE_INTERVAL = 10.0
STREAM_ALERT_AFTER = 60.0
QUOTE_MAX_AGE = 60.0
EQUITY_SAMPLE_INTERVAL = 300.0
BALANCE_SYNC_INTERVAL = 300.0  # para yatirma/cekme icin deal gecmisi bu aralikla taranir (olay kacmis olabilir)
BALANCE_HISTORY_DAYS = 29  # gecmis sorgusu sinirinin (30 gun) icinde kalinir
BASE_LIVE = "capital_base_live"  # ayar anahtari: sermaye tabani canli moda geciste alindi mi
RECONCILE_INTERVAL = 300.0  # olay kacirilmis olabilir: broker durumu duzenli olarak yeniden okunur
AUTH_BACKOFF_START = 30.0  # kimlik reddinden sonra yonetim isteklerinin durdugu sure (art arda redde katlanir)
AUTH_BACKOFF_MAX = 300.0
AUTH_ALERT_TTL = 3600.0  # bu sureden sonra yeni bir kimlik reddi yeniden bildirilir
STOP_GRACE = 5.0  # dolumdan sonra SL/TP emrinin gorulmesi icin taninan sure
STOP_RECHECK = 30.0
STOP_RECHECK_UNKNOWN = 300.0  # seviye bilinmiyorsa (elle mudahale gerekir) daha seyrek kontrol
REARM_LIMIT = 3  # stop bu kadar denemede kurulamazsa pozisyon kapatilir
ATR_MAX_AGE_BARS = 3
TICK_CHUNK = 20


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
    reasons: dict[str, int] = field(default_factory=dict)
    blocked_reasons: dict[str, int] = field(default_factory=dict)


def _default_stream_factory(client, path, on_message, name):
    return Stream(client, path, on_message, name=name)


class Bot:
    def __init__(self, settings: Settings, client, repo: Repo, notifier, clock: Callable[[], float] = time.time,
                 *, stream_factory=None, sleep=asyncio.sleep, news=None):
        self.settings = settings
        self.client = client
        self.repo = repo
        self.notifier = notifier
        self._clock = clock
        self._sleep = sleep
        self.news = news  # NewsCalendar | None (None: haber filtresi yok)
        self._stream_factory = stream_factory or _default_stream_factory
        self.catalog = InstrumentCatalog(client)
        self.quotes = QuoteBook(clock=clock)
        self.candles = CandleStore(repo.conn, client, self.catalog, clock=clock)
        self.account: Account | None = None
        self.provider = ExnessV9Provider(self.catalog, self.candles, self.quotes, lambda: self.account)
        self.executor = Executor(client, repo, notifier, self.catalog, clock=clock,
                                 on_auth_error=self._auth_error)
        self.shadow = ShadowBook(repo)
        self.streams: list = []
        self.started = False
        self._details: dict | None = None
        self._tick_stream = None
        self._subscribed: set[str] = set()
        self._connection_alerted = False
        self._daily_blocked = False
        self._last_equity_sample = 0.0
        self._balance_synced_at = 0.0
        self.last_scan: ScanSummary | None = None
        self._limits = schema.Limits()
        self._events_stream = None
        self._event_connections = 0
        self._auth_alerted = False
        self._auth_alerted_at = 0.0
        self._auth_error_at = 0.0
        self._auth_backoff = AUTH_BACKOFF_START
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
        universe = self.catalog.universe(self.repo.get_bot_settings().enabled_symbols)
        await self._record("info", "bot_started", f"Bot başladı: {len(universe)} sembol izleniyor",
                           {"universe": len(universe), "catalog_errors": len(catalog_errors),
                            "dry_run": self.repo.get_bot_settings().dry_run})

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
            return
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
                self.repo.set_bot_state(start_capital=account.equity, start_at=now)
            return
        if settings.dry_run:
            if state.start_capital != account.equity or state.start_at is None:
                self.repo.set_bot_state(start_capital=account.equity,
                                        start_at=state.start_at if state.start_at is not None else now)
            return
        self.repo.set_bot_state(start_capital=account.equity, start_at=now)
        self.repo.set_setting(BASE_LIVE, True)
        self._balance_synced_at = now  # bu andan onceki bakiye islemleri tabanin icindedir
        await self._record(
            "info", "capital_base",
            f"Canlı mod: kayıp sınırları {account.equity:.2f} {account.currency} üzerinden ölçülecek "
            f"(günlük %{settings.risk.daily_loss_pct:g}, toplam %{settings.risk.total_loss_pct:g}).",
            {"start_capital": account.equity, "currency": account.currency}, notify=True,
            title="Canlı mod başladı")

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
        if deal.type != "balance" or not deal.profit:
            return
        state = self.repo.bot_state()
        at = deal.time if deal.time is not None else self._clock()
        apply = (self._base_is_live() and state.start_capital is not None and state.start_at is not None
                 and at > state.start_at)
        base = self.repo.apply_balance_op(deal.id, at, deal.profit, apply=apply)
        if base is None:
            return
        unit = f" {self.account.currency}" if self.account is not None else ""
        kind = "Para yatırma" if deal.profit > 0 else "Para çekme"
        await self._record(
            "info", "balance_change",
            f"{kind}: {deal.profit:+.2f}{unit}. Kayıp sınırı tabanı {state.start_capital:.2f} → {base:.2f}{unit}; "
            "bu tutar bot kârı/zararı sayılmaz.",
            {"amount": deal.profit, "start_capital": base}, notify=True, title=kind)

    async def sync_balance_ops(self) -> None:
        """Deal gecmisinden para yatirma/cekme islemlerini toplar (olay akisi kacirmis olabilir)."""
        state = self.repo.bot_state()
        if not self._base_is_live() or state.start_at is None or self._auth_blocked():
            return
        now = self._clock()
        watermark = float(self.repo.get_setting("balance_synced_at", 0.0) or 0.0)
        since = max(state.start_at, watermark - 600.0, now - BALANCE_HISTORY_DAYS * 86400.0)
        try:
            deals = await fetch_all_deals(self.client, since)
        except ExnessAuthError as exc:
            await self._auth_error(exc)
            return
        except ExnessError as exc:
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
        """
        now = self._clock()
        self._auth_error_at = now
        self._auth_blocked_until = now + self._auth_backoff
        self._auth_backoff = min(self._auth_backoff * 2, AUTH_BACKOFF_MAX)
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
        self._auth_blocked_until = 0.0
        self._auth_backoff = AUTH_BACKOFF_START
        if was_alerted:
            await self._record("info", "auth_restored", "Exness kimlik doğrulaması yeniden çalışıyor.")

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
            except ExnessAuthError as exc:
                await self._auth_error(exc)
                summary.skipped = "auth_error"
                return summary
            except ExnessRateLimited as exc:
                # Limit asildi: bu turu birak, dongude tekrar deneme.
                summary.errors += 1
                summary.skipped = "rate_limited"
                await self._record("warning", "rate_limited", f"İstek limiti doldu; tarama yarıda kesildi ({exc})")
                return summary
            except (ExnessError, ValueError) as exc:
                summary.errors += 1
                log.warning("mumlar alinamadi %s: %s", symbol, exc)
                continue
            scanned.add(symbol)
            await self._auth_ok()
            modes = {s: strategy_mode(settings, s) for s in v9.builtin_strategy_ids()}
            results = evaluate_all(self.provider, symbol, equity=self.account.equity, risk_pct=settings.risk.risk_pct,
                                   commission_per_lot=self._commission(instrument, settings), modes=modes, now=now)
            summary.scanned += 1
            await asyncio.sleep(0)  # analiz islemciyi tutar; pozisyon yonetimine sira ver
            for result in results:
                if result.candidate is None:
                    summary.reasons[result.decision] = summary.reasons.get(result.decision, 0) + 1
                    log.info("aday yok %s: %s (%s)", symbol, result.decision, "; ".join(result.reasons))
                    continue
                summary.candidates += 1
                await self._consider(result, instrument, settings, summary)

        for symbol in self.shadow.open_symbols():  # sanal islemleri kapanmis mumlarla sonuclandir
            try:
                self.catalog.get(symbol)
                if symbol not in scanned:
                    await self.candles.get(symbol, "M15", 128)
                    scanned.add(symbol)
                self.shadow.resolve(symbol, self.candles.cached(symbol, "M15", 128), now)
            except (ExnessError, ValueError, KeyError):
                continue
        await self._refresh_open_candles(scanned)
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
        score, votes, multiplier = self._score(result, instrument, settings)
        if result.mode == "shadow":
            # Golge kipindeki strateji: sinyali ve sanal sonucu izle, gercek emir gonderme.
            reason = "paused" if candidate.strategy_id in scorecard.paused(self.repo) else "shadow"
            if self.shadow.open(candidate, reason, score, self._clock()):
                summary.shadowed += 1
            return
        if multiplier is None:
            self.shadow.open(candidate, "low_score", score, self._clock())
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
        data = {**dataclasses.asdict(candidate), "dry_run": settings.dry_run, "score": score, "votes": votes}
        text = (f"{candidate.symbol} {candidate.side} {candidate.lots:g} lot @ {candidate.entry:g}, "
                f"SL {candidate.stop_loss:g}, TP {candidate.take_profit_2:g} ({candidate.strategy_id})")
        if settings.dry_run:
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
            return True  # dogrulanamadi: bir sonraki turda yeniden dene (kontrol hakki harcanmaz)
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
        for listed in self.repo.open_trades():
            # Onceki pozisyonun istegi beklenirken bu islem bir olayla degismis ya da kapanmis olabilir.
            trade = self.repo.get_trade(listed.position_id)
            if trade is None or not trade.is_open:
                continue
            try:
                instrument = self.catalog.get(trade.symbol)
            except KeyError:
                continue
            quote = self.quotes.quote(trade.symbol)
            if quote is None or now - quote["time"] > QUOTE_MAX_AGE:
                continue  # bayat fiyatla stop tasima
            if (trade.origin == "bot" or trade.manage) and await self._guard_stop(trade, quote, now):
                continue
            if not trade.manage:
                continue
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
                continue
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
            self._set_account(report.account)
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
                await self._record(
                    "warning", "news_unavailable",
                    "Haber takvimi 24 saattir alınamıyor. Bot çalışmaya devam ediyor ama haber penceresi "
                    "koruması güncel değil.", notify=True, title="Haber takvimi alınamıyor")

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

    async def _every(self, interval: float, action, name: str) -> None:
        while True:
            await self._sleep(interval)
            try:
                await action()
            except asyncio.CancelledError:
                raise
            except Exception:  # tek bir turun hatasi donguyu durdurmamali
                log.exception("%s dongusunde hata", name)

    async def _bar_loop(self) -> None:
        while True:
            now = self._clock()
            boundary = (int(now // BAR_SECONDS) + 1) * BAR_SECONDS + BAR_DELAY
            await self._sleep(max(0.5, boundary - now))
            try:
                await self.on_bar_close()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("tarama dongusunde hata")

    async def run(self) -> None:
        await self._start_with_backoff()
        await asyncio.gather(
            *(stream.run() for stream in self.streams),
            self._bar_loop(),
            self._every(MANAGE_INTERVAL, self.manage_tick, "yonetim"),
            self._every(HEARTBEAT_INTERVAL, self.heartbeat, "kalp atisi"),
            self._every(RESOLVE_INTERVAL, self.resolve_orders, "emir cozumleme"),
            self._every(RECONCILE_INTERVAL, self.reconcile_now, "mutabakat"),
        )


_SKIP = {"halted": "bot durduruldu (toplam kayıp sınırı)", "stopped": "kullanıcı durdurdu",
         "stream_down": "Exness bağlantısı yok", "account_blocked": "hesap yeni işleme kapalı",
         "daily_limit": "günlük kayıp sınırı doldu"}
