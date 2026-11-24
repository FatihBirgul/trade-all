"""Read-only MT5 and explicitly labelled fixture data providers."""
from __future__ import annotations
import threading
import os
import json
import copy
from datetime import datetime, timezone
from .core import DataError, SYMBOLS, DATA_SYMBOLS, TIMEFRAMES, finite, validate_bars

class FixtureProvider:
    name='fixture-test-only'
    def __init__(self, data): self.data=data
    def metadata(self,symbol):
        return copy.deepcopy({'symbol':symbol,'price_kind':'bid','source':self.name,
                              **self.data[symbol]['metadata']})
    def quote(self,symbol): return copy.deepcopy(self.data[symbol]['quote'])
    def candles(self,symbol,timeframe,count=220): return copy.deepcopy(self.data[symbol]['candles'][timeframe][-count:])
    def loss_for(self,symbol,side,lots,entry,stop):
        m=self.metadata(symbol)
        return (stop-entry)*(1 if side=='BUY' else -1)*lots*m['tick_value']/m['tick_size']

class MT5Provider:
    name='mt5'
    def __init__(self, mt5=None, mappings=None, *, historical_evidence=None):
        if mt5 is None:
            try: import MetaTrader5 as mt5
            except ImportError: raise DataError('MetaTrader5 package unavailable; Windows terminal required')
        if mappings is None:
            raw=os.environ.get('MT5_SYMBOL_MAP','{}')
            try: mappings=json.loads(raw)
            except json.JSONDecodeError: raise DataError('MT5_SYMBOL_MAP must be JSON')
            if not isinstance(mappings,dict) or any(k not in DATA_SYMBOLS or not isinstance(v,str) for k,v in mappings.items()):
                raise DataError('invalid MT5_SYMBOL_MAP')
        raw_hours=os.environ.get('MT5_BROKER_HOURS','{}')
        try: self.hours=json.loads(raw_hours)
        except json.JSONDecodeError: raise DataError('MT5_BROKER_HOURS must be JSON')
        if not isinstance(self.hours,dict): raise DataError('invalid MT5_BROKER_HOURS')
        raw_spread=os.environ.get('MT5_MAX_SPREAD','{}')
        try: self.max_spread=json.loads(raw_spread)
        except json.JSONDecodeError: raise DataError('MT5_MAX_SPREAD must be JSON')
        if not isinstance(self.max_spread,dict): raise DataError('invalid MT5_MAX_SPREAD')
        from .spread_policy import load_policy
        self.spread_policy = load_policy(os.environ.get('MT5_SPREAD_POLICY_FILE'))
        self.mt5=mt5; self.lock=threading.RLock(); self.mappings=mappings
        self.connected=False; self._demo_account_guard=None; self._read_only_real=False
        from .historical_sessions import configured_historical_store
        self.historical_evidence = (historical_evidence if historical_evidence is not None
                                    else configured_historical_store())

    def historical_session_policy(self, symbol, as_of):
        """Independent reviewed evidence; no environment/API approval switch."""
        if not hasattr(self, 'historical_evidence'):
            return None  # Existing fixture adapters without a configured store.
        with self.lock:
            actual, _ = self._symbol(symbol)
            account = self._call('account_info')
            self._check_account_guard()
            if account is None:
                raise DataError('MT5 account unavailable')
            return self.historical_evidence.evaluate(
                broker='Exness', server=getattr(account, 'server', None),
                product='Standard Cent', currency=getattr(account, 'currency', None),
                broker_symbol=actual, canonical_symbol=symbol, as_of=as_of)
    def _call(self, name, *args):
        try: return getattr(self.mt5,name)(*args)
        except Exception as exc:
            self.connected=False
            raise DataError(f'MT5 {name} failed') from exc
    def connect(self):
        with self.lock:
            if self.connected and hasattr(self.mt5, 'terminal_info'):
                terminal = self._call('terminal_info')
                if terminal is None or not getattr(terminal, 'connected', False):
                    try: self._call('shutdown')
                    except DataError: pass
                    self.connected = False
            if not self.connected:
                if not self._call('initialize'): raise DataError(f"MT5 initialize failed: {self._call('last_error')}")
                self.connected=True
    def health(self):
        with self.lock:
            self.connect()
            terminal = self._call('terminal_info') if hasattr(self.mt5, 'terminal_info') else None
            if terminal is None or not getattr(terminal, 'connected', False):
                raise DataError('MT5 terminal disconnected')
            return {'connected':True,'trade_allowed':bool(getattr(terminal,'trade_allowed',False))}
    def demo_preflight(self, expected_server, expected_currency):
        """Read account type before any symbol, quote, candle or profit access."""
        return self.account_preflight('DEMO_ONLY', expected_server, expected_currency)

    def account_preflight(self, policy, expected_server, expected_currency):
        """Explicit account-mode gate; never exposes login or real balance."""
        with self.lock:
            self._demo_account_guard=None; self._read_only_real=False
            if policy not in ('DEMO_ONLY', 'REAL_READONLY_DATA') or not expected_server or not expected_currency:
                raise DataError('account preflight configuration unavailable')
            self.connect()
            terminal = self._call('terminal_info') if hasattr(self.mt5, 'terminal_info') else None
            if terminal is None or getattr(terminal, 'connected', False) is not True:
                raise DataError('demo preflight blocked')
            account = self._call('account_info')
            modes = [getattr(self.mt5, 'ACCOUNT_TRADE_MODE_'+name, None)
                     for name in ('DEMO', 'CONTEST', 'REAL')]
            expected_mode = modes[0] if policy == 'DEMO_ONLY' else modes[2]
            if (account is None or any(type(mode) is not int for mode in modes)
                    or len(set(modes)) != 3 or type(getattr(account, 'trade_mode', None)) is not int
                    or account.trade_mode != expected_mode
                    or type(getattr(account, 'login', None)) is not int
                    or getattr(account, 'server', None) != expected_server
                    or getattr(account, 'currency', None) != expected_currency):
                raise DataError('demo preflight blocked')
            balance = None
            if policy == 'DEMO_ONLY':
                balance = finite(getattr(account, 'balance', None), 'demo balance')
                if balance <= 0:
                    raise DataError('demo preflight blocked')
            self._demo_account_guard=(account.login, expected_server, expected_currency, expected_mode)
            self._read_only_real=policy == 'REAL_READONLY_DATA'
            return {'status':'PASS', 'currency':expected_currency,
                    'balance':balance}
    def close(self):
        with self.lock:
            if self.connected:
                try: self._call('shutdown')
                finally: self.connected=False
    def _symbol(self, symbol):
        if symbol not in DATA_SYMBOLS: raise DataError('unsupported symbol')
        if os.environ.get('MT5_ANALYSIS_POLICY') == 'REAL_READONLY_DATA' and not self._read_only_real:
            self.account_preflight('REAL_READONLY_DATA', os.environ.get('MT5_EXPECTED_REAL_SERVER'),
                                   os.environ.get('MT5_EXPECTED_REAL_CURRENCY'))
        self.connect()
        self._check_account_guard()
        actual=self.mappings.get(symbol,symbol)
        info=self._call('symbol_info',actual)
        self._check_account_guard()
        if info is None or not actual or not isinstance(actual,str):
            raise DataError('broker symbol mapping unverified')
        # An alias is trusted only when explicitly configured and resolves to an exact MT5 name.
        if actual != symbol and self.mappings.get(symbol) != actual:
            raise DataError('broker symbol mapping unverified')
        if symbol not in actual.upper():
            raise DataError('broker symbol does not match canonical instrument')
        base,profit=getattr(info,'currency_base',None),getattr(info,'currency_profit',None)
        if base and profit and (base.upper()!=symbol[:3] or profit.upper()!=symbol[3:]):
            raise DataError('broker instrument currencies mismatch')
        if self._read_only_real:
            if getattr(info, 'visible', None) is not True:
                raise DataError('broker symbol not visible in read-only mode')
        elif not self._call('symbol_select',actual,True): raise DataError('symbol_select failed')
        return actual,info
    def _check_account_guard(self):
        if self._demo_account_guard is None:
            return
        account = self._call('account_info')
        if account is None or (getattr(account,'login',None),getattr(account,'server',None),
                               getattr(account,'currency',None),getattr(account,'trade_mode',None)) != self._demo_account_guard:
            raise DataError('account changed during analysis')
    def metadata(self,symbol):
        with self.lock:
            actual,i=self._symbol(symbol)
            account=self._call('account_info')
            self._check_account_guard()
            if account is None: raise DataError('MT5 account unavailable')
            required=('trade_contract_size','trade_tick_size','trade_tick_value','point','volume_min','volume_max','volume_step','trade_stops_level')
            missing = [key for key in required if not hasattr(i,key)]
            if missing: raise DataError('incomplete broker metadata: '+','.join(missing))
            invalid = [key for key in required[:-1] if finite(getattr(i,key),key) <= 0]
            if invalid: raise DataError('invalid broker metadata: '+','.join(invalid))
            mode=getattr(i,'trade_mode',None)
            allowed={1:['BUY'],2:['SELL'],4:['BUY','SELL']}.get(mode,[])
            declared_hours=self.hours.get(symbol)
            # A configured schedule is only an operator declaration. In REAL
            # read-only mode no independently verified instrument session is
            # available, so it cannot authorize missing candles or plans.
            bound_hours=(declared_hours if not self._read_only_real
                         and isinstance(declared_hours,dict)
                         and declared_hours.get('broker_symbol')==actual else None)
            calc_mode = getattr(i, 'trade_calc_mode', None)
            calc_name = next((name for name in ('FOREX', 'FOREX_NO_LEVERAGE', 'CFD', 'CFDLEVERAGE')
                              if type(calc_mode) is int and
                              getattr(self.mt5, 'SYMBOL_CALC_MODE_'+name, None) == calc_mode), None)
            meta = {'symbol':symbol,'broker_symbol':actual,'asset_type':'metal' if symbol=='XAUUSD' else 'forex',
                    'source':'mt5','digits':getattr(i,'digits',None),
                    'market_type':'unverified','contract_type':'unverified','price_kind':'bid',
                    'trade_calc_mode':calc_mode, 'trade_calc_mode_name':calc_name,
                    'symbol_spread_points':getattr(i,'spread',None),
                    'trade_mode':mode,'allowed_directions':allowed,
                    'base_currency':getattr(i,'currency_base',None),
                    'profit_currency':getattr(i,'currency_profit',None),
                    'margin_currency':getattr(i,'currency_margin',None),
                    'freeze_level':getattr(i,'trade_freeze_level',None),
                    'tick_value_profit':getattr(i,'trade_tick_value_profit',None),
                    'tick_value_loss':getattr(i,'trade_tick_value_loss',None),
                    'broker_server':getattr(account,'server',None),
                    'max_spread':None if self._read_only_real else self.max_spread.get(symbol),
                    'contract_size':i.trade_contract_size,
                    'tick_size':i.trade_tick_size,'tick_value':i.trade_tick_value,
                    'point':i.point,'volume_min':i.volume_min,'volume_max':i.volume_max,
                    'volume_step':i.volume_step,'stops_level':i.trade_stops_level,
                    'trade_allowed':bool(allowed) and getattr(account,'trade_allowed',False) is True,
                    'broker_hours':bound_hours,
                    'broker_hours_status':('UNVERIFIED_REAL_SESSION' if self._read_only_real
                                           else 'OPERATOR_DECLARED' if bound_hours
                                           else 'UNVERIFIED_INSTRUMENT'),
                    'account_currency':getattr(account,'currency',None),
                    'tick_value_currency':getattr(account,'currency',None) if account else None}
            from .broker_contract import contract_observation
            from .spread_policy import bind_rule
            meta['broker_contract'] = contract_observation(meta, datetime.now(timezone.utc).isoformat())
            meta['broker_contract_required'] = self._read_only_real
            meta['spread_policy_required'] = self._read_only_real
            meta['spread_policy'] = bind_rule(self.spread_policy, symbol, actual,
                                              meta['broker_server'], meta['account_currency'])
            return meta
    def quote(self,symbol):
        with self.lock:
            actual,_=self._symbol(symbol); t=self._call('symbol_info_tick',actual)
            self._check_account_guard()
            if t is None: raise DataError('tick unavailable')
            stamp=t.time_msc/1000 if getattr(t,'time_msc',0) else t.time
            bid,ask=finite(t.bid,'bid'),finite(t.ask,'ask')
            age=datetime.now(timezone.utc).timestamp()-finite(stamp,'tick time')
            if age>120 or age < -5: raise DataError('stale tick')
            if bid<=0 or ask<=bid: raise DataError('invalid bid/ask')
            return {'symbol':symbol,'bid':bid,'ask':ask,'spread':ask-bid,'time':stamp,
                    'provider':'mt5','freshness':'FRESH'}
    def candles(self,symbol,timeframe,count=220):
        if timeframe not in TIMEFRAMES: raise DataError('invalid timeframe')
        if not 1<=count<=10000: raise DataError('invalid candle count')
        with self.lock:
            actual,_=self._symbol(symbol)
            tf=getattr(self.mt5,'TIMEFRAME_'+timeframe)
            rows=self._call('copy_rates_from_pos',actual,tf,0,count+1)
            self._check_account_guard()
            if rows is None: raise DataError('candles unavailable')
            now=datetime.now(timezone.utc).timestamp()
            # MT5 bar timestamp marks the OPEN; omit current unfinished bar.
            try:
                result=[{'time':int(r['time']),'open':float(r['open']),'high':float(r['high']),
                         'low':float(r['low']),'close':float(r['close']),'tick_volume':int(r['tick_volume'])}
                        for r in rows if int(r['time'])+TIMEFRAMES[timeframe]<=now][-count:]
            except (KeyError,TypeError,ValueError) as exc:
                raise DataError('invalid MT5 candle data') from exc
            validate_bars(result,timeframe,now)
            return result
    def calc_profit(self,side,lots,entry,stop):
        with self.lock:
            order_type=self.mt5.ORDER_TYPE_BUY if side=='BUY' else self.mt5.ORDER_TYPE_SELL
            # The symbol is selected by the caller's metadata/quote request.
            raise DataError('symbol argument required for MT5 profit calculation')
    def loss_for(self,symbol,side,lots,entry,stop):
        if side not in ('BUY','SELL') or min(finite(lots,'lots'),finite(entry,'entry'),finite(stop,'stop'))<=0:
            raise DataError('invalid broker profit calculation inputs')
        with self.lock:
            actual,_=self._symbol(symbol)
            typ=self.mt5.ORDER_TYPE_BUY if side=='BUY' else self.mt5.ORDER_TYPE_SELL
            result=self._call('order_calc_profit',typ,actual,lots,entry,stop)
            self._check_account_guard()
            if result is None: raise DataError('order_calc_profit failed')
            return result
