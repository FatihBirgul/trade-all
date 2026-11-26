"""Modul kayit defteri. Yeni modul: bir dosya + asagida bir `register(...)` satiri.

Oy modullerinin sirasi `config.FUSION_MODULES` ile aynidir (puan agirliklari o adlarla eslesir).
"""

from .base import Context, Module, Signal, Vote, get, modules, register
from .strategies.donchian_breakout import DonchianBreakout
from .strategies.ema_pullback import EmaPullback
from .strategies.ema_pullback_h1 import EmaPullbackH1
from .strategies.smc_sweep import SmcSweep
from .strategies.v13 import V13
from .strategies.week_trade import WeekTrade
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
# Swing ailesi (kullanicinin eski masasindaki kurallar; gecmis testi yok): yalnizca golgede izlenir.
register(SmcSweep())
register(EmaPullbackH1("20_21"))
register(EmaPullbackH1("21_50"))
# Eski masanin GERCEK kodu (`smc.py`, v13) birebir tasindi; WEEK TRADE belgedeki 2 yillik testin kurallaridir.
register(V13("smc", "H1"))
register(V13("smc", "H4"))
register(V13("ema", "H1"))
register(V13("ema", "H4"))
register(WeekTrade())

__all__ = ["Context", "Module", "Signal", "Vote", "get", "modules", "register"]
