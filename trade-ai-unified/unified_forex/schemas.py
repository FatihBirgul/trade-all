"""Additive nested financial schema for the retained schema6 envelope."""
from pydantic import BaseModel,ConfigDict,Field
from typing import Literal


class FinancialModel(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    def __getitem__(self,key):
        if key not in type(self).model_fields:raise KeyError(key)
        return getattr(self,key)
    def get(self,key,default=None):return getattr(self,key,default)


class EntryZone(FinancialModel):
    low:float=Field(gt=0)
    high:float=Field(gt=0)
    price_side:Literal['bid','ask']


class LotSizing(FinancialModel):
    lots:float=Field(gt=0)
    estimated_risk:float=Field(ge=0)
    unrounded_risk:float=Field(gt=0)
    risk_cap:float=Field(gt=0)
    currency:str=Field(pattern='^[A-Z]{3}$')


class CostAdjustedPlan(FinancialModel):
    gross_reward_risk:float
    gross_price_reward_risk:float
    gross_loss_at_minimum_lot:float=Field(gt=0)
    gross_reward_at_minimum_lot:float=Field(gt=0)
    net_reward_risk:float
    net_reward_at_minimum_lot:float
    loss_at_minimum_lot:float=Field(gt=0)
    currency:str
    version:str
    slippage_basis:str
    commission_basis:str


class RiskPolicy(FinancialModel):
    decision:Literal['PASS','BLOCK']
    reasons:list[str]
    fingerprint:str
    sizing:LotSizing|None
    records_source:str
    daily_planned_risk:float=Field(ge=0)
    daily_realized_loss:float=Field(ge=0)
    cost_adjusted_plan:CostAdjustedPlan|None=None
