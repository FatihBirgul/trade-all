"""Modul kayit defteri. Yeni modul: bir dosya + asagida bir `register(...)` satiri.

Oy modullerinin sirasi `config.FUSION_MODULES` ile aynidir (puan agirliklari o adlarla eslesir).
"""

from .base import Context, Module, Signal, Vote, get, modules, register
from .strategies.donchian_breakout import DonchianBreakout
from .strategies.ema_pullback import EmaPullback
from .votes.confluence import Confluence
from .votes.momentum import Momentum
from .votes.mtf import Mtf
from .votes.other_strategies import OtherStrategies
from .votes.patterns import CandlePattern, ChartPattern
from .votes.regime import Regime
from .votes.session import Session
from .votes.structure import Structure

register(Mtf())
register(Regime())
register(CandlePattern())
register(ChartPattern())
register(Structure())
register(Momentum())
register(Confluence())
register(OtherStrategies())
register(Session())

# Yeni stratejiler: kimlikleri `tb_` ile baslar ve varsayilan olarak golge kipindedir (config.strategy_mode).
register(EmaPullback())
register(DonchianBreakout())

__all__ = ["Context", "Module", "Signal", "Vote", "get", "modules", "register"]
