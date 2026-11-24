"""Deterministic technical-analysis engine.

All indicator values are computed here from real OHLCV data using pandas/numpy.
The AI layer is NEVER asked to invent indicator numbers — it only receives the
structured output of this module.

V1.2 correctness changes:
- Technical parameters are timeframe-aware.
- EMA values require sufficient warm-up history.
- Short histories cannot manufacture EMA-based trend evidence.
- Volume direction remains independent from trend direction.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Timeframe-aware technical parameters
#
# These are safety defaults, not backtest-calibrated values.
# They are intentionally conservative and will be calibrated later.
# ---------------------------------------------------------------------------
TIMEFRAME_PARAMS = {
    "1m": {
        "swing_left": 5,
        "swing_right": 5,
        "volume_lookback": 8,
        "ema_warmup": {
            20: 30,
            50: 75,
            100: 130,
            200: 250,
        },
    },
    "5m": {
        "swing_left": 5,
        "swing_right": 5,
        "volume_lookback": 7,
        "ema_warmup": {
            20: 30,
            50: 75,
            100: 130,
            200: 250,
        },
    },
    "15m": {
        "swing_left": 4,
        "swing_right": 4,
        "volume_lookback": 6,
        "ema_warmup": {
            20: 30,
            50: 75,
            100: 130,
            200: 250,
        },
    },
    "1H": {
        "swing_left": 3,
        "swing_right": 3,
        "volume_lookback": 5,
        "ema_warmup": {
            20: 30,
            50: 75,
            100: 130,
            200: 250,
        },
    },
    "4H": {
        "swing_left": 3,
        "swing_right": 3,
        "volume_lookback": 5,
        "ema_warmup": {
            20: 30,
            50: 75,
            100: 130,
            200: 250,
        },
    },
    "1D": {
        "swing_left": 2,
        "swing_right": 2,
        "volume_lookback": 4,
        "ema_warmup": {
            20: 30,
            50: 75,
            100: 130,
            200: 250,
        },
    },
}

DEFAULT_TIMEFRAME = "4H"


def _round(v, n=2):
    if v is None:
        return None

    try:
        value = float(v)
    except (TypeError, ValueError):
        return None

    if not np.isfinite(value):
        return None

    return round(value, n)


def _to_df(candles: List[dict]) -> pd.DataFrame:
    return pd.DataFrame(candles)


def _params_for(timeframe: str) -> Dict:
    return TIMEFRAME_PARAMS.get(
        timeframe,
        TIMEFRAME_PARAMS[DEFAULT_TIMEFRAME],
    )


def _warmed_last(
    series: pd.Series,
    required_bars: int,
    decimals: int = 4,
):
    """Return the latest indicator value only after sufficient warm-up."""
    if len(series) < required_bars:
        return None

    value = series.iloc[-1]

    if pd.isna(value):
        return None

    return _round(value, decimals)


def _warmed_ema(
    close: pd.Series,
    period: int,
    required_bars: int,
):
    series = ema(close, period)
    return _warmed_last(
        series,
        required_bars,
        decimals=4,
    )


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(
        span=period,
        adjust=False,
    ).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def rsi(
    series: pd.Series,
    period: int = 14,
) -> pd.Series:
    delta = series.diff()

    gain = (
        delta
        .clip(lower=0)
        .rolling(period)
        .mean()
    )

    loss = (
        (-delta.clip(upper=0))
        .rolling(period)
        .mean()
    )

    rs = gain / loss.replace(
        0,
        np.nan,
    )

    result = 100 - (
        100 / (1 + rs)
    )
    # Preserve warm-up NaNs; only a fully observed zero-loss window gets 100.
    # This engine uses simple rolling averages, not Wilder smoothing.
    result = result.mask((loss == 0) & (gain > 0), 100.0)
    return result.mask((loss == 0) & (gain == 0), 50.0)


def macd(series: pd.Series):
    ema12 = ema(
        series,
        12,
    )

    ema26 = ema(
        series,
        26,
    )

    macd_line = ema12 - ema26

    signal = macd_line.ewm(
        span=9,
        adjust=False,
    ).mean()

    hist = macd_line - signal

    return (
        macd_line,
        signal,
        hist,
    )


def stoch_rsi(
    series: pd.Series,
    period: int = 14,
):
    r = rsi(
        series,
        period,
    )

    min_r = (
        r
        .rolling(period)
        .min()
    )

    max_r = (
        r
        .rolling(period)
        .max()
    )

    k = (
        (r - min_r)
        / (max_r - min_r).replace(
            0,
            np.nan,
        )
        * 100
    )

    d = k.rolling(3).mean()

    return k, d


def atr(
    df: pd.DataFrame,
    period: int = 14,
) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]

    prev_close = close.shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return tr.rolling(period).mean()


def bollinger(
    series: pd.Series,
    period: int = 20,
    mult: float = 2.0,
):
    mid = sma(
        series,
        period,
    )

    std = (
        series
        .rolling(period)
        .std()
    )

    upper = mid + mult * std
    lower = mid - mult * std

    return (
        upper,
        mid,
        lower,
    )


def _swings(
    df: pd.DataFrame,
    left: int = 3,
    right: int = 3,
):
    """Return indices of swing highs and swing lows."""
    highs = []
    lows = []

    h = df["high"].values
    l = df["low"].values
    n = len(df)

    if n <= left + right:
        return highs, lows

    for i in range(
        left,
        n - right,
    ):
        window_h = h[
            i - left : i + right + 1
        ]

        window_l = l[
            i - left : i + right + 1
        ]

        if (
            h[i] == window_h.max()
            and
            (window_h == h[i]).sum() == 1
        ):
            highs.append(i)

        if (
            l[i] == window_l.min()
            and
            (window_l == l[i]).sum() == 1
        ):
            lows.append(i)

    return (
        highs,
        lows,
    )


def support_resistance(
    df: pd.DataFrame,
    swing_highs,
    swing_lows,
    price: float,
):
    """Cluster recent swing points into support/resistance."""
    tol = price * 0.006

    def cluster(vals):
        vals = sorted(vals)
        clusters = []

        for value in vals:
            placed = False

            for cluster_item in clusters:
                if (
                    abs(
                        cluster_item["level"]
                        - value
                    )
                    <= tol
                ):
                    cluster_item[
                        "points"
                    ].append(value)

                    cluster_item[
                        "level"
                    ] = float(
                        np.mean(
                            cluster_item[
                                "points"
                            ]
                        )
                    )

                    placed = True
                    break

            if not placed:
                clusters.append(
                    {
                        "level": value,
                        "points": [value],
                    }
                )

        return [
            {
                "level": _round(
                    item["level"],
                    4,
                ),
                "touches": len(
                    item["points"]
                ),
            }
            for item in clusters
        ]

    high_vals = [
        df["high"].values[i]
        for i in swing_highs
    ][-12:]

    low_vals = [
        df["low"].values[i]
        for i in swing_lows
    ][-12:]

    combined = (
        high_vals
        + low_vals
    )

    resistance = [
        c
        for c in cluster(combined)
        if (
            c["level"]
            and c["level"] > price
        )
    ]

    support = [
        c
        for c in cluster(combined)
        if (
            c["level"]
            and c["level"] < price
        )
    ]

    resistance = sorted(
        resistance,
        key=lambda x: x["level"],
    )[:4]

    support = sorted(
        support,
        key=lambda x: x["level"],
        reverse=True,
    )[:4]

    return (
        support,
        resistance,
    )


def market_structure(
    df: pd.DataFrame,
    swing_highs,
    swing_lows,
) -> Dict:
    """Classify structure from the latest confirmed swing highs/lows."""
    h = [
        df["high"].values[i]
        for i in swing_highs
    ][-3:]

    l = [
        df["low"].values[i]
        for i in swing_lows
    ][-3:]

    hh = (
        len(h) >= 2
        and h[-1] > h[-2]
    )

    hl = (
        len(l) >= 2
        and l[-1] > l[-2]
    )

    lh = (
        len(h) >= 2
        and h[-1] < h[-2]
    )

    ll = (
        len(l) >= 2
        and l[-1] < l[-2]
    )

    if hh and hl:
        label = "uptrend"
        desc = (
            "Higher highs and higher lows"
        )

    elif lh and ll:
        label = "downtrend"
        desc = (
            "Lower highs and lower lows"
        )

    else:
        label = "ranging"
        desc = (
            "No clear sequence of "
            "higher highs/lows"
        )

    return {
        "label": label,
        "description": desc,
        "higher_high": bool(hh),
        "higher_low": bool(hl),
        "lower_high": bool(lh),
        "lower_low": bool(ll),
    }


def _volume_direction(
    df: pd.DataFrame,
    lookback: int = 5,
) -> int:
    """Estimate directional volume from recent closed candle bodies.

    This remains a directional-volume proxy, NOT true order-flow delta.
    """
    if (
        df.empty
        or "open" not in df.columns
        or "volume" not in df.columns
    ):
        return 0

    sample = df.tail(
        max(1, lookback)
    )

    signed_volume = 0.0

    for _, row in sample.iterrows():
        body = (
            float(row["close"])
            - float(row["open"])
        )

        volume = float(
            row["volume"]
        )

        if body > 0:
            signed_volume += volume

        elif body < 0:
            signed_volume -= volume

    if signed_volume > 0:
        return 1

    if signed_volume < 0:
        return -1

    return 0


def compute(
    candles: List[dict],
    timeframe: str = DEFAULT_TIMEFRAME,
) -> Dict:
    """Compute the full timeframe-aware technical snapshot."""
    df = _to_df(candles)

    if df.empty:
        raise ValueError(
            "No candle data provided."
        )

    if timeframe not in TIMEFRAME_PARAMS:
        timeframe = DEFAULT_TIMEFRAME

    params = _params_for(
        timeframe
    )

    price = float(
        df["close"].iloc[-1]
    )

    close = df["close"]

    # -----------------------------------------------------------------------
    # EMA
    #
    # Explicit warm-up requirements prevent short histories from producing
    # falsely confident EMA-based trend evidence.
    # -----------------------------------------------------------------------
    ema20_series = ema(
        close,
        20,
    )

    ema50_series = ema(
        close,
        50,
    )

    ema100_series = ema(
        close,
        100,
    )

    ema200_series = ema(
        close,
        200,
    )

    ema20 = _warmed_last(
        ema20_series,
        params["ema_warmup"][20],
    )

    ema50 = _warmed_last(
        ema50_series,
        params["ema_warmup"][50],
    )

    ema100 = _warmed_last(
        ema100_series,
        params["ema_warmup"][100],
    )

    ema200 = _warmed_last(
        ema200_series,
        params["ema_warmup"][200],
    )

    # Other indicators
    sma20 = sma(
        close,
        20,
    )

    rsi14 = rsi(
        close,
        14,
    )

    macd_line, macd_signal, macd_hist = macd(
        close
    )

    srsi_k, srsi_d = stoch_rsi(
        close
    )

    atr14 = atr(
        df,
        14,
    )

    bb_u, bb_m, bb_l = bollinger(
        close,
        20,
    )

    # Volume
    vol = df["volume"]

    vol_ma = sma(
        vol,
        20,
    )

    last_vol = float(
        vol.iloc[-1]
    )

    last_vol_ma = (
        float(
            vol_ma.iloc[-1]
        )
        if not np.isnan(
            vol_ma.iloc[-1]
        )
        else last_vol
    )

    vol_ratio = (
        last_vol / last_vol_ma
        if last_vol_ma
        else 1.0
    )

    volume_direction = _volume_direction(
        df,
        lookback=params[
            "volume_lookback"
        ],
    )

    # Market structure / levels
    swing_highs, swing_lows = _swings(
        df,
        left=params[
            "swing_left"
        ],
        right=params[
            "swing_right"
        ],
    )

    support, resistance = support_resistance(
        df,
        swing_highs,
        swing_lows,
        price,
    )

    structure = market_structure(
        df,
        swing_highs,
        swing_lows,
    )

    def last(
        series: pd.Series,
        required_bars: int = 1,
        decimals: int = 4,
    ):
        return _warmed_last(
            series,
            required_bars,
            decimals=decimals,
        )

    atr_value = last(
        atr14,
        required_bars=14,
        decimals=4,
    )

    atr_pct = None

    if atr_value is not None and price:
        atr_pct = _round(
            (
                float(atr_value)
                / price
            ) * 100,
            2,
        )

    indicators = {
        "price": _round(
            price,
            4,
        ),

        "ema20": ema20,
        "ema50": ema50,
        "ema100": ema100,
        "ema200": ema200,

        "sma20": last(
            sma20,
            required_bars=20,
        ),

        "rsi14": last(
            rsi14,
            required_bars=14,
        ),

        "macd": last(
            macd_line,
        ),
        "macd_signal": last(
            macd_signal,
        ),
        "macd_hist": last(
            macd_hist,
        ),

        "stoch_rsi_k": last(
            srsi_k,
            required_bars=28,
        ),
        "stoch_rsi_d": last(
            srsi_d,
            required_bars=30,
        ),

        "atr14": atr_value,
        "atr_pct": atr_pct,

        "bb_upper": last(
            bb_u,
            required_bars=20,
        ),
        "bb_middle": last(
            bb_m,
            required_bars=20,
        ),
        "bb_lower": last(
            bb_l,
            required_bars=20,
        ),

        "volume": _round(
            last_vol,
            2,
        ),

        "volume_ma20": _round(
            last_vol_ma,
            2,
        ),

        "volume_ratio": _round(
            vol_ratio,
            2,
        ),

        "volume_direction": volume_direction,

        "timeframe": timeframe,

        "ema_warmup": {
            "ema20": len(df)
            >= params[
                "ema_warmup"
            ][20],

            "ema50": len(df)
            >= params[
                "ema_warmup"
            ][50],

            "ema100": len(df)
            >= params[
                "ema_warmup"
            ][100],

            "ema200": len(df)
            >= params[
                "ema_warmup"
            ][200],
        },
    }

    return {
        "price": _round(
            price,
            4,
        ),

        "indicators": indicators,

        "structure": structure,

        "levels": {
            "support": support,
            "resistance": resistance,
        },

        "closes": [
            _round(
                c,
                4,
            )
            for c in close.tail(
                60
            ).tolist()
        ],

        "timeframe": timeframe,
    }
