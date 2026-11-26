"""V9 disindaki (ortak arayuzle yazilmis) stratejilerin adaya cevrilmesi.

Bu stratejiler varsayilan olarak GOLGE kipindedir: sinyalleri sanal islem olarak izlenir, emir gonderilmez.
Canliya almak kullanici onayi ve karne kosulu ister (API). Canliya alinmis bir strateji de V9 adaylariyla
ayni yoldan gecer: guven puani, haber penceresi, portfoy kapisi ve SL zorunlulugu aynen uygulanir.
Lot yalnizca risk butcesinden hesaplanir ve adima ASAGI yuvarlanir.
"""

from __future__ import annotations

import hashlib
import logging
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from .adapter import Candidate, Evaluation
from .modules import Context, Signal, modules

log = logging.getLogger(__name__)
UPPER_MAX_AGE = 4 * 86400.0  # son kapanmis H4/D1 mumu bundan eskiyse swing stratejileri calismaz

MIN_NET_RR = 1.5  # spec §6.2 sert veto
MIN_STOP_SPREADS = 3.0  # stop mesafesi en az bu kadar spread olmali (gurultu stopu olmasin)
BAR_SECONDS = 900
TP2_R = 3.0
QUOTE_MAX_AGE = 60.0  # app.QUOTE_MAX_AGE ile ayni: bundan eski fiyatla giris/lot hesaplanmaz
QUOTE_FUTURE_TOLERANCE = 5.0
# V9 ayni sembolun verisini bu kararlarla reddettiyse yeni stratejiler de o veriyle sinyal uretmez.
V9_DATA_REJECTED = frozenset({"STALE_DATA", "PROVIDER_UNAVAILABLE"})
# V9 raporu yoksa ya da veri yetersizse guven puani anlamsizdir: sinyal yalnizca golgede izlenir.
V9_DEGRADED = frozenset({"INSUFFICIENT_DATA"})


def strategy_ids() -> frozenset[str]:
    return frozenset(m.id for m in modules("strategy"))


def _round(value: float, tick: float, up: bool) -> float:
    quantum = Decimal(str(tick))
    units = (Decimal(str(value)) / quantum).to_integral_value(rounding=ROUND_CEILING if up else ROUND_FLOOR)
    return float(units * quantum)


def _floor_lots(raw: float, step: float) -> float:
    quantum = Decimal(str(step))
    return float((Decimal(str(raw)) / quantum).to_integral_value(rounding=ROUND_FLOOR) * quantum)


def _opposed(report: dict, side: str) -> bool:
    """V9'da ters yonde CONFIRMED bir strateji var mi? (spec §6.2: ayni sembolde ters yonlu onay sert vetodur)"""
    return any(isinstance(row, dict) and row.get("status") == "CONFIRMED" and row.get("direction") not in (None, side)
               for row in (report.get("strategies") or []))


def build_candidate(provider, instrument, signal: Signal, strategy_id: str, *, equity: float, risk_pct: float,
                    quote: dict, commission_per_lot: float = 0.0) -> tuple[Candidate | None, str]:
    """Sinyali emre hazir adaya cevirir -> (aday | None, neden)."""
    buy = signal.side == "BUY"
    sign = 1.0 if buy else -1.0
    tick = instrument.tick_size
    entry = quote["ask"] if buy else quote["bid"]  # gercek giris fiyati: spread maliyeti dahil
    # Stop zarar yonunde uzaga, hedef yakina yuvarlanir: yuvarlama riski buyutmez, R/R'yi sisirmez.
    stop = _round(signal.stop, tick, up=not buy)
    distance = (entry - stop) * sign
    if distance <= 0:
        return None, "stop girisin yanlis tarafinda"
    if distance < MIN_STOP_SPREADS * quote["spread"]:
        return None, "stop mesafesi spread'e gore cok dar"
    target = _round(entry + sign * 2.0 * distance, tick, up=not buy)
    commission = max(0.0, float(commission_per_lot or 0.0))
    try:
        # Zarar: stopa gidis + gidis-donus komisyon. Kazanc: hedefe gidis - komisyon. Ikisi de hesap para biriminde.
        loss_per_lot = -provider.loss_for(instrument.symbol, signal.side, 1.0, entry, stop) + commission
        gain_per_lot = provider.loss_for(instrument.symbol, signal.side, 1.0, entry, target) - commission
    except (LookupError, KeyError):
        return None, "hesap para birimine donusum kuru yok"
    if loss_per_lot <= 0 or equity <= 0:
        return None, "risk hesaplanamadi"
    net_rr = gain_per_lot / loss_per_lot  # spread (giris fiyatinda) ve komisyon dusulmus
    if net_rr < MIN_NET_RR:
        return None, "net R/R 1.5'in altinda"
    budget = equity * risk_pct / 100.0
    step = instrument.volume_step or instrument.volume_min
    # En buyuk lot da adima ASAGI yuvarlanir: adim disi bir lot gonderimde yukari yuvarlanabilirdi.
    lots = min(_floor_lots(budget / loss_per_lot, step),
               _floor_lots(instrument.volume_max, step) if instrument.volume_max else float("inf"))
    if lots < instrument.volume_min or lots <= 0:
        return None, "en kucuk lot risk butcesini asiyor"
    key = f"{strategy_id}|{instrument.symbol}|{signal.side}|{signal.bar_time}"
    return Candidate(
        symbol=instrument.symbol, side=signal.side, entry=entry, stop_loss=stop, take_profit_1=target,
        take_profit_2=_round(entry + sign * TP2_R * distance, tick, up=not buy), lots=lots, strategy_id=strategy_id,
        setup_id=hashlib.sha1(key.encode()).hexdigest()[:24], net_rr=net_rr,
        analysis_id=hashlib.sha256(key.encode()).hexdigest(), risk_amount=loss_per_lot * lots), "ok"


def evaluate(provider, instrument, *, equity: float, risk_pct: float, modes: dict[str, str], now: float,
             report: object | None = None, v9_decisions: tuple[str, ...] = (),
             commission_per_lot: float = 0.0) -> list[Evaluation]:
    """Kipi `off` olmayan her yeni stratejiyi calistirir; yalnizca aday ureten sonuclar doner.

    `v9_decisions`: V9'un ayni sembol icin bu taramadaki kararlari. V9 veriyi bayat/erisilemez bulduysa
    sinyal uretilmez; rapor yoksa ya da veri yetersizse canli strateji de yalnizca golgede izlenir."""
    if V9_DATA_REJECTED.intersection(v9_decisions):
        return []
    degraded = report is None or bool(V9_DEGRADED.intersection(v9_decisions))
    active = [m for m in modules("strategy") if modes.get(m.id, "shadow") != "off"]
    if not active:
        return []
    symbol = instrument.symbol
    try:
        quote = provider.quote(symbol)
    except LookupError:
        return []
    # Fiyat TAZE olmali: giris ve lot bu fiyattan hesaplanir. Bayat fiyatla stop mesafesi kuculur, lot katlanir.
    if not (-QUOTE_FUTURE_TOLERANCE <= now - quote["time"] <= QUOTE_MAX_AGE):
        return []
    bars = {frame: provider.candles(symbol, frame, 256) for frame in ("M15", "H1")}
    # Swing stratejileri ust zaman dilimlerini de okur; onbellekte yoksa bos gelir ve o stratejiler sinyal uretmez.
    for frame, count, seconds in (("H4", 120, 14400), ("D1", 90, 86400)):
        try:
            found = provider.candles(symbol, frame, count)
        except (LookupError, KeyError):
            found = []
        # Bayat ust zaman dilimi (yenilenememis onbellek) kullanilmaz: hafta sonu + tatil payi kadar eski olabilir.
        if found and now - (found[-1]["time"] + seconds) > UPPER_MAX_AGE:
            found = []
        bars[frame] = found
    m15 = bars["M15"]
    # Yalnizca kapanmis ve GUNCEL mum: son kapanmis M15 mumu az once kapanmis olmali (bakis-ileri ve bayat veri yok).
    if not m15 or not (0 <= now - (m15[-1]["time"] + BAR_SECONDS) < BAR_SECONDS):
        return []
    data = report if isinstance(report, dict) else (report.model_dump() if report is not None else {})
    context = Context(symbol=symbol, now=now, kind=instrument.kind, report=data, bars=bars, quote=quote,
                      instrument=instrument)
    results: list[Evaluation] = []
    for module in active:
        try:
            signal = module.evaluate(context)
        except Exception:  # noqa: BLE001 - tek bir strateji taramayi dusurmemeli
            log.exception("strateji hata verdi: %s %s", module.id, symbol)
            continue
        if not isinstance(signal, Signal):
            continue
        if signal.bar_time != m15[-1]["time"]:
            continue  # strateji son kapanmis mumdan baska bir mumu kullanmis
        if _opposed(data, signal.side):
            log.info("yeni strateji adayi elendi %s %s: V9'da ters yonlu onay", module.id, symbol)
            continue
        candidate, why = build_candidate(provider, instrument, signal, module.id, equity=equity, risk_pct=risk_pct,
                                         quote=quote, commission_per_lot=commission_per_lot)
        if candidate is None:
            log.info("yeni strateji adayi elendi %s %s: %s", module.id, symbol, why)
            continue
        results.append(Evaluation(symbol, f"{signal.side}_CANDIDATE", (signal.reason,), candidate, report,
                                  mode="shadow" if degraded else modes.get(module.id, "shadow")))
    return results
