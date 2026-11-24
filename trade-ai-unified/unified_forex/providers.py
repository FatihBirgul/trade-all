"""Retained read-only MT5 lifecycle, with explicit V6 identity/schedule declarations."""
import json,os
from forex.providers import MT5Provider,FixtureProvider
from forex.core import DataError


class ContractMT5Provider(MT5Provider):
    def margin_for(self,symbol,side,lots,price):
        from forex.core import finite
        if side not in ('BUY','SELL'):raise DataError('invalid margin sample side')
        lots=finite(lots,'lots');price=finite(price,'price')
        if min(lots,price)<=0:raise DataError('positive margin sample required')
        with self.lock:
            actual,_=self._symbol(symbol)
            if not callable(getattr(self.mt5,'order_calc_margin',None)):raise DataError('read-only margin calculation unavailable')
            action=getattr(self.mt5,'ORDER_TYPE_BUY',0) if side=='BUY' else getattr(self.mt5,'ORDER_TYPE_SELL',1)
            value=finite(self._call('order_calc_margin',action,actual,lots,price),'broker margin')
            if value<0:raise DataError('negative broker margin')
            return value
    def __init__(self,*args,instruments=None,**kwargs):
        super().__init__(*args,**kwargs)
        try:self.instruments=instruments if instruments is not None else json.loads(os.environ.get('MT5_INSTRUMENT_CONTRACTS','{}'))
        except ValueError as exc:raise DataError('invalid MT5_INSTRUMENT_CONTRACTS') from exc
        if not isinstance(self.instruments,dict):raise DataError('instrument contract map required')
    def metadata(self,symbol):
        meta=super().metadata(symbol)
        supplied=self.instruments.get(symbol,{})
        allowed={'market_type','contract_type','broker_hours_verified','broker_hours_trust','schedule_source'}
        if not isinstance(supplied,dict) or set(supplied)-allowed:raise DataError('unknown instrument declaration fields')
        # Declarations never override tick/contract/currency/permission values
        # obtained from the broker, and never prove live connectivity by themselves.
        if supplied.get('broker_hours_trust') not in (None,'DECLARED','UNAVAILABLE'):
            raise DataError('operator cannot assert authenticated broker schedule')
        merged={**meta,**supplied}
        from .market import schedule_contract
        merged['schedule_provenance']=schedule_contract(merged)
        return merged
