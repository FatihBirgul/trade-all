"""Owned logical recipients/preferences; no device tokens, sender or provider.

Owner headers are trusted administrative Gateway assertions, not mobile identity.
Gateway overwrites them from its authenticated server-owned renewal family.
"""
import re
from typing import Literal
from pydantic import Field
from .api_models import Model
from .product_db import fingerprint
from .errors import V2Error
from . import domain_journal as domain
class NoticeCategories(Model):
    analysis: bool = Field(False,strict=True)
    source: bool = Field(False,strict=True)
    risk: bool = Field(False,strict=True)
    system: bool = Field(False,strict=True)
class NoticePreferencesWrite(Model):
    idempotency_key: str = Field(min_length=8,max_length=128,pattern=r'^[a-zA-Z0-9_.:-]+$')
    expected_revision: int = Field(ge=0,le=256,strict=True)
    enabled: bool = Field(strict=True)
    categories: NoticeCategories = Field(default_factory=NoticeCategories)
    recipient_action: Literal['keep','replace','revoke'] = 'keep'
class NoticePreferences(Model):
    portfolio_id: Literal['AUTO','MANUAL']
    data_mode: Literal['fixture','live']
    revision: int
    observed_at_ms: int
    enabled: bool
    categories: NoticeCategories
    recipient_id: str | None
    recipient_status: Literal['not_registered','active','revoked','expired']
    expires_at_ms: int | None
    push_status: Literal['NOT_CONFIGURED'] = 'NOT_CONFIGURED'
    device_credentials_supported: Literal[False] = False
    sender_running: Literal[False] = False
    state_semantics: Literal['read_observation_or_immutable_command_receipt'] = 'read_observation_or_immutable_command_receipt'
    scope: Literal['owned_logical_recipient_only'] = 'owned_logical_recipient_only'
class NotificationControls:
    def __init__(self,db):
        self.db=db
        with db.transaction() as c:
            c.execute('CREATE TABLE IF NOT EXISTS notification_controls(id TEXT PRIMARY KEY,owner TEXT NOT NULL,portfolio TEXT NOT NULL,revision INTEGER NOT NULL,body TEXT NOT NULL,body_hash TEXT NOT NULL,UNIQUE(owner,portfolio,revision))')
            for op in ('UPDATE','DELETE'):
                c.execute(f"CREATE TRIGGER IF NOT EXISTS notification_controls_{op.lower()} BEFORE {op} ON notification_controls BEGIN SELECT RAISE(ABORT,'immutable notification control'); END")
            domain.attach(c)
    def identity(self,owner,expires):
        if not isinstance(owner,str) or not re.fullmatch('[a-f0-9]{64}',owner) or type(expires) is not int or not self.db.clock()<expires<=self.db.clock()+31*86400000:
            raise V2Error('NOTIFICATION_OWNER_REQUIRED','Active trusted recipient assertion required',403)
    def latest(self,c,owner,account):
        row=c.execute('SELECT body,body_hash FROM notification_controls WHERE owner=? AND portfolio=? ORDER BY revision DESC LIMIT 1',(owner,account)).fetchone()
        value=self.db.decode(row) if row else None
        if value and (value['owner_ref']!=owner or value['portfolio_id']!=account):raise V2Error('STORAGE_CORRUPT','Recipient scope mismatch',503)
        return value
    def public(self,b,account):
        return NoticePreferences(portfolio_id=account,data_mode=self.db.mode,observed_at_ms=self.db.clock(),revision=b['revision'] if b else 0,enabled=b['enabled'] if b else False,categories=b['categories'] if b else NoticeCategories(),recipient_id=b['recipient_id'] if b else None,
            recipient_status='revoked' if b and b['revoked'] else 'not_registered' if not b or not b['generation'] else 'expired' if b['lease_expires_at_ms']<=self.db.clock() else 'active',expires_at_ms=b['lease_expires_at_ms'] if b and b['generation'] else None)
    def read(self,account,owner,expires):
        self.identity(owner,expires)
        with self.db.transaction() as c:return self.public(self.latest(c,owner,account),account)
    def write(self,account,owner,expires,request):
        self.identity(owner,expires)
        args={'portfolio_id':account,'preferences_digest':fingerprint(request.model_dump(exclude={'idempotency_key'}))};scope='notification:'+account+':'+owner
        with self.db.transaction() as c:
            prior=self.db.command(c,scope,request.idempotency_key,args)
            if prior is not None:return NoticePreferences.model_validate(prior)
            old=self.latest(c,owner,account);revision=old['revision'] if old else 0
            if request.expected_revision!=revision:raise V2Error('NOTIFICATION_REVISION_CONFLICT','Reload latest preference revision',409)
            if revision>=256:raise V2Error('NOTIFICATION_HISTORY_LIMIT','Preference revision budget reached',429)
            generation=old['generation'] if old else 0;revoked=old['revoked'] if old else False;lease=old['lease_expires_at_ms'] if old else 0
            if request.recipient_action=='replace' or not generation and request.enabled and request.recipient_action=='keep' and not revoked:
                generation+=1;revoked=False;lease=min(expires,self.db.clock()+86400000)
            if request.recipient_action=='revoke':revoked=True
            key=fingerprint({'owner':owner,'account':account,'revision':revision+1})
            record={'schema_version':1,'owner_ref':owner,'portfolio_id':account,'revision':revision+1,'enabled':request.enabled,'categories':request.categories.model_dump(),'generation':generation,'revoked':revoked,'lease_expires_at_ms':lease,'created_at_ms':self.db.clock(),'parent_id':old['id'] if old else None,'id':key,'data_mode':self.db.mode,
                'recipient_id':fingerprint({'owner':owner,'account':account,'generation':generation}) if generation else None}
            self.db.put(c,'notification_controls',key,record,owner=owner,portfolio=account,revision=revision+1)
            response=self.public(record,account).model_dump(mode='json');self.db.remember(c,scope,request.idempotency_key,args,response)
            return NoticePreferences.model_validate(response)
    def authorizer(self,*,owner,account,recipient_id,session_valid):
        """Explicit single-recipient fixture/adapter binding. No runtime installation.

        Future live sender must also prove provider/device credentials and check
        session revocation against its real authority; callback is not a claim of it.
        """
        def allowed(c,notice,now):
            b=self.latest(c,owner,account);details=notice.get('details',{})
            category='source' if details.get('change_kind') in ('source_unavailable','source_recovered') else {'scanner_error':'system','paper_event':'risk'}.get(notice.get('kind'),notice.get('kind'))
            notice_account=details.get('portfolio_id')
            if notice_account is None and details.get('tracking_id'):
                tracking=self.db.get(c,'analysis_tracking',details['tracking_id']);notice_account=tracking.get('portfolio_id') if tracking else None
            if notice_account is None and details.get('analysis_id'):
                analysis=self.db.get(c,'analyses',details['analysis_id'])
                notice_account=analysis.get('risk_portfolio') if analysis and analysis.get('analysis_id')==details['analysis_id'] and analysis.get('data_mode')==self.db.mode else None
            return bool(b and b['enabled'] and not b['revoked'] and b['lease_expires_at_ms']>now and b['recipient_id']==recipient_id and notice_account==account and b['categories'].get(category,False) and session_valid() is True)
        return allowed
