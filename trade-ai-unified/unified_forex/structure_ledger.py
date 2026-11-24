"""Bounded causal FVG ledger. OHLC geometry only; no liquidity/order-size claims."""
from dataclasses import asdict
from hashlib import sha256
from collections import deque
import json
from threading import RLock
from forex.contracts import canonical
from market_ai.v2.market_data_contract import Candle,Instrument
from .pattern_lab import valid_frame

VERSION='fx-fvg-ledger-v9-1'
TERMINAL={'MITIGATED','INVALIDATED','EXPIRED'}


class StructureLedger:
    def __init__(self,*,capacity=128,expiry_bars=30):
        if type(capacity) is not int or not 1<=capacity<=256 or type(expiry_bars) is not int or not 1<=expiry_bars<=100:raise ValueError('Invalid ledger bounds')
        self.capacity=capacity;self.expiry=expiry_bars;self.events={};self.history=deque(maxlen=15)
        self.identity=None;self.timeframe=None;self.source=None;self.last_closed=None;self.processed=0
        self.lock=RLock()
    def consume(self,frame,tick):
        with self.lock:return self._consume(frame,tick)
    def _consume(self,frame,tick):
        if not valid_frame(frame,tick,1):raise ValueError('Closed valid structure snapshot required')
        if self.last_closed is not None and self.last_closed>frame.bars[-1].close_time_ms:
            raise ValueError('Structure ledger is ahead of snapshot; use an independent historical replay')
        instrument=asdict(frame.bars[0].instrument)
        source=frame.bars[0].source
        if self.source is not None and source!=self.source:raise ValueError('Ledger source mismatch')
        if self.identity is not None and (instrument!=self.identity or frame.timeframe!=self.timeframe):raise ValueError('Ledger identity mismatch')
        self.identity=instrument;self.timeframe=frame.timeframe;self.source=source
        recent={b.close_time_ms:b for b in self.history}
        for b in frame.bars:
            if self.last_closed is not None and b.close_time_ms<=self.last_closed:
                if b.close_time_ms in recent and b!=recent[b.close_time_ms]:raise ValueError('Historical revision requires a new ledger')
                continue
            if self.last_closed is not None and b.open_time_ms!=self.last_closed and (self.last_closed,b.open_time_ms) not in frame.permitted_gaps:
                raise ValueError('Ledger update gap requires closed-bar replay')
            self.processed+=1
            for event in self.events.values():
                if event['state'] in TERMINAL:continue
                age=self.processed-event['created_sequence'];up=event['direction']=='bullish'
                low,high=event['low'],event['high'];width=high-low
                # Closed beyond far edge invalidates before a mere wick fill.
                invalid=b.close<low-tick if up else b.close>high+tick
                full=b.low<=low if up else b.high>=high
                penetration=(high-b.low)/width if up else (b.high-low)/width
                state='INVALIDATED' if invalid else 'MITIGATED' if full else 'EXPIRED' if age>self.expiry else 'PARTIALLY_FILLED' if penetration>0 else event['state']
                if penetration>0: event['fill_fraction']=max(event['fill_fraction'],min(1,penetration))
                if state!=event['state']:
                    event['transitions'].append({'state':state,'known_at':b.close_time_ms})
                    event['state']=state
                if state in TERMINAL:event['terminal_at']=b.close_time_ms
                if penetration>0 and event['last_touch_sequence']<self.processed-1:
                    event['reentries']+=1
                if penetration>0:event['last_touch_sequence']=self.processed
            self.history.append(b)
            if len(self.history)==15:
                rows=list(self.history);a,m,c=rows[-3:]
                atr=sum(max(x.high-x.low,abs(x.high-y.close),abs(x.low-y.close)) for y,x in zip(rows,rows[1:]))/14
                up=c.low>a.high;down=c.high<a.low
                if up!=down:
                    low,high=(a.high,c.low) if up else (c.high,a.low)
                    if high-low>=max(tick,.1*atr) and abs(m.close-m.open)>=.5*atr and ((m.close>m.open) if up else (m.close<m.open)):
                        event_id=sha256(canonical([self.identity,self.timeframe,c.source,a.close_time_ms,c.close_time_ms,low,high,VERSION]).encode()).hexdigest()[:24]
                        self.events[event_id]=dict(event_id=event_id,kind='FVG',direction='bullish' if up else 'bearish',
                            low=low,high=high,origin_at=a.close_time_ms,first_known_at=c.close_time_ms,
                            confirmed_at=c.close_time_ms,state='CONFIRMED',terminal_at=None,fill_fraction=0.,
                            reentries=0,created_sequence=self.processed,last_touch_sequence=self.processed,
                            transitions=[{'state':'DETECTED','known_at':c.close_time_ms},{'state':'CONFIRMED','known_at':c.close_time_ms}],
                            algorithm_version=VERSION,ohlc_heuristic=True,directional_permission=False)
            self.last_closed=b.close_time_ms
            while len(self.events)>self.capacity:self.events.pop(next(iter(self.events)))
        return self.view()
    def view(self):
        with self.lock:return self._view()
    def _view(self):
        return json.loads(canonical({'version':VERSION,'events':list(self.events.values()),'last_closed':self.last_closed,
            'source':self.source,'identity':self.identity,'timeframe':self.timeframe,
            'scope':'bounded_observed_history','capacity':self.capacity,'restart':'restore_validated_checkpoint_or_replay_closed_bars',
            'eviction':'oldest_event_first; evicted history unavailable','source_authenticated':False}))
    def checkpoint(self):
        with self.lock:return self._checkpoint()
    def _checkpoint(self):
        body=dict(version=VERSION,capacity=self.capacity,expiry_bars=self.expiry,identity=self.identity,
            timeframe=self.timeframe,last_closed=self.last_closed,processed=self.processed,
            source=self.source,history=[asdict(b) for b in self.history],events=list(self.events.values()))
        raw=canonical(body)
        return {'body':json.loads(raw),'sha256':sha256(raw.encode()).hexdigest()}
    @classmethod
    def restore(cls,payload):
        if not isinstance(payload,dict) or set(payload)!={'body','sha256'}:raise ValueError('Invalid checkpoint envelope')
        raw=canonical(payload)
        if len(raw)>400000:raise ValueError('Checkpoint budget exceeded')
        body=payload['body']
        keys={'version','capacity','expiry_bars','identity','timeframe','source','last_closed','processed','history','events'}
        if not isinstance(body,dict) or set(body)!=keys:raise ValueError('Invalid checkpoint fields')
        if payload['sha256']!=sha256(canonical(body).encode()).hexdigest() or body['version']!=VERSION:raise ValueError('Checkpoint hash/version mismatch')
        obj=cls(capacity=body['capacity'],expiry_bars=body['expiry_bars'])
        if len(body['history'])>15 or len(body['events'])>obj.capacity:raise ValueError('Checkpoint cardinality invalid')
        if type(body['processed']) is not int or body['processed']<len(body['history']):raise ValueError('Invalid checkpoint sequence')
        body=json.loads(canonical(body))
        obj.identity=body['identity'];obj.timeframe=body['timeframe'];obj.source=body['source'];obj.last_closed=body['last_closed'];obj.processed=body['processed']
        for row in body['history']:
            b=Candle(**{**row,'instrument':Instrument(**row['instrument'])})
            if asdict(b.instrument)!=obj.identity or b.source!=obj.source or b.close_time_ms>obj.last_closed or b.is_final is not True:raise ValueError('Checkpoint candle identity/source/finality invalid')
            obj.history.append(b)
        if obj.history:
            from forex.core import TIMEFRAMES
            from market_ai.v2.market_data_contract import validate_series
            if obj.timeframe not in TIMEFRAMES or obj.last_closed!=obj.history[-1].close_time_ms:raise ValueError('Checkpoint timeframe/watermark invalid')
            gaps=tuple((a.close_time_ms,b.open_time_ms) for a,b in zip(obj.history,list(obj.history)[1:]) if a.close_time_ms!=b.open_time_ms)
            if not validate_series(tuple(obj.history),timeframe_ms=TIMEFRAMES[obj.timeframe]*1000,as_of_ms=obj.last_closed,
                max_age_ms=0,min_bars=1,permitted_gaps=gaps).ok:raise ValueError('Checkpoint candle chronology/OHLC invalid')
        elif body['events'] or obj.last_closed is not None or obj.processed:raise ValueError('Empty checkpoint state inconsistent')
        for e in body['events']:
            if len(e['transitions'])>104 or e['first_known_at']>obj.last_closed or e['state'] not in TERMINAL|{'CONFIRMED','PARTIALLY_FILLED'}:raise ValueError('Checkpoint event invalid')
            if e['event_id'] in obj.events or not 0<e['low']<e['high'] or not 0<=e['fill_fraction']<=1:raise ValueError('Checkpoint event geometry/identity invalid')
            if type(e['created_sequence']) is not int or not 1<=e['created_sequence']<=obj.processed or e['direction'] not in ('bullish','bearish'):raise ValueError('Checkpoint event sequence/direction invalid')
            if e['algorithm_version']!=VERSION or e['state']!=e['transitions'][-1]['state']:raise ValueError('Checkpoint transition version/state invalid')
            stamps=[x['known_at'] for x in e['transitions']]
            if stamps!=sorted(stamps) or any(not e['first_known_at']<=t<=obj.last_closed for t in stamps):raise ValueError('Checkpoint transition chronology invalid')
            obj.events[e['event_id']]=e
        return obj


class LedgerStore:
    """Provider-owned process scope, bounded; provider replacement starts fresh."""
    def __init__(self,capacity=24):
        if type(capacity) is not int or not 1<=capacity<=48:raise ValueError('Invalid ledger store bound')
        from collections import OrderedDict
        self.rows=OrderedDict();self.capacity=capacity;self.lock=RLock()
    def get(self,provider,symbol,timeframe):
        key=(id(provider),symbol,timeframe)
        with self.lock:
            if key not in self.rows:self.rows[key]=(provider,StructureLedger())
            self.rows.move_to_end(key)
            while len(self.rows)>self.capacity:self.rows.popitem(last=False)
            return self.rows[key][1]
