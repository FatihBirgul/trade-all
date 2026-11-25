"""API istek govdeleri. Araliklar burada dogrulanir; gecersiz govde 422 doner."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PairRequest(Strict):
    code: str = Field(pattern=r"^[0-9]{6}$")


class PositionPatch(Strict):
    sl: float | None = Field(default=None, gt=0)
    tp: float | None = Field(default=None, gt=0)
    manage: bool | None = None

    @model_validator(mode="after")
    def _something(self):
        if self.sl is None and self.tp is None and self.manage is None:
            raise ValueError("sl, tp ya da manage alanlarindan en az biri gerekli")
        return self


class CloseRequest(Strict):
    volume: float | None = Field(default=None, gt=0)


class ManualTrade(Strict):
    symbol: str = Field(pattern=r"^[A-Z0-9]{3,12}$")
    side: Literal["BUY", "SELL"]
    sl_distance: float = Field(gt=0)  # fiyat cinsinden; SL zorunlu
    tp_distance: float | None = Field(default=None, gt=0)
    lots: float | None = Field(default=None, gt=0)  # verilmezse risk yuzdesine gore hesaplanir
    # Uygulamanin urettigi tekil kimlik: ayni istek (zaman asimi sonrasi) tekrarlanirsa ikinci emir acilmaz.
    client_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._~-]{8,64}$")


class ResumeRequest(Strict):
    confirm_halt: bool = False


class CloseAllRequest(Strict):
    confirm: str


class StrategyModeRequest(Strict):
    mode: Literal["live", "shadow", "off"]
    confirm: bool = False  # golgedeki/duraklatilmis stratejiyi canliya almak icin bilincli onay


class DeviceRequest(Strict):
    expo_token: str = Field(pattern=r"^Expo(nent)?PushToken\[[A-Za-z0-9_-]{1,200}\]$")
