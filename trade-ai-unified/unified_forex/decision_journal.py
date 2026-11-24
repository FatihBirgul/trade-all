"""Opt-in immutable analysis and later observations; no order/position engine."""
from collections import OrderedDict
from datetime import datetime,timezone,timedelta
from hashlib import sha256
from threading import RLock
import json
from forex.contracts import canonical
from forex.core import TIMEFRAMES,finite

VERSION='fx-forward-journal-v9-1'


class DecisionJournal:
    def __init__(self,capacity=256):
        if type(capacity) is not int or not 1<=capacity<=512:raise ValueError('Journal capacity1..512 required')
        self.capacity=capacity;self.decisions=OrderedDict();self.observations={};self.lock=RLock()
    def record(self,report):
        from .engine import AnalysisReport
        r=AnalysisReport.model_validate(report.model_dump() if hasattr(report,'model_dump') else report).model_dump(mode='json')
        generated=datetime.fromisoformat(r['as_of_utc'])
        if generated.tzinfo is None:raise ValueError('UTC-aware decision timestamp required')
        body={'version':VERSION,'analysis_id':r['analysis_id'],'generated_at':generated.isoformat(),
            'symbol':r['symbol'],'provider':r['provider'],'broker_symbol':r['broker_symbol'],'timeframe':r['timeframe'],
            'source_versions':r['source_versions'],'snapshot_id':r['snapshot_id'],'decision':r['final_decision'],
            'risk_veto':r['decision_reasons'],'entry_sl_tp':{'entry_zone':r['entry_zone'],'stop_loss':r['stop_loss'],
                'take_profit_1':r['take_profit_1'],'take_profit_2':r['take_profit_2']},
            'expires_at':(generated+timedelta(seconds=TIMEFRAMES[r['timeframe']])).isoformat(),
            'market_status':r['market_status'],'freshness':r['freshness'],
            'macro_coverage':r['information'].get('coverage_status','UNVERIFIED'),
            'future_observation_status':'NOT_OBSERVED','execution_permission':False}
        raw=canonical(body)
        if not body['analysis_id'] or len(raw)>64000:raise ValueError('Invalid bounded decision record')
        digest=sha256(raw.encode()).hexdigest()
        with self.lock:
            old=self.decisions.get(body['analysis_id'])
            if old is not None and old[1]!=digest:raise ValueError('Decision identity already frozen')
            self.decisions.setdefault(body['analysis_id'],(raw,digest))
            while len(self.decisions)>self.capacity:
                key,_=self.decisions.popitem(last=False);self.observations.pop(key,None)
        return {'analysis_id':body['analysis_id'],'decision_sha256':digest,'execution_permission':False}
    def observe(self,analysis_id,*,observed_at,price,source,as_of=None):
        now=as_of or datetime.now(timezone.utc)
        if observed_at.tzinfo is None or now.tzinfo is None or observed_at>now:raise ValueError('Known aware observation timestamp required')
        price=finite(price,'observed price')
        if price<=0 or not isinstance(source,str) or not 1<=len(source)<=128:raise ValueError('Explicit bounded observation required')
        with self.lock:
            if analysis_id not in self.decisions:raise ValueError('Decision missing or evicted')
            raw,digest=self.decisions[analysis_id];decision=json.loads(raw)
            if observed_at<=datetime.fromisoformat(decision['generated_at']):raise ValueError('Outcome cannot be generated with or before decision')
            rows=self.observations.setdefault(analysis_id,[])
            if len(rows)>=32:raise ValueError('Observation budget32 exceeded')
            body={'analysis_id':analysis_id,'decision_sha256':digest,'observed_at':observed_at.isoformat(),
                'price':price,'source':source,'status':'SIMULATED_OBSERVATION_NOT_BROKER_EXECUTION'}
            text=canonical(body);oid=sha256(text.encode()).hexdigest()
            if any(r['observation_id']==oid for r in rows):return json.loads(canonical(next(r for r in rows if r['observation_id']==oid)))
            if rows and observed_at<datetime.fromisoformat(rows[-1]['observed_at']):raise ValueError('Observation chronology cannot move backward')
            row={**body,'observation_id':oid};rows.append(row)
            return json.loads(canonical(row))
    def export(self,analysis_id):
        with self.lock:
            if analysis_id not in self.decisions:return None
            raw,digest=self.decisions[analysis_id]
            return {'decision':json.loads(raw),'decision_sha256':digest,
                'observations':json.loads(canonical(self.observations.get(analysis_id,[]))),
                'storage':'PROCESS_MEMORY_OPT_IN; restart_loses_records; bounded_oldest_eviction',
                'forward_validated':False}
