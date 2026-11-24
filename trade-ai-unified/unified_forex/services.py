"""Bounded scanner and local alert events composed with retained Forex services."""
from datetime import datetime,timezone
from hashlib import sha256
from threading import RLock
from collections import OrderedDict
from .engine import AnalysisEngine
from .market import RequestCache
from .strategies import BREAKOUT
from forex.core import SYMBOLS,TIMEFRAMES,DataError,finite
from forex.alerts import AlertEngine as V5Alerts
from forex.information import parse_rss


def scan(provider,symbols=SYMBOLS,timeframes=('M15',),*,now=None,balance=None,risk_pct=1,limit=16):
    if (not symbols or not timeframes or len(symbols)*len(timeframes)>limit
            or len(set(symbols))!=len(symbols) or len(set(timeframes))!=len(timeframes)
            or any(s not in SYMBOLS for s in symbols) or any(tf not in TIMEFRAMES for tf in timeframes)):
        raise DataError('invalid bounded scanner request')
    cache=RequestCache(provider);engine=AnalysisEngine()
    if now is None:
        for symbol in symbols:
            for method,args in [('metadata',(symbol,)),('quote',(symbol,))]+[('candles',(symbol,tf,256)) for tf in dict.fromkeys((*timeframes,*('D1' if tf=='D1' else 'H4' for tf in timeframes)))]:
                try:getattr(cache,method)(*args)
                except DataError:pass
    when=now if now is not None else datetime.now(timezone.utc).timestamp()
    reports=[engine.analyze(cache,s,tf,now=when,balance=balance,risk_pct=risk_pct).model_dump() for s in symbols for tf in timeframes]
    reports.sort(key=lambda r:(r['data_status']!='OK',r['final_decision'] not in ('BUY_CANDIDATE','SELL_CANDIDATE'),
                               r['trading_eligibility']!='ELIGIBLE',r['symbol'],r['timeframe']))
    return {'provider':provider.name,'as_of_utc':datetime.fromtimestamp(when,timezone.utc).isoformat(),
            'ranking_policy':'valid data, candidate, supplied risk eligibility, symbol/timeframe; no probability score',
            'results':reports,'cached_resource_reads':len(cache.cache),
            'cache_stats':{'hits':cache.hits,'misses':cache.misses,'scope':'request_only'}}


class Alerts:
    def __init__(self,cooldown_seconds=300):
        if type(cooldown_seconds) is not int or not 1<=cooldown_seconds<=3600:raise ValueError('Cooldown1..3600 seconds required')
        self.legacy=V5Alerts(cooldown_seconds);self.cooldown=cooldown_seconds
        self.sent={};self.prices={};self.sessions={};self.lock=RLock()
        self.seen=OrderedDict();self.setups={};self.capacity=256
    def evaluate(self,report,*,now=None,price_levels=()):
        with self.lock:return self._evaluate(report,now=now,price_levels=price_levels)
    def _evaluate(self,report,*,now=None,price_levels=()):
        if len(price_levels)>10:raise ValueError('at most10 price levels')
        price_levels=tuple(finite(p,'price level') for p in price_levels)
        if any(p<=0 for p in price_levels):raise ValueError('positive price levels required')
        r=report.model_dump() if hasattr(report,'model_dump') else report
        if r['symbol'] not in SYMBOLS or r['timeframe'] not in TIMEFRAMES:raise ValueError('Unsupported alert identity')
        when=now if now is not None else datetime.fromisoformat(r['as_of_utc'])
        plan=None if r['entry_zone'] is None else {'entry':r['entry_zone']['low'],'stop_loss':r['stop_loss']}
        old={'symbol':r['symbol'],'timeframe':r['timeframe'],'signal':r['legacy_signal'],'plan':plan,
             'reasons':r['decision_reasons'],'data_status':r['data_status'],
             'session':{'broker':{'status':r['market_status']}}}
        q=r['freshness'];quote={'spread':q.get('spread'),'max_spread':q.get('max_spread')}
        result=self.legacy.evaluate(old,quote=quote,now=when)
        extra=[];key=(r['symbol'],r['timeframe'])
        action=(r.get('market_structure') or {}).get('price_action',{})
        if action.get('structure',{}).get('events'):extra.append(('STRUCTURE_CHANGE','confirmed closed structure event'))
        if any(s['strategy_id']==BREAKOUT and s['status']=='CONFIRMED' for s in r['strategies']):
            extra.append(('CONFIRMED_BREAKOUT','closed price breakout setup observed'))
        if r['risk_policy'] and r['risk_policy']['decision']=='BLOCK':extra.append(('RISK_VETO','; '.join(r['risk_policy']['reasons'])))
        if any('macro' in reason for reason in r['decision_reasons']):extra.append(('HIGH_IMPACT_MACRO','declared event risk context; coverage unverified'))
        with self.lock:
            setup=next((s.get('setup_id') for s in r['strategies'] if s['status']=='CONFIRMED' and r.get('routing') and s['strategy_id']==r['routing'].get('strategy_id')),None) if r['entry_zone'] is not None else None
            prior_setup=self.setups.get(key)
            if prior_setup and not setup:extra.append(('SETUP_INVALIDATED','previous setup is no longer eligible; see current refusal reasons'))
            if prior_setup and any('maximum age' in s['reason'] for s in r['strategies']):extra.append(('SETUP_EXPIRED','maximum closed-candle setup age exceeded'))
            self.setups[key]=setup
            previous=self.sessions.get(key)
            if previous is not None and previous!=r['market_status']:extra.append(('SESSION_CHANGE',previous+' -> '+r['market_status']))
            self.sessions[key]=r['market_status']
            price=q.get('bid');before=self.prices.get(key)
            if price is not None:
                if before is not None:
                    for level in price_levels:
                        if (before<level<=price) or (before>level>=price):extra.append(('PRICE_LEVEL:'+str(level),'crossed declared level '+str(level)))
                self.prices[key]=price
            self.sent={k:t for k,t in self.sent.items() if (when-t).total_seconds()<self.cooldown}
            for kind,reason in extra:
                event_key=(*key,kind)
                if event_key in self.sent:continue
                self.sent[event_key]=when
                result.append({'id':sha256(f'{event_key}|{when.isoformat()}'.encode()).hexdigest()[:20],
                               'type':kind,'source':'unified-v6','symbol':key[0],'timeframe':key[1],
                               'timestamp':when.isoformat(),'reason':reason,'execution_permission':False})
            normalized=[]
            for event in result:
                typ=event['type']
                if typ=='SETUP_CONFIRMED':identity=setup
                elif typ in ('SETUP_INVALIDATED','SETUP_EXPIRED'):identity=prior_setup
                elif typ=='STRUCTURE_CHANGE':identity=repr(sorted((e['kind'],e['direction'],e['pivot_time_ms'],e['event_time_ms']) for e in action['structure']['events']))
                elif typ=='CONFIRMED_BREAKOUT':identity=repr(sorted(s.get('setup_id') for s in r['strategies'] if s['strategy_id']==BREAKOUT and s['status']=='CONFIRMED'))
                else:identity=when.isoformat()
                event_id=sha256(f'{key}|{typ}|{identity}'.encode()).hexdigest()[:24]
                if event_id in self.seen:continue
                self.seen[event_id]=when.isoformat()
                normalized.append({**event,'id':event_id,'event_id':event_id,'severity':event.get('severity','MEDIUM'),
                    'execution_permission':False,'restart_semantics':'in_memory_dedup_resets_on_restart','source_version':'fx-alerts-v7-1'})
            while len(self.seen)>self.capacity:self.seen.popitem(last=False)
            self.sent=dict(list(self.sent.items())[-self.capacity:])
            self.legacy.sent=dict(list(self.legacy.sent.items())[-self.capacity:])
        return normalized


def ingest_news(payload,source,now=None):
    rows=parse_rss(payload,source,now)
    retrieved=(now if now is not None else datetime.now(timezone.utc)).isoformat()
    return {'items':[{**r,'retrieved_at':retrieved} for r in rows],'data_status':'DECLARED_SOURCE',
            'coverage_verified':False,'directional_permission':False}
