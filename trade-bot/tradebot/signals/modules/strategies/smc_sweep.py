"""SMC: likidite supurmesi + displacement + yapi kirilimi + Order Block/FVG ortusmesi (swing ailesi).

Kurulum H1 mumlariyla aranir, giris kapanmis bir M15 tetik mumuyla verilir. AL (SAT ayna goruntusu):
1. Gunluk yon yukari (bkz. swing_rules.daily_bias).
2. Supurme: son 24 H1 mumundan biri, kendisinden onceki bir donus dibinin ALTINA igne atip USTUNDE kapanmis.
3. Displacement: supurmeden sonraki 6 H1 mumu icinde govdesi >= 1 x H1 ATR olan yukselen bir mum.
4. Yapi kirilimi (BOS/CHoCH): o mum ya da sonrasi, supurmeden onceki son donus tepesinin ustunde kapanmis.
5. Ilgi bolgesi (POI): Order Block (displacement'tan onceki son dusen H1 mumunun araligi) ve ona bitisik ya da
   onunla ortusen FVG'nin (displacement'in onceki mumunun tepesi ile sonraki mumunun dibi arasindaki bosluk)
   alt yarisi. FVG yoksa ya da Order Block'a degmiyorsa kurulum sayilmaz.
6. Giris: fiyat POI'ye donmus (M15 dibi <= POI ustu) ve son kapanmis M15 mumu bir tetik mumu: yutan mum
   (engulfing) ya da pinbar (alt igne >= 2 x govde, kapanis araligin ust ucte birinde); kapanis POI'nin altinda degil.
   POI'de bekleyen limit emir surumu yazilmadi; yalnizca kapanmis tetik mumu kullanilir.
Kurulum, supurulen dibin altinda bir H1 kapanisiyla ya da kirilimdan 48 H1 mumu sonra gecersiz olur.
Stop: supurulen dibin 0,1 x H1 ATR altinda; en az 1,5 x gunluk ATR uzakta. Hedef varsayilan 2R.
"""

from __future__ import annotations

from ..base import Context, Signal
from ..indicators import atr, pivots
from .swing_rules import daily_bias, plan

SWEEP_WINDOW = 24
DISPLACEMENT_WITHIN = 6
SETUP_LIFE = 48
PIVOT_LOOKBACK = 60


def _mirror(bars: list[dict], sign: float) -> list[dict]:
    """SAT icin fiyatlari ters cevirir: boylece tek bir (AL) kural kumesi iki yonde de kullanilir."""
    if sign > 0:
        return bars
    return [{"time": b["time"], "open": -b["open"], "high": -b["low"], "low": -b["high"], "close": -b["close"]}
            for b in bars]


def find_setup(h1: list[dict]) -> dict | None:
    """Yukari yonlu kurulum -> {sweep_low, poi_low, poi_high, broke_at} (en yenisi) ya da None."""
    width = atr(h1)
    if not width or len(h1) < PIVOT_LOOKBACK:
        return None
    highs, lows = pivots(h1)
    last = len(h1) - 1
    for sweep in range(last - 2, max(last - SWEEP_WINDOW, 4), -1):  # en yeni supurmeden geriye
        bar = h1[sweep]
        prior_lows = [i for i in lows if sweep - PIVOT_LOOKBACK <= i <= sweep - 3]
        swept = [h1[i]["low"] for i in prior_lows if bar["low"] < h1[i]["low"] < bar["close"]]
        if not swept:
            continue
        prior_highs = [i for i in highs if sweep - PIVOT_LOOKBACK <= i < sweep]
        if not prior_highs:
            continue
        structure_high = h1[prior_highs[-1]]["high"]
        for move in range(sweep + 1, min(sweep + DISPLACEMENT_WITHIN, last - 1) + 1):
            candle = h1[move]
            if candle["close"] - candle["open"] < width:
                continue
            broke = next((i for i in range(move, last + 1) if h1[i]["close"] > structure_high), None)
            if broke is None or last - broke > SETUP_LIFE:
                continue
            block = next((h1[i] for i in range(move - 1, sweep - 1, -1) if h1[i]["close"] < h1[i]["open"]), None)
            if block is None:
                continue
            gap_low, gap_high = h1[move - 1]["high"], h1[move + 1]["low"]
            if gap_high <= gap_low or block["high"] < gap_low - 0.1 * width:
                continue  # FVG yok ya da Order Block'a degmiyor
            poi_low, poi_high = block["low"], gap_low + (gap_high - gap_low) / 2.0
            sweep_low = bar["low"]
            if any(b["close"] < sweep_low for b in h1[sweep + 1:]):
                continue  # kurulum bozuldu
            return {"sweep_low": sweep_low, "poi_low": poi_low, "poi_high": poi_high, "broke_at": h1[broke]["time"]}
    return None


def trigger(m15: list[dict], poi_low: float, poi_high: float) -> bool:
    """Son kapanmis M15 mumu POI'ye degmis bir yukselis tetik mumu mu (yutan mum ya da pinbar)?"""
    if len(m15) < 2:
        return False
    bar, previous = m15[-1], m15[-2]
    span = bar["high"] - bar["low"]
    if span <= 0 or bar["low"] > poi_high or bar["close"] < poi_low or bar["close"] <= bar["open"]:
        return False
    body = bar["close"] - bar["open"]
    engulfing = previous["close"] < previous["open"] and bar["close"] > previous["open"] and bar["open"] <= previous["close"]
    pinbar = (min(bar["open"], bar["close"]) - bar["low"]) >= 2.0 * body and bar["close"] >= bar["high"] - span / 3.0
    return engulfing or pinbar


class SmcSweep:
    id, kind = "tb_smc_sweep_v1", "strategy"

    def evaluate(self, context: Context) -> Signal | None:
        m15, h1 = context.bars.get("M15") or [], context.bars.get("H1") or []
        if len(m15) < 3 or len(h1) < PIVOT_LOOKBACK:
            return None
        bias = daily_bias(context.bars.get("D1") or [], context.bars.get("H4") or [])
        if bias is None:
            return None
        sign = 1.0 if bias == "bullish" else -1.0
        setup = find_setup(_mirror(h1, sign))
        if setup is None:
            return None
        flipped = _mirror(m15[-3:], sign)
        # Tetik, yapi kirilimini yapan H1 mumu KAPANDIKTAN sonra gelmeli.
        if flipped[-1]["time"] < setup["broke_at"] + 3600 or not trigger(flipped, setup["poi_low"], setup["poi_high"]):
            return None
        width = atr(h1) or 0.0
        side = "BUY" if sign > 0 else "SELL"
        entry = m15[-1]["close"]
        structure = sign * (setup["sweep_low"] - 0.1 * width)
        stop = plan(side, entry, structure, context.bars)
        if stop is None:
            return None
        return Signal(side, entry, stop, entry + sign * 2.0 * abs(entry - stop),
                      f"gunluk yon {bias}, likidite supurmesi + yapi kirilimi, OB/FVG bolgesinde tetik mumu",
                      bar_time=int(m15[-1]["time"]))
