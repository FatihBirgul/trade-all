"""Strateji ve oy modullerinin ortak arayuzu (spec §6.2).

Her modul ayni kucuk arayuzu uygular: `evaluate(context) -> Vote | Signal | None`.
- Oy modulu (`kind = "vote"`): bir adayi destekler (+1), karsi cikar (-1) ya da cekimser kalir (0).
- Strateji modulu (`kind = "strategy"`): kosullar olustuysa bir `Signal` (yon, giris, stop, hedef) dondurur.
Yeni bir modul eklemek tek bir dosya ve `modules/__init__.py` icinde tek bir kayit satiridir.
Moduller V9 raporunu ve mumlari yalnizca OKUR; V9'a, risk kapisina ya da emir yoluna dokunmaz.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from ...config import CUSTOM_STRATEGY_PREFIX

Kind = Literal["vote", "strategy"]


@dataclass(frozen=True)
class Vote:
    module: str
    value: int  # 1 destek, 0 cekimser, -1 karsi
    detail: str


@dataclass(frozen=True)
class Signal:
    side: Literal["BUY", "SELL"]
    entry: float
    stop: float
    target: float
    reason: str
    bar_time: int  # sinyali ureten son KAPANMIS M15 mumunun acilis zamani
    plan: dict | None = None  # istege bagli cikis plani (ileri test icin): tur, model, puan, hedef fiyatlari


@dataclass(frozen=True)
class Context:
    symbol: str
    now: float
    kind: str = "forex"  # enstruman turu: forex | metal | crypto
    side: str | None = None  # oy modulleri icin adayin yonu (BUY / SELL)
    report: dict = field(default_factory=dict)  # V9 raporu (sozluk); yoksa bos
    bars: dict = field(default_factory=dict)  # zaman dilimi -> kapanmis mumlar (eskiden yeniye)
    quote: dict | None = None
    instrument: Any = None

    @property
    def wanted(self) -> str:
        return "bullish" if self.side == "BUY" else "bearish"


class Module(Protocol):
    id: str
    kind: Kind

    def evaluate(self, context: Context) -> Vote | Signal | None: ...


_REGISTRY: dict[str, Module] = {}


def register(module: Module) -> Module:
    if module.id in _REGISTRY:
        raise ValueError(f"modul iki kez kaydedildi: {module.id}")
    if module.kind not in ("vote", "strategy"):
        raise ValueError(f"gecersiz modul turu: {module.kind}")
    if module.kind == "strategy" and not module.id.startswith(CUSTOM_STRATEGY_PREFIX):
        # On ek, V9 disindaki stratejilerin varsayilan olarak golgede baslamasini saglar.
        raise ValueError(f"strateji kimligi '{CUSTOM_STRATEGY_PREFIX}' ile baslamali: {module.id}")
    _REGISTRY[module.id] = module
    return module


def modules(kind: Kind | None = None) -> list[Module]:
    """Kayit sirasiyla moduller."""
    return [m for m in _REGISTRY.values() if kind is None or m.kind == kind]


def get(module_id: str) -> Module | None:
    return _REGISTRY.get(module_id)


# ---------------------------------------------------------------- ortak yardimcilar
def dig(data: Any, *path: str) -> Any:
    for key in path:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def direction(value: Any) -> str | None:
    """Farkli modullerin yon ifadelerini ('bullish', 'UP', 'BUY' ...) tek bicime indirger."""
    if not isinstance(value, str):
        return None
    text = value.lower()
    if text in ("bullish", "buy", "up", "uptrend", "long") or text.startswith("bull"):
        return "bullish"
    if text in ("bearish", "sell", "down", "downtrend", "short") or text.startswith("bear"):
        return "bearish"
    return None


def agree(found: str | None, wanted: str) -> int:
    return 0 if found is None else (1 if found == wanted else -1)
