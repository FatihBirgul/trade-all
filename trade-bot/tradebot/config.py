"""Ayarlar.

`Settings` yalnizca ortam degiskenlerinden gelir (sirlar dahil) ve calisirken degismez.
`BotSettings` SQLite'ta saklanir ve API uzerinden degistirilir; araliklar spec §6.3'e gore
burada dogrulanir, boylece aralik disi deger hicbir yoldan iceri giremez.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    exness_api_key: SecretStr
    exness_private_key: SecretStr
    exness_account_id: str = Field(pattern=r"^[1-9][0-9]{0,19}$")
    exness_gateway_host: str = Field(min_length=1)
    exness_ap_host: str | None = None
    db_path: Path = Path("/var/lib/tradebot/tradebot.db")
    v9_root: Path = REPO_ROOT / "trade-ai-unified"
    api_bind: str = "127.0.0.1:8090"


_ENV = {
    "exness_api_key": "EXNESS_API_KEY",
    "exness_private_key": "EXNESS_PRIVATE_KEY",
    "exness_account_id": "EXNESS_ACCOUNT_ID",
    "exness_gateway_host": "EXNESS_GATEWAY_HOST",
    "exness_ap_host": "EXNESS_AP_HOST",
    "db_path": "TRADEBOT_DB_PATH",
    "v9_root": "TRADEBOT_V9_ROOT",
    "api_bind": "TRADEBOT_API_BIND",
}
_REQUIRED = ("exness_api_key", "exness_private_key", "exness_account_id", "exness_gateway_host")


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env
    values = {field: env[name] for field, name in _ENV.items() if env.get(name)}
    missing = [_ENV[field] for field in _REQUIRED if field not in values]
    if missing:
        # Deger degil yalnizca degisken adi yazilir; sirlar hata metnine girmez.
        raise ValueError("eksik ortam degiskeni: " + ", ".join(missing))
    return Settings(**values)


class RiskSettings(BaseModel):
    """Spec §6.3. Sabit kurallar Literal ile kilitlidir."""

    model_config = ConfigDict(extra="forbid")

    risk_pct: float = Field(default=0.5, ge=0.25, le=1.0)
    max_open_bot: int = Field(default=3, ge=1, le=5)
    per_symbol: Literal[1] = 1
    per_currency_side: Literal[2] = 2
    daily_loss_pct: float = Field(default=5, ge=2, le=10)
    total_loss_pct: float = Field(default=25, ge=10, le=30)


class ManageSettings(BaseModel):
    """Spec §6.5 kademeli stop esikleri."""

    model_config = ConfigDict(extra="forbid")

    be_at_r: float = Field(default=1.0, gt=0, le=5)
    partial_at_r: float = Field(default=2.0, gt=0, le=10)
    partial_fraction: float = Field(default=0.5, gt=0, lt=1)
    trail_atr_mult: float = Field(default=1.0, gt=0, le=10)
    tp2_r: float = Field(default=3.0, gt=0, le=20)


FUSION_MODULES = ("mtf", "regime", "candle_pattern", "chart_pattern", "structure", "momentum", "confluence",
                  "other_strategies", "session")


def _default_weights() -> dict[str, float]:
    return {module: (2.0 if module in ("mtf", "regime") else 1.0) for module in FUSION_MODULES}


class FusionSettings(BaseModel):
    """Spec §6.2 guven puani: esikler ve modul agirliklari. Carpanlar sabittir: 0.5x / 0.75x / 1.0x."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    min_score: float = Field(default=40, ge=0, le=100)  # altinda islem yok (gozlem)
    mid_score: float = Field(default=60, ge=0, le=100)  # altinda 0.5x risk
    high_score: float = Field(default=80, ge=0, le=100)  # altinda 0.75x, ustunde 1.0x risk
    weights: dict[str, float] = Field(default_factory=_default_weights)
    pause_min_trades: int = Field(default=20, ge=5, le=500)  # karne: en az bu kadar islemden sonra
    pause_avg_r: float = Field(default=0.0, ge=-1.0, le=1.0)  # ortalama R bunun altindaysa strateji duraklatilir

    @model_validator(mode="after")
    def _ordered(self):
        if not self.min_score <= self.mid_score <= self.high_score:
            raise ValueError("esikler artan sirada olmali: min_score <= mid_score <= high_score")
        if any(not 0 <= float(w) <= 10 for w in self.weights.values()):
            raise ValueError("modul agirliklari 0 ile 10 arasinda olmali")
        unknown = set(self.weights) - set(FUSION_MODULES)
        if unknown:
            raise ValueError("bilinmeyen modul: " + ", ".join(sorted(unknown)))
        self.weights = {**_default_weights(), **self.weights}
        return self


class NewsSettings(BaseModel):
    """Spec §6.6 haber penceresi: yuksek etkili haberden once ve sonra bu kadar dakika yeni bot islemi yok."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    window_minutes: int = Field(default=30, ge=5, le=120)


class BotSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk: RiskSettings = Field(default_factory=RiskSettings)
    manage: ManageSettings = Field(default_factory=ManageSettings)
    news: NewsSettings = Field(default_factory=NewsSettings)
    fusion: FusionSettings = Field(default_factory=FusionSettings)
    enabled_symbols: set[str] | None = None  # None = hepsi
    enabled_strategies: set[str] | None = None  # None = hepsi (eski alan; listede olmayan strateji kapali sayilir)
    # Strateji kipi: live (gercek islem), shadow (yalnizca sanal izleme), off. Listede olmayan strateji live'dir.
    strategy_modes: dict[str, Literal["live", "shadow", "off"]] = Field(default_factory=dict)
    dry_run: bool = True
    commission_per_lot: float = Field(default=0.0, ge=0)


CUSTOM_STRATEGY_PREFIX = "tb_"  # V9 disindaki (yeni) stratejilerin kimlik on eki


def strategy_mode(settings: BotSettings, strategy_id: str) -> str:
    """Stratejinin etkin kipi: acik kip > (yeni strateji ise `shadow`) > eski `enabled_strategies` > `live`.

    Yeni stratejiler (spec §6.2) acikca canliya alinmadikca GOLGEdedir; V9 stratejileri dogrudan canlida baslar.
    """
    mode = settings.strategy_modes.get(strategy_id)
    if mode is not None:
        return mode
    if strategy_id.startswith(CUSTOM_STRATEGY_PREFIX):
        return "shadow"
    if settings.enabled_strategies is not None and strategy_id not in settings.enabled_strategies:
        return "off"
    return "live"
