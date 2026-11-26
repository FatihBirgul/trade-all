"""Faz 5 strateji kutuphanesi: `strateji_listesi_v2.md`deki tanimlar, KAYNAKTAKI varsayilan parametrelerle.

Her strateji kendi zaman diliminde, mum KAPANISINDA sinyal uretir. Kaynak cikis vermiyorsa varsayilan: stop 2 x ATR(14)
ve karsi sinyalde cikis. Kaynaktan bilincli farklar her stratejinin `note` alaninda yazilidir.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from . import indicators as ind
from .engine import Series, Spec

NAN = np.nan


@dataclass(frozen=True)
class Strategy:
    id: str
    family: str  # A trend, B kirilim, C ortalamaya donus, D takvim, E capraz, X mevcut
    tf: str
    source: str
    build: Callable  # (series, context) -> Spec
    note: str = ""
    kinds: tuple = ("forex", "metal", "crypto", "index")


def _rows(s: Series) -> list[dict]:
    return [{"time": int(s.time[i]), "open": float(s.open[i]), "high": float(s.high[i]), "low": float(s.low[i]),
             "close": float(s.close[i]), "tick_volume": 0} for i in range(len(s))]


def _false(n):
    return np.zeros(n, bool)


def _atr_stop(s: Series, k: float = 2.0, n: int = 14) -> np.ndarray:
    return k * ind.atr(s.high, s.low, s.close, n)


# ---------------------------------------------------------------- A. trend takibi
def turtle(entry_n: int, exit_n: int):
    def build(s: Series, ctx) -> Spec:
        hi, lo = ind.rolling_max(s.high, entry_n), ind.rolling_min(s.low, entry_n)
        xlo, xhi = ind.rolling_min(s.low, exit_n), ind.rolling_max(s.high, exit_n)
        n_ = ind.atr(s.high, s.low, s.close, 20)
        return Spec(long=s.close > hi, short=s.close < lo, stop=2.0 * n_,
                    exit_long=s.close < xlo, exit_short=s.close > xhi)
    return build


def ma_cross(s: Series, ctx) -> Spec:
    fast, slow = ind.sma(s.close, 50), ind.sma(s.close, 200)
    up, down = ind.cross_up(fast, slow), ind.cross_down(fast, slow)
    return Spec(long=up, short=down, stop=_atr_stop(s), exit_long=down, exit_short=up)


def faber(s: Series, ctx) -> Spec:
    m = ind.sma(s.close, 200)
    above, below = s.close > m, s.close < m
    return Spec(long=above, short=below, stop=_atr_stop(s), exit_long=below, exit_short=above)


def tsmom(s: Series, ctx) -> Spec:
    """Ayin ilk D1 kapanisinda son 252 islem gunu getirisinin isaretine gore yon; ayda bir yeniden dengeleme."""
    n = len(s)
    month = np.array([np.datetime64(int(x), "s").astype("datetime64[M]") for x in s.time])
    first = np.concatenate([[False], month[1:] != month[:-1]])  # ayin ilk mumu: bir onceki ayin son kapanisindan sonra
    past = np.concatenate([np.full(252, NAN), s.close[:-252]]) if n > 252 else np.full(n, NAN)
    with np.errstate(invalid="ignore"):
        up, down = first & (s.close > past), first & (s.close < past)
    return Spec(long=up, short=down, stop=_atr_stop(s), exit_long=down, exit_short=up)


def clenow(s: Series, ctx) -> Spec:
    e50, e100 = ind.ema(s.close, 50), ind.ema(s.close, 100)
    hi, lo = ind.rolling_max(s.close, 50), ind.rolling_min(s.close, 50)
    a100 = ind.atr(s.high, s.low, s.close, 100)
    return Spec(long=(e50 > e100) & (s.close > hi), short=(e50 < e100) & (s.close < lo), stop=3.0 * a100,
                trail=3.0 * a100)


def supertrend(s: Series, ctx) -> Spec:
    line, d = ind.supertrend(s.high, s.low, s.close, 10, 3.0)
    prev = np.concatenate([[0.0], d[:-1]])
    up, down = (d > 0) & (prev < 0), (d < 0) & (prev > 0)
    return Spec(long=up, short=down, stop=np.abs(s.close - line), exit_long=down, exit_short=up)


def adx_dmi(s: Series, ctx) -> Spec:
    pdi, mdi, adx = ind.dmi(s.high, s.low, s.close, 14)
    strong, weak = adx > 25, adx < 20
    return Spec(long=strong & (pdi > mdi), short=strong & (mdi > pdi), stop=_atr_stop(s), exit_long=weak,
                exit_short=weak)


def parabolic(s: Series, ctx) -> Spec:
    sar, d = ind.psar(s.high, s.low, 0.02, 0.2)
    prev = np.concatenate([[0.0], d[:-1]])
    up, down = (d > 0) & (prev < 0), (d < 0) & (prev > 0)
    return Spec(long=up, short=down, stop=np.abs(s.close - sar), exit_long=down, exit_short=up)


def ichimoku(s: Series, ctx) -> Spec:
    t, k, top, bottom = ind.ichimoku(s.high, s.low)
    return Spec(long=(s.close > top) & (t > k), short=(s.close < bottom) & (t < k), stop=_atr_stop(s),
                exit_long=s.close < k, exit_short=s.close > k)


def macd_zero(s: Series, ctx) -> Spec:
    line, sig = ind.macd(s.close)
    up, down = ind.cross_up(line, sig), ind.cross_down(line, sig)
    return Spec(long=up & (line > 0), short=down & (line < 0), stop=_atr_stop(s), exit_long=down, exit_short=up)


# ---------------------------------------------------------------- C. ortalamaya donus
def rsi2(s: Series, ctx) -> Spec:
    m200, m5, r = ind.sma(s.close, 200), ind.sma(s.close, 5), ind.rsi(s.close, 2)
    return Spec(long=(s.close > m200) & (r < 10), short=(s.close < m200) & (r > 90), stop=_atr_stop(s),
                exit_long=s.close > m5, exit_short=s.close < m5)


def double7(s: Series, ctx) -> Spec:
    m200 = ind.sma(s.close, 200)
    lo7, hi7 = ind.rolling_min(s.close, 7, prior=False), ind.rolling_max(s.close, 7, prior=False)
    at_low, at_high = s.close <= lo7, s.close >= hi7
    return Spec(long=(s.close > m200) & at_low, short=(s.close < m200) & at_high, stop=_atr_stop(s),
                exit_long=at_high, exit_short=at_low)


def ibs(s: Series, ctx) -> Spec:
    span = s.high - s.low
    with np.errstate(divide="ignore", invalid="ignore"):
        value = np.where(span > 0, (s.close - s.low) / span, 0.5)
    return Spec(long=value < 0.2, short=_false(len(s)), stop=_atr_stop(s), exit_long=value > 0.8, max_bars=1)


def bollinger_revert(s: Series, ctx) -> Spec:
    mid, upper, lower = ind.bollinger(s.close, 20, 2.0)
    m200 = ind.sma(s.close, 200)
    long = (s.close > m200) & (s.low <= lower) & (s.close > lower)
    short = (s.close < m200) & (s.high >= upper) & (s.close < upper)
    return Spec(long=long, short=short, stop=_atr_stop(s), exit_long=s.close >= mid, exit_short=s.close <= mid)


def three_down(s: Series, ctx) -> Spec:
    m200 = ind.sma(s.close, 200)
    d = np.diff(s.close, prepend=NAN)
    down3 = (d < 0) & (np.roll(d, 1) < 0) & (np.roll(d, 2) < 0)
    down3[:3] = False
    return Spec(long=(s.close > m200) & down3, short=_false(len(s)), stop=_atr_stop(s), exit_long=d > 0,
                max_bars=5)


def turtle_soup(s: Series, ctx) -> Spec:
    """20 gunluk dip, en az 4 gun once yapilmis; bugun o dibin altina inip uzerinde kapanis -> AL (ayna: SAT)."""
    n = len(s)
    long, short, stop = _false(n), _false(n), np.full(n, NAN)
    a = ind.atr(s.high, s.low, s.close, 14)
    for i in range(21, n):
        window_l, window_h = s.low[i - 20:i], s.high[i - 20:i]
        k_l, k_h = int(np.argmin(window_l)), int(np.argmax(window_h))
        prior_low, prior_high = window_l[k_l], window_h[k_h]
        if 20 - k_l >= 4 and s.low[i] < prior_low < s.close[i]:
            long[i], stop[i] = True, s.close[i] - s.low[i] + 0.1 * a[i]
        elif 20 - k_h >= 4 and s.high[i] > prior_high > s.close[i]:
            short[i], stop[i] = True, s.high[i] - s.close[i] + 0.1 * a[i]
    return Spec(long=long, short=short, stop=stop, trail=3.0 * a)


def holy_grail(s: Series, ctx) -> Spec:
    pdi, mdi, adx = ind.dmi(s.high, s.low, s.close, 14)
    e20 = ind.ema(s.close, 20)
    a = ind.atr(s.high, s.low, s.close, 14)
    strong = adx > 30
    long = strong & (pdi > mdi) & (s.low <= e20) & (s.close > e20)
    short = strong & (mdi > pdi) & (s.high >= e20) & (s.close < e20)
    stop = np.where(long, s.close - s.low, np.where(short, s.high - s.close, NAN)) + 0.1 * a
    return Spec(long=long, short=short, stop=stop, trail=3.0 * a)


# ---------------------------------------------------------------- yardimcilar (zaman)
def _utc(times) -> list:
    from datetime import datetime, timezone
    return [datetime.fromtimestamp(int(x), timezone.utc) for x in times]


def _local(moments, zone) -> list:
    from datetime import datetime, timezone
    return [datetime.fromtimestamp(int(x), timezone.utc).astimezone(zone) for x in moments]


def _daily_map(s: Series, d: Series) -> np.ndarray:
    """Her mumun kapanisinda kapanmis son D1 mumu (-1: yok)."""
    return np.searchsorted(d.time + 86400, s.time + s.seconds, side="right") - 1


# ---------------------------------------------------------------- B. kirilim / volatilite
def williams(s: Series, ctx) -> Spec:
    """Gun acilisi +/- 0,6 x dunku aralik; seviye H1 KAPANISIYLA asilinca giris, gun sonunda cikis."""
    d = ctx["D1"]
    di = _daily_map(s, d)
    n = len(s)
    day = (s.time // 86400).astype(np.int64)
    first = np.concatenate([[True], day[1:] != day[:-1]])
    day_open = np.zeros(n)
    current = np.nan
    for i in range(n):
        if first[i]:
            current = s.open[i]
        day_open[i] = current
    rng = np.where(di >= 0, (d.high - d.low)[np.clip(di, 0, None)], np.nan)
    # dunku aralik: kapanmis son D1 bugunun mumu olamaz (bugun kapanmadi) -> di dunu gosterir
    up, down = day_open + 0.6 * rng, day_open - 0.6 * rng
    prev = np.concatenate([[np.nan], s.close[:-1]])
    same_day = np.concatenate([[False], day[1:] == day[:-1]])
    long = (s.close > up) & ~((prev > up) & same_day)
    short = (s.close < down) & ~((prev < down) & same_day)
    day_end = (s.time + s.seconds) % 86400 == 0
    long &= ~day_end
    short &= ~day_end
    return Spec(long=long, short=short, stop=_atr_stop(s), exit_long=day_end, exit_short=day_end)


def narrow_range(k: int, inside: bool):
    def build(s: Series, ctx) -> Spec:
        span = s.high - s.low
        narrow = np.zeros(len(s), bool)
        for i in range(k - 1, len(s)):
            narrow[i] = span[i] <= span[i - k + 1:i + 1].min()
        if inside:
            prev_h, prev_l = np.concatenate([[np.nan], s.high[:-1]]), np.concatenate([[np.nan], s.low[:-1]])
            narrow &= (s.high < prev_h) & (s.low > prev_l)
        setup = np.concatenate([[False], narrow[:-1]])
        hi, lo = np.concatenate([[np.nan], s.high[:-1]]), np.concatenate([[np.nan], s.low[:-1]])
        long, short = setup & (s.close > hi), setup & (s.close < lo)
        stop = np.where(long, s.close - lo, np.where(short, hi - s.close, NAN))
        a = ind.atr(s.high, s.low, s.close, 14)
        return Spec(long=long, short=short, stop=stop, trail=3.0 * a)
    return build


def opening_range(s: Series, ctx) -> Spec:
    """ABD nakit acilisinin ilk saati (09:00-10:00 NY H1 mumu) araligi; gun icinde kapanisla kirilim; 16:00 NY'de cikis."""
    from zoneinfo import ZoneInfo
    ny = _local(s.time, ZoneInfo("America/New_York"))
    n = len(s)
    long, short, stop = _false(n), _false(n), np.full(n, NAN)
    exit_ = _false(n)
    hi = lo = None
    taken = None
    for i in range(n):
        t = ny[i]
        if t.weekday() >= 5:
            continue
        if t.hour == 9:
            hi, lo, taken = s.high[i], s.low[i], t.date()
            continue
        if t.hour == 15:
            exit_[i] = True  # 15:00-16:00 mumunun kapanisi = nakit kapanis
            continue
        if hi is None or taken != t.date() or not 10 <= t.hour < 15:
            continue
        if s.close[i] > hi:
            long[i], stop[i], hi = True, s.close[i] - lo, np.inf  # gunde bir giris
        elif s.close[i] < lo:
            short[i], stop[i], lo = True, hi - s.close[i], -np.inf
    return Spec(long=long, short=short, stop=stop, exit_long=exit_, exit_short=exit_)


def keltner(s: Series, ctx) -> Spec:
    mid = ind.ema(s.close, 20)
    a = ind.atr(s.high, s.low, s.close, 14)
    upper, lower = mid + 2.0 * a, mid - 2.0 * a
    return Spec(long=s.close > upper, short=s.close < lower, stop=2.0 * a, exit_long=s.close < mid,
                exit_short=s.close > mid)


def bollinger_squeeze(s: Series, ctx) -> Spec:
    mid, upper, lower = ind.bollinger(s.close, 20, 2.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        width = (upper - lower) / mid
    look = 756  # ~6 ay H4
    low6 = ind.rolling_min(np.where(np.isnan(width), np.inf, width), look, prior=False)
    squeezed = ind.rolling_max((width <= low6 + 1e-12).astype(float), 5, prior=False) > 0
    return Spec(long=squeezed & (s.close > upper), short=squeezed & (s.close < lower), stop=_atr_stop(s),
                exit_long=s.close < mid, exit_short=s.close > mid)


def asia_london_h1(s: Series, ctx) -> Spec:
    """Mevcut golge stratejinin H1 karsiligi: Londra 00-08 araligi, 08-12 arasinda ilk H1 kapanisi disarida;
    stop karsi uc, hedef aralik genisligi, 21:00 Londra'da cikis; aralik 0,2-1,0 x D1 ATR(14)."""
    from zoneinfo import ZoneInfo
    ld = _local(s.time, ZoneInfo("Europe/London"))
    d = ctx["D1"]
    di = _daily_map(s, d)
    datr = ind.atr(d.high, d.low, d.close, 14)
    n = len(s)
    long, short, stop, target, exit_ = _false(n), _false(n), np.full(n, NAN), np.full(n, NAN), _false(n)
    day, hi, lo, done = None, -np.inf, np.inf, False
    for i in range(n):
        t = ld[i]
        if t.date() != day:
            day, hi, lo, done = t.date(), -np.inf, np.inf, False
        if t.hour < 8:
            hi, lo = max(hi, s.high[i]), min(lo, s.low[i])
            continue
        if t.hour == 20:
            exit_[i] = True  # 20:00-21:00 mumunun kapanisi
        if done or t.hour >= 12 or not np.isfinite(hi) or di[i] < 0:
            continue
        width = hi - lo
        a = datr[di[i]]
        if not (a > 0 and 0.2 * a <= width <= 1.0 * a):
            done = True
            continue
        if s.close[i] > hi:
            long[i], stop[i], target[i], done = True, s.close[i] - lo, hi + width - s.close[i], True
        elif s.close[i] < lo:
            short[i], stop[i], target[i], done = True, hi - s.close[i], s.close[i] - (lo - width), True
        else:
            continue
    target = np.where(target > 0, target, NAN)
    long &= np.isfinite(target)
    short &= np.isfinite(target)
    return Spec(long=long, short=short, stop=stop, target=target, exit_long=exit_, exit_short=exit_)


# ---------------------------------------------------------------- D. takvim (endeksler)
def us_holidays(year: int) -> set:
    """NYSE tatilleri (kural tabanli): yilbasi, MLK, Baskanlar, Kutsal Cuma, Anma, Juneteenth (2022+), 4 Temmuz,
    Isci, Sukran, Noel; hafta sonuna denk gelen sabit tatil Cuma/Pazartesi'ye kayar."""
    from datetime import date, timedelta

    def nth(month, weekday, k):
        d0 = date(year, month, 1)
        return d0 + timedelta(days=(weekday - d0.weekday()) % 7 + 7 * (k - 1))

    def last(month, weekday):
        d0 = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
        return d0 - timedelta(days=(d0.weekday() - weekday) % 7)

    def observed(d0):
        return d0 - timedelta(days=1) if d0.weekday() == 5 else d0 + timedelta(days=1) if d0.weekday() == 6 else d0

    a, b, c = year % 19, year // 100, year % 100
    d_, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d_ - g + 15) % 30
    i_, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i_ - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month = (h + l_ - 7 * m + 114) // 31
    day = (h + l_ - 7 * m + 114) % 31 + 1
    easter = date(year, month, day)
    days = {observed(date(year, 1, 1)), nth(1, 0, 3), nth(2, 0, 3), easter - timedelta(days=2), last(5, 0),
            observed(date(year, 7, 4)), nth(9, 0, 1), nth(11, 3, 4), observed(date(year, 12, 25))}
    if year >= 2022:
        days.add(observed(date(year, 6, 19)))
    return days


def _trading_days(s: Series) -> tuple[list, np.ndarray]:
    """D1 mumlarinin tarihleri ve islem gunu mu (hafta ici, tatil degil)."""
    dates = [t.date() for t in _utc(s.time)]
    hol = set()
    for y in {d.year for d in dates}:
        hol |= us_holidays(y)
    trading = np.array([d.weekday() < 5 and d not in hol for d in dates])
    return dates, trading


def turn_of_month(s: Series, ctx) -> Spec:
    """Ayin son islem gununden bir onceki gunun kapanisinda AL; yeni ayin 3. islem gunu kapanisinda cikis.
    (Takvim onceden bilinir: 'son islem gunu' tatil takviminden belirlenir.)"""
    dates, trading = _trading_days(s)
    n = len(s)
    long, exit_ = _false(n), _false(n)
    idx = [i for i in range(n) if trading[i]]
    for pos, i in enumerate(idx):
        nxt = idx[pos + 1] if pos + 1 < len(idx) else None
        after = idx[pos + 2] if pos + 2 < len(idx) else None
        if nxt is not None and after is not None and dates[nxt].month == dates[i].month and dates[after].month != dates[i].month:
            long[i] = True
        count = 0
        for q in range(pos, -1, -1):
            if dates[idx[q]].month != dates[i].month:
                break
            count += 1
        if count == 3:
            exit_[i] = True
    return Spec(long=long, short=_false(n), stop=_atr_stop(s), exit_long=exit_)


def overnight(s: Series, ctx) -> Spec:
    """ABD nakit kapanisinda (15:00-16:00 NY H1 mumunun kapanisi) AL; ertesi islem gunu 09:00-10:00 NY mumunun
    kapanisinda cikis (nakit acilistan yarim saat sonra: H1 verisiyle en yakin an)."""
    from zoneinfo import ZoneInfo
    ny = _local(s.time, ZoneInfo("America/New_York"))
    long = np.array([t.weekday() < 5 and t.hour == 15 for t in ny])
    exit_ = np.array([t.weekday() < 5 and t.hour == 9 for t in ny])
    return Spec(long=long, short=_false(len(s)), stop=_atr_stop(s), exit_long=exit_)


def pre_holiday(s: Series, ctx) -> Spec:
    dates, trading = _trading_days(s)
    hol = set()
    for y in {d.year for d in dates}:
        hol |= us_holidays(y)
    from datetime import timedelta
    n = len(s)
    long = _false(n)
    for i in range(n):
        if not trading[i]:
            continue
        nxt = dates[i] + timedelta(days=1)
        while nxt.weekday() >= 5:
            nxt += timedelta(days=1)
        long[i] = nxt in hol
    return Spec(long=long, short=_false(n), stop=_atr_stop(s), exit_long=trading.copy())


# ---------------------------------------------------------------- E. capraz kesit (diger sembollerin D1 kapanislari)
CURRENCIES = ("USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD")
USD_PAIRS = {"EUR": ("EURUSD", 1), "GBP": ("GBPUSD", 1), "AUD": ("AUDUSD", 1), "NZD": ("NZDUSD", 1),
             "JPY": ("USDJPY", -1), "CHF": ("USDCHF", -1), "CAD": ("USDCAD", -1)}


def _closes_at(other: Series, moments: np.ndarray) -> np.ndarray:
    """Her an icin `other`in o anda kapanmis son D1 kapanisi."""
    k = np.searchsorted(other.time + 86400, moments, side="right") - 1
    return np.where(k >= 0, other.close[np.clip(k, 0, None)], np.nan)


def currency_momentum(s: Series, ctx) -> Spec:
    """Haftanin ilk D1 kapanisinda 8 para birimini USD'ye karsi 63 islem gunu getirisine gore sirala; en guclu /
    en zayif cifti AL (sembol bu ciftse; tersiyse SAT); bir sonraki haftalik dengelemede secili degilse cikis."""
    base, quote = s.symbol[:3], s.symbol[3:6]
    n = len(s)
    long, short, exit_ = _false(n), _false(n), _false(n)
    universe = ctx.get("universe") or {}
    if base not in CURRENCIES or quote not in CURRENCIES:
        return Spec(long=long, short=short, stop=np.full(n, NAN))
    moments = s.time + s.seconds
    weekday = np.array([t.weekday() for t in _utc(s.time)])
    first = np.concatenate([[False], weekday[1:] < weekday[:-1]])  # haftanin ilk D1 mumu
    strength = {"USD": np.zeros(n)}
    for cur, (pair, sign) in USD_PAIRS.items():
        other = universe.get(pair)
        if other is None:
            return Spec(long=long, short=short, stop=np.full(n, NAN))
        now, past = _closes_at(other, moments), _closes_at(other, moments - 91 * 86400)
        with np.errstate(divide="ignore", invalid="ignore"):
            strength[cur] = sign * np.log(now / past)
    table = np.vstack([strength[c] for c in CURRENCIES])
    ok = np.all(np.isfinite(table), axis=0)
    best = np.argmax(np.where(ok, table, -np.inf), axis=0)
    worst = np.argmin(np.where(ok, table, np.inf), axis=0)
    bi, qi = CURRENCIES.index(base), CURRENCIES.index(quote)
    pick_long = ok & (best == bi) & (worst == qi)
    pick_short = ok & (best == qi) & (worst == bi)
    long, short = first & pick_long, first & pick_short
    exit_ = first & ~pick_long
    exit_s = first & ~pick_short
    return Spec(long=long, short=short, stop=_atr_stop(s), exit_long=exit_, exit_short=exit_s)


def cross_asset_momentum(s: Series, ctx) -> Spec:
    """Ayin ilk D1 kapanisinda butun sepetin (33 sembol) 126 islem gunu getirisine gore ilk 3'u AL; bir sonraki
    aylik dengelemede ilk 3'te degilse cikis. Yalnizca AL."""
    universe = ctx.get("universe") or {}
    n = len(s)
    moments = s.time + s.seconds
    month = np.array([t.month for t in _utc(s.time)])
    first = np.concatenate([[False], month[1:] != month[:-1]])
    rets = []
    names = sorted(universe)
    for name in names:
        other = universe[name]
        with np.errstate(divide="ignore", invalid="ignore"):
            rets.append(np.log(_closes_at(other, moments) / _closes_at(other, moments - 182 * 86400)))
    if s.symbol not in names or len(names) < 5:
        return Spec(long=_false(n), short=_false(n), stop=np.full(n, NAN))
    table = np.vstack(rets)
    mine = table[names.index(s.symbol)]
    filled = np.where(np.isfinite(table), table, -np.inf)
    rank = (filled > mine).sum(axis=0)  # kendisinden iyi olanlarin sayisi
    top = np.isfinite(mine) & (rank < 3) & (np.isfinite(table).sum(axis=0) >= 10)
    return Spec(long=first & top, short=_false(n), stop=_atr_stop(s), exit_long=first & ~top)


# ---------------------------------------------------------------- mevcut stratejiler (karsilastirma)
def week_trade(s: Series, ctx) -> Spec:
    """WEEK TRADE (`bt.py`): 4H kapanisinda sinyal; stop 2 x gunluk ATR; cikis: +1R'de stop girise, +2R'de +1R
    kilit, sonra en iyi fiyat - 2 x 4H ATR; 7 gunde +1R yoksa cikis. Golge stratejinin yumusak surumu."""
    from ..signals.modules.strategies import week_trade as wt
    from ..week_replica import H4 as H4S
    n = len(s)
    long, short, stop, atr4 = _false(n), _false(n), np.full(n, NAN), np.full(n, NAN)
    h4 = [{"time": int(s.time[i]), "open": s.open[i], "high": s.high[i], "low": s.low[i], "close": s.close[i]}
          for i in range(n)]
    d = ctx["D1"]
    d1 = [{"time": int(d.time[i]), "open": d.open[i], "high": d.high[i], "low": d.low[i], "close": d.close[i]}
          for i in range(len(d))]
    d1_times = [b["time"] for b in d1]
    import bisect
    for i in range(60, n):
        cut = bisect.bisect_right(d1_times, h4[i]["time"] + H4S)
        found = wt.signal(h4[max(0, i - 299):i + 1], d1[max(0, cut - 300):cut])
        if found is None:
            continue
        (long if found["side"] == "BUY" else short)[i] = True
        stop[i], atr4[i] = found["stop_distance"], found["atr4"]

    def exit_fn(series, i, sign, entry, stop_price, spread_at):
        risk = abs(entry - stop_price)
        best, locked, stop_level = 0.0, 0, stop_price
        for j in range(i + 1, len(series)):
            shift = 0.0 if sign > 0 else spread_at(series.time[j])
            op, hi, lo, cl = (series.open[j] + shift, series.high[j] + shift, series.low[j] + shift,
                              series.close[j] + shift)
            if (sign > 0 and lo <= stop_level) or (sign < 0 and hi >= stop_level):
                price = min(op, stop_level) if sign > 0 else max(op, stop_level)
                return j, price, "stop"
            fav = ((hi if sign > 0 else lo) - entry) * sign / risk
            best = max(best, fav)
            if best >= 1.0 and locked < 1:
                stop_level, locked = (max(stop_level, entry) if sign > 0 else min(stop_level, entry)), 1
            if best >= 2.0 and locked < 2:
                level = entry + sign * risk
                stop_level, locked = (max(stop_level, level) if sign > 0 else min(stop_level, level)), 2
            if best > 2.0:
                extreme = entry + sign * best * risk
                level = extreme - sign * 2.0 * atr4[i]
                stop_level = max(stop_level, level) if sign > 0 else min(stop_level, level)
            if locked == 0 and series.time[j] + series.seconds - (series.time[i] + series.seconds) >= 7 * 86400:
                return j, cl, "time"
        return None, None, "open"

    return Spec(long=long, short=short, stop=stop, exit_fn=exit_fn)


def ema_h1(fast: int, slow: int):
    """Eski masanin EMA pullback H1 stratejisi (golgedeki `tb_emapb_h1_*`): sinyal ve stop ayni modulden; cikis
    sabit stop + 2R hedef (golge izleyicinin kurali)."""
    def build(s: Series, ctx) -> Spec:
        from ..signals.modules.base import Context
        from ..signals.modules.strategies.ema_pullback_h1 import EmaPullbackH1
        strategy = EmaPullbackH1(f"{fast}_{slow}")
        n = len(s)
        long, short, stop = _false(n), _false(n), np.full(n, NAN)
        rows = [{"time": int(s.time[i]), "open": s.open[i], "high": s.high[i], "low": s.low[i], "close": s.close[i],
                 "tick_volume": 0} for i in range(n)]
        upper = {tf: _rows(ctx[tf]) for tf in ("H4", "D1")}
        closes = {tf: ctx[tf].time + ctx[tf].seconds for tf in ("H4", "D1")}
        for i in range(60, n):
            last = rows[i]
            now = last["time"] + 3600
            m15 = [{**last, "time": last["time"] + 2700}]  # zamanlama icin: H1'in son ceyregi (fiyat H1 kapanisi)
            bars = {"M15": m15, "H1": rows[max(0, i - 299):i + 1]}
            for tf in ("H4", "D1"):
                cut = int(np.searchsorted(closes[tf], now, side="right"))
                bars[tf] = upper[tf][max(0, cut - 300):cut]
            signal = strategy.evaluate(Context(symbol=s.symbol, now=now, bars=bars))
            if signal is None:
                continue
            (long if signal.side == "BUY" else short)[i] = True
            stop[i] = abs(signal.entry - signal.stop)
        return Spec(long=long, short=short, stop=stop, target=2.0 * stop, max_bars=None)
    return build


STRATEGIES: list[Strategy] = [
    Strategy("A01_turtle_s1", "A", "D1", "Curtis Faith, Way of the Turtle (Sistem 1: 20/10)", turtle(20, 10),
             "giris kapanisla (gun ici kirilim degil); 'onceki islem kazandiysa atla' kurali ve piramitleme yok"),
    Strategy("A02_turtle_s2", "A", "D1", "Curtis Faith, Way of the Turtle (Sistem 2: 55/20)", turtle(55, 20),
             "giris kapanisla; piramitleme yok"),
    Strategy("A03_ma_cross", "A", "D1", "Klasik 50/200 kesisimi; Clenow, Following the Trend", ma_cross,
             "stop 2 x ATR(14) (kaynakta stop yok: varsayilan)"),
    Strategy("A04_faber_sma200", "A", "D1", "Faber (2007), fiyat > SMA200", faber,
             "D1 kapanisinda; SMA200 altinda SAT (FX'te simetrik); stop 2 x ATR(14) varsayilan"),
    Strategy("A05_tsmom12", "A", "D1", "Moskowitz, Ooi, Pedersen (2012), 12 ay zaman serisi momentumu", tsmom,
             "ayin ilk D1 kapanisinda yeniden dengeleme; 252 islem gunu; stop 2 x ATR(14) varsayilan"),
    Strategy("A06_clenow", "A", "D1", "Clenow, Following the Trend", clenow,
             "50 gunluk KAPANIS tepesi/dibi; iz suren stop 3 x ATR(100)"),
    Strategy("A07_supertrend", "A", "H4", "Olivier Seban, Supertrend (10, 3)", supertrend,
             "yon degisiminde giris ve cikis; ilk stop giristeki Supertrend cizgisi"),
    Strategy("A08_adx_dmi", "A", "H4", "Wilder (1978), ADX(14) > 25 + DMI", adx_dmi,
             "ADX < 20'de cikis; stop 2 x ATR(14) varsayilan"),
    Strategy("A09_psar", "A", "D1", "Wilder (1978), Parabolic SAR 0.02 / 0.2", parabolic,
             "donuste giris ve cikis; ilk stop giristeki SAR"),
    Strategy("A10_ichimoku", "A", "D1", "Goichi Hosoda, Ichimoku 9/26/52", ichimoku,
             "bulut ustu + Tenkan > Kijun; Kijun alti kapanista cikis; stop 2 x ATR(14)"),
    Strategy("A11_macd_zero", "A", "D1", "Gerald Appel, MACD 12/26/9", macd_zero,
             "MACD > 0 iken sinyal kesisimi; ters kesisimde cikis; stop 2 x ATR(14)"),
    Strategy("C19_rsi2", "C", "D1", "Connors & Alvarez (2008), RSI(2)", rsi2,
             "SMA200 ustu RSI(2) < 10 AL, SMA5 ustu kapanista cikis (ayna SAT); stop 2 x ATR(14) varsayilan"),
    Strategy("C20_double7", "C", "D1", "Connors & Alvarez, Double 7s", double7,
             "7 gunun en dusuk kapanisinda AL, en yuksekte cikis; FX'te ayna SAT; stop 2 x ATR(14)"),
    Strategy("C21_ibs", "C", "D1", "Pagonidis (2013), IBS etkisi", ibs,
             "IBS < 0,2 AL; ertesi gun kapanis ya da IBS > 0,8'de cikis; yalnizca AL, endeksler",
             kinds=("index",)),
    Strategy("C22_bollinger_revert", "C", "H4", "John Bollinger, banda dokunup iceri kapanis", bollinger_revert,
             "SMA200 yonunde; orta bantta cikis; stop 2 x ATR(14)"),
    Strategy("C23_three_down", "C", "D1", "Connors & Alvarez, 3 gun dusus", three_down,
             "SMA200 ustu 3 dusuk kapanis; 5 gun ya da ilk yukselis kapanisinda cikis; endeksler", kinds=("index",)),
    Strategy("C24_turtle_soup", "C", "D1", "Raschke & Connors, Street Smarts (1995), Turtle Soup", turtle_soup,
             "kapanisla (gun ici stop emri degil); stop gunun dibinin 0,1 ATR alti; iz suren 3 x ATR(14)"),
    Strategy("C25_holy_grail", "C", "D1", "Raschke & Connors, Street Smarts, Holy Grail", holy_grail,
             "ADX(14) > 30, EMA20'ye dokunup trend yonunde kapanis; stop mumun ucu; iz suren 3 x ATR(14)"),
    Strategy("B12_williams", "B", "H1", "Larry Williams, Long-Term Secrets to Short-Term Trading", williams,
             "acilis +/- 0,6 x dunku aralik; gun ici stop emri yerine H1 KAPANISIYLA asilinca giris; gun sonunda "
             "cikis; stop 2 x ATR(14) H1"),
    Strategy("B13_nr7", "B", "D1", "Toby Crabel (1990), NR7", narrow_range(7, False),
             "NR7 gununden sonra kapanisla kirilim (stop emri degil); stop NR7 gununun karsi ucu; iz suren 3 x ATR"),
    Strategy("B14_nr4_inside", "B", "D1", "Crabel (1990); Raschke, NR4 + ic gun", narrow_range(4, True),
             "NR4 ve ic gun sonrasi kapanisla kirilim; stop karsi uc; iz suren 3 x ATR"),
    Strategy("B15_orb", "B", "H1", "Crabel (1990), acilis araligi kirilimi", opening_range,
             "ABD nakit acilisinin ilk saati yerine 09:00-10:00 NY H1 mumu (H1 veri); kapanisla kirilim; "
             "16:00 NY'de cikis; endeksler", kinds=("index",)),
    Strategy("B16_keltner", "B", "H4", "Chester Keltner / Linda Raschke, EMA20 +/- 2 x ATR", keltner,
             "kapanisla kanal disi; EMA20'ye donuste cikis"),
    Strategy("B17_bollinger_squeeze", "B", "H4", "John Bollinger, Bollinger on Bollinger Bands", bollinger_squeeze,
             "bant genisligi son 5 mumda 6 ayin en dusugu; kapanisla bant disi; orta bantta cikis"),
    Strategy("B18_asia_london_h1", "B", "H1", "Asya araligi / Londra kirilimi (golge stratejinin H1 surumu)",
             asia_london_h1, "M15 yerine H1 kapanisi; diger kurallar golgedeki tanimla ayni"),
    Strategy("D26_turn_of_month", "D", "D1", "Ariel (1987); McConnell & Xu (2008)", turn_of_month,
             "son islem gunu oncesi AL, yeni ayin 3. islem gunu cikis; stop 2 x ATR(14)", kinds=("index",)),
    Strategy("D27_overnight", "D", "H1", "Cliff, Cooper & Gulen (2008), gece getirisi", overnight,
             "nakit kapanista AL; ertesi gun 09:00-10:00 NY mumunun kapanisinda cikis (H1)", kinds=("index",)),
    Strategy("D28_pre_holiday", "D", "D1", "Ariel (1990), tatil oncesi", pre_holiday,
             "NYSE tatilinden onceki islem gunu kapanisinda AL; sonraki islem gunu kapanisinda cikis",
             kinds=("index",)),
    Strategy("E29_currency_momentum", "E", "D1", "Menkhoff, Sarno, Schmeling, Schrimpf (2012)", currency_momentum,
             "8 para birimi USD'ye karsi 63 islem gunu (91 takvim gunu); haftalik; en guclu/en zayif cift "
             "listede yoksa o hafta islem yok", kinds=("forex",)),
    Strategy("E30_cross_asset_momentum", "E", "D1", "Asness, Moskowitz, Pedersen (2013)", cross_asset_momentum,
             "33 sembollu sepette 126 islem gunu (182 takvim gunu) getirisi; aylik; ilk 3 AL"),
    Strategy("X_week_trade", "X", "H4", "Eski masanin bt.py'si (WEEK TRADE, yumusak)", week_trade),
    Strategy("X_ema_h1_20_21", "X", "H1", "Eski masanin EMA pullback H1 (20/21)", ema_h1(20, 21)),
    Strategy("X_ema_h1_21_50", "X", "H1", "Eski masanin EMA pullback H1 (21/50)", ema_h1(21, 50)),
]
BY_ID = {s.id: s for s in STRATEGIES}
