"""Explicit opt-in transport foundation; never installed/started by Runtime.

No network/provider/recipient credentials here. No adapter means no writes. A real
adapter must enforce the passed timeout and prove provider idempotency separately.
Acceptance is not device delivery; immutable original outbox rows stay unchanged.
"""
from dataclasses import dataclass
import re
from uuid import uuid4
from .product_db import fingerprint,encode
from . import domain_journal as domain

@dataclass(frozen=True)
class AdapterResult:
    outcome:str
    receipt_ref:str=''
    error_code:str=''
    def __post_init__(self):
        if self.outcome not in ('accepted','retryable','permanent') or not isinstance(self.receipt_ref,str) or not re.fullmatch('[A-Za-z0-9_.:-]{0,128}',self.receipt_ref) or (self.outcome=='accepted' and not self.receipt_ref) or self.error_code not in ('','adapter_timeout','adapter_error'):
            raise ValueError('Only sanitized acceptance/failure receipts are supported; no delivered state')

class NotificationDispatcher:
    def __init__(self,db,adapter=None,*,clock=None,authorization=None):
        self.db,self.adapter,self.clock=db,adapter,clock or db.clock
        self.authorization=authorization
        if adapter is None:return
        if db.mode!='fixture':raise ValueError('Live transport unavailable without trusted provider/device integration')
        if getattr(adapter,'mode',None)!=db.mode or getattr(adapter,'supports_idempotency',False) is not True or not callable(getattr(adapter,'send',None)):
            raise ValueError('Same-mode idempotent adapter with bounded send required')
        if not callable(authorization):raise ValueError('Explicit recipient/account/session authorization required')
        with db.transaction() as c:
            c.execute('CREATE TABLE IF NOT EXISTS notification_delivery_state(id TEXT PRIMARY KEY,outbox_n INTEGER NOT NULL UNIQUE,body TEXT NOT NULL,body_hash TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS notification_delivery_attempts(id TEXT PRIMARY KEY,body TEXT NOT NULL,body_hash TEXT NOT NULL)')
            c.execute("CREATE INDEX IF NOT EXISTS delivery_due ON notification_delivery_state(json_extract(body,'$.status'),json_extract(body,'$.ready_at_ms'))")
            for op in ('UPDATE','DELETE'):
                c.execute(f"CREATE TRIGGER IF NOT EXISTS notification_delivery_attempts_{op.lower()} BEFORE {op} ON notification_delivery_attempts BEGIN SELECT RAISE(ABORT,'immutable delivery evidence'); END")
            c.execute("CREATE INDEX IF NOT EXISTS delivery_started_time ON notification_delivery_attempts(json_extract(body,'$.time_ms')) WHERE json_extract(body,'$.outcome')='started'")
            domain.attach(c)

    def _save(self,c,state):
        c.execute('UPDATE notification_delivery_state SET body=?,body_hash=? WHERE id=?',(encode(state),fingerprint(state),state['notification_id']))

    def _record(self,c,state,outcome,*,receipt_ref='',error_code=''):
        body={'schema_version':1,'notification_id':state['notification_id'],'outbox_hash':state['outbox_hash'],'attempt':state['attempt'],
            'outcome':outcome,'time_ms':self.clock(),'data_mode':self.db.mode,'receipt_ref':receipt_ref,'error_code':error_code,
            'idempotency_key':state['idempotency_key']}
        key=fingerprint({'notification':body['notification_id'],'attempt':body['attempt'],'outcome':outcome})
        self.db.put(c,'notification_delivery_attempts',key,body)

    def _claim(self,limit):
        now=self.clock();claimed=[];skips={'expired':0,'preference_blocked':0,'invalid_source':0,'rate_limited':0}
        with self.db.transaction() as c:
            domain.begin(c,effective_at=now,source={'control':'notification_delivery_claim'})
            due=[self.db.decode(r) for r in c.execute("SELECT body,body_hash FROM notification_delivery_state WHERE json_extract(body,'$.status') IN ('pending','leased') AND json_extract(body,'$.ready_at_ms')<=? ORDER BY json_extract(body,'$.ready_at_ms'),id LIMIT ?",(now,limit))]
            candidates=[(s,self.db.get(c,'notifications',s['notification_id'])) for s in due]
            remaining=limit-len(candidates)
            if remaining:
                for n,key,raw,h in c.execute('SELECT rowid,id,body,body_hash FROM notifications WHERE rowid>(SELECT COALESCE(MAX(outbox_n),0) FROM notification_delivery_state) ORDER BY rowid LIMIT ?',(remaining,)):
                    notification=self.db.decode((raw,h))
                    state={'schema_version':1,'notification_id':key,'outbox_n':n,'outbox_hash':fingerprint(notification),'attempt':0,'status':'pending','ready_at_ms':now,'lease_id':None,'idempotency_key':'notification:'+key,'data_mode':self.db.mode}
                    self.db.put(c,'notification_delivery_state',key,state,outbox_n=n);candidates.append((state,notification))
            for state,notification in candidates:
                if notification is None or fingerprint(notification)!=state['outbox_hash'] or notification['data_mode']!=self.db.mode:raise ValueError('Immutable outbox source mismatch')
                details=notification['details'];expires=details.get('expires_at_ms',notification['created_at_ms']+900000)
                if type(expires) is not int:
                    state['status']='invalid_source';self._record(c,state,'invalid_source');self._save(c,state);skips['invalid_source']+=1;continue
                if expires<=now:
                    state['status']='expired';self._record(c,state,'expired');self._save(c,state);skips['expired']+=1;continue
                if details.get('change_kind') in ('source_unavailable','source_recovered'):
                    follow=self.db.get(c,'analysis_tracking',details.get('tracking_id'))
                    if not follow or not follow.get('notify_source_changes',False) or not follow['enabled']:
                        state['status']='preference_blocked';self._record(c,state,'preference_blocked');self._save(c,state);skips['preference_blocked']+=1;continue
                if self.authorization(c,notification,now) is not True:
                    state['status']='preference_blocked';self._record(c,state,'preference_blocked');self._save(c,state);skips['preference_blocked']+=1;continue
                recent=c.execute("SELECT COUNT(*) FROM (SELECT 1 FROM notification_delivery_attempts WHERE json_extract(body,'$.outcome')='started' AND json_extract(body,'$.time_ms')>? LIMIT 60)",(now-60000,)).fetchone()[0]
                if recent>=60:
                    state.update(status='pending',ready_at_ms=now+60000,lease_id=None);self._save(c,state);skips['rate_limited']+=1;continue
                if state['status']=='leased':self._record(c,state,'lease_expired',error_code='adapter_timeout')
                if state['attempt']>=5:
                    state['status']='exhausted';self._save(c,state);continue
                state.update(attempt=state['attempt']+1,status='leased',ready_at_ms=now+30000,lease_id=uuid4().hex)
                self._save(c,state);self._record(c,state,'started');claimed.append((dict(state),notification))
        return claimed,skips

    def _finish(self,state,result):
        with self.db.transaction() as c:
            current=self.db.get(c,'notification_delivery_state',state['notification_id'])
            if current['status']!='leased' or current['lease_id']!=state['lease_id']:return False
            domain.begin(c,effective_at=self.clock(),source={'control':'notification_delivery_result'})
            self._record(c,current,result.outcome,receipt_ref=result.receipt_ref,error_code=result.error_code)
            status=result.outcome
            if status=='retryable':status='exhausted' if current['attempt']>=5 else 'pending'
            current.update(status=status,lease_id=None,ready_at_ms=self.clock()+min(5000*2**(current['attempt']-1),300000))
            self._save(c,current);return True

    def _recheck(self,state,notification):
        with self.db.transaction() as c:
            current=self.db.get(c,'notification_delivery_state',state['notification_id'])
            if not current or current['lease_id']!=state['lease_id'] or current['status']!='leased':return 'lease_lost'
            details=notification['details'];expires=details.get('expires_at_ms',notification['created_at_ms']+900000)
            status='expired' if expires<=self.clock() else 'preference_blocked'
            follow=self.db.get(c,'analysis_tracking',details.get('tracking_id')) if details.get('change_kind') in ('source_unavailable','source_recovered') else None
            follow_allowed=details.get('change_kind') not in ('source_unavailable','source_recovered') or bool(follow and follow['enabled'] and follow.get('notify_source_changes'))
            if status!='expired' and follow_allowed and self.authorization(c,notification,self.clock()) is True:return 'allowed'
            domain.begin(c,effective_at=self.clock(),source={'control':'notification_delivery_authorization'})
            current.update(status=status,lease_id=None)
            self._record(c,current,status);self._save(c,current)
            return status

    def tick(self,*,limit=10):
        if type(limit) is not int or not 1<=limit<=10:raise ValueError('Bounded batch1..10 required')
        report={'status':'not_configured' if self.adapter is None else 'completed','accepted':0,'retryable':0,'permanent':0,'expired':0,'preference_blocked':0,'invalid_source':0,'device_delivery':'UNVERIFIED','rate_limited':0,'lease_lost':0}
        if self.adapter is None:return report
        claimed,skips=self._claim(limit);report.update(skips)
        for state,notification in claimed:
            permission=self._recheck(state,notification)
            if permission!='allowed':
                report[permission]+=1;continue
            # No SQLite lock is held while an adapter performs bounded I/O.
            try:
                result=self.adapter.send(notification,idempotency_key=state['idempotency_key'],timeout_seconds=5)
                if not isinstance(result,AdapterResult):raise ValueError('Invalid adapter result')
            except TimeoutError:result=AdapterResult('retryable',error_code='adapter_timeout')
            except Exception:result=AdapterResult('retryable',error_code='adapter_error')
            if self._finish(state,result):report[result.outcome]+=1
        return report
