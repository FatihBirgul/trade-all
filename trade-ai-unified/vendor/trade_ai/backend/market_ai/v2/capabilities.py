"""Capabilities supported by a validated candle batch, never a live-feed promise.

Order book, trades, OI, funding and liquidation require separate validated
feeds. Candle metadata alone cannot grant any of those capabilities.
"""
from __future__ import annotations

from typing import Sequence

from .market_data_contract import Candle


MARKET_CONTRACTS = {
    "cfd": frozenset({"cfd"}),
    "crypto_spot": frozenset({"spot"}),
    "crypto_perpetual": frozenset({"perpetual"}),
    "forex_spot": frozenset({"spot"}),
    "gold_spot": frozenset({"spot"}),
}


def candle_capabilities(candles: Sequence[Candle]) -> frozenset[str]:
    """Derive conservative capabilities AFTER series quality validation.

    FX/gold spot cannot claim centralized exchange volume. Mixed volume kinds
    retain OHLC only; unavailable volume is never silently replaced by zero.
    Invalid market/contract or identity combinations grant no capabilities.
    """
    if not candles:
        return frozenset()
    identity = candles[0].instrument
    if identity.contract_type not in MARKET_CONTRACTS.get(identity.market, ()):
        return frozenset()
    if any(c.instrument != identity or c.source != candles[0].source for c in candles):
        return frozenset()
    kinds = {c.volume_kind for c in candles}
    if "real" in kinds and identity.market in {"forex_spot", "gold_spot", "cfd"}:
        return frozenset()
    available = {"ohlc"}
    if kinds == {"real"}:
        available.add("real_volume")
    elif kinds == {"tick"}:
        available.add("tick_volume")
    return frozenset(available)
