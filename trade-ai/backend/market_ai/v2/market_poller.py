"""Public market observations -> atomic paper events; no exchange order path."""
from .errors import V2Error
from .market_data_contract import Instrument, validate_series
from .paper_ledger import dec, text
from .spot_provider import ProviderUnavailable


class MarketPoller:
    def __init__(self, runtime):
        self.runtime = runtime

    def active_symbols(self):
        db = self.runtime.db
        with db.transaction() as c:
            pending = {o["symbol"] for o in db.rows(c,"orders") if o["status"] in ("pending","partially_filled")}
            pending.update(p["symbol"] for p in db.rows(c,"positions") if dec(p["quantity"]) > 0)
            return sorted(pending)

    def poll(self, symbols, *, on_event=None):
        r, results = self.runtime, []
        db, provider, now = r.db, r.analysis.provider, r.clock()
        recovery_pending = False
        for symbol in sorted(set(symbols)):
            with db.transaction() as c:
                positions = [p for p in db.rows(c,"positions") if p["symbol"] == symbol and dec(p["quantity"]) > 0]
                orders = [o for o in db.rows(c,"orders") if o["symbol"] == symbol and o["status"] in ("pending","partially_filled")]
                if not positions and not orders:
                    continue
                # An idle period needs no historical marks. The ledger still
                # checks continuity whenever an exposure actually spans a gap.
                first = min([o["created_at_ms"] for o in orders] + [p["mark_time_ms"] for p in positions])
                last = c.execute("SELECT MAX(close_ms) FROM events WHERE symbol=?",(symbol,)).fetchone()[0]
            try:
                bars = provider.candles(symbol,"1m",now)
            except ProviderUnavailable as exc:
                raise V2Error("PROVIDER_UNAVAILABLE","Public spot source unavailable; no fixture fallback",503) from exc
            identity = Instrument(symbol,"crypto_spot",provider.venue,"last","spot","USDT")
            def check(series, timestamp, max_age):
                quality = validate_series(series,timeframe_ms=60000,as_of_ms=timestamp,max_age_ms=max_age)
                if not quality.ok or any(b.instrument != identity or b.source != provider.source_name or b.volume_kind != "real"
                                          or b.open_time_ms % 60000 or b.close_time_ms % 60000 for b in series):
                    raise V2Error("MARKET_DATA_INVALID","Poll input failed source/spot identity/closed-candle checks",503)
            check(bars, now, 60000)
            required = max((first+59999)//60000*60000, last if last is not None else 0)
            boundary = now//60000*60000
            historical = False
            if bars and bars[0].open_time_ms > required and required < boundary:
                # Bound memory/network/lock time to one historical page per
                # symbol/tick. Progress is committed; scanner blocks new risk
                # until all active exposure has consecutive current marks.
                if not callable(getattr(provider, "candle_window", None)):
                    raise V2Error("PAPER_HISTORY_UNAVAILABLE", "Missing closed bars; provider has no verified historical adapter", 503)
                end = min(required+300*60000, boundary)
                try:
                    bars = provider.candle_window(symbol, required, end)
                except ProviderUnavailable as exc:
                    raise V2Error("PROVIDER_UNAVAILABLE", "Historical spot source unavailable; recovery remains blocked", 503) from exc
                historical = True
                if not bars or bars[0].open_time_ms != required or bars[-1].close_time_ms != end:
                    raise V2Error("PAPER_HISTORY_INCOMPLETE", "Historical window boundaries are incomplete; no prices invented", 503)
            check(bars, bars[-1].close_time_ms if historical else now, 0 if historical else 60000)
            with db.transaction() as c:
                for b in bars:
                    if b.open_time_ms < first or (last is not None and b.close_time_ms <= last):
                        continue
                    event = {k:text(getattr(b,k)) for k in ("open","high","low","close","volume")}
                    event.update(symbol=symbol,open_time_ms=b.open_time_ms,close_time_ms=b.close_time_ms,is_final=b.is_final)
                    result=r.ledger.event(c,event,now)
                    if on_event is not None:
                        on_event(c,result)
                    results.append(result)
                if historical and bars[-1].close_time_ms < boundary:
                    remaining = any(p["symbol"] == symbol and dec(p["quantity"]) > 0 for p in db.rows(c,"positions"))
                    remaining |= any(o["symbol"] == symbol and o["status"] in ("pending","partially_filled") for o in db.rows(c,"orders"))
                    recovery_pending |= remaining
        if recovery_pending:
            raise V2Error("PAPER_RECOVERY_IN_PROGRESS", "Consecutive historical page committed; poll again before creating new risk", 409)
        return {"data_mode":db.mode,"events":results,"scheduler":"explicit_poll_only"}
