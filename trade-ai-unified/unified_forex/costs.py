"""Dated declared execution assumptions; never authenticated broker costs."""
from dataclasses import dataclass
from forex.core import finite,price_round
from pydantic import BaseModel,ConfigDict,Field

VERSION='fx-dated-costs-v8-1'


class CostDeclaration(BaseModel):
    model_config=ConfigDict(extra='forbid',frozen=True,allow_inf_nan=False,strict=True)
    commission_round_trip_per_lot:float|None=Field(default=None,ge=0,le=1_000_000)
    commission_currency:str|None=Field(default=None,pattern='^[A-Z]{3}$')
    spread_price:float|None=Field(default=None,ge=0,le=10000)
    slippage_price:float|None=Field(default=None,ge=0,le=10000)


def at_rules(meta,reference,defaults):
    declared=CostDeclaration.model_validate(meta.get('cost_assumptions',{}))
    tick=finite(meta.get('tick_size'),'tick size');value=finite(meta.get('tick_value'),'tick value')
    if min(tick,value,reference)<=0:raise ValueError('Cost conversion metadata invalid')
    commission=declared.commission_round_trip_per_lot
    if commission is not None and declared.commission_currency!=meta.get('account_currency'):raise ValueError('Declared commission currency mismatch')
    factor=value/tick
    return {'commission_account_per_lot':commission if commission is not None else reference*defaults[0]/10000*factor,
            'spread':price_round(declared.spread_price if declared.spread_price is not None else reference*defaults[1]/10000,tick,'up'),
            'slippage':declared.slippage_price if declared.slippage_price is not None else reference*defaults[2]/10000,
            'basis':'DECLARED_EPOCH_OVERRIDE' if meta.get('cost_assumptions') else 'FIXED_BPS_SIMULATION_ASSUMPTION',
            'version':VERSION,'authenticated':False}
