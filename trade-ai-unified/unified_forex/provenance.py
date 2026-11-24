"""Content identity and explicit historical trust; no automatic data downloads."""
from datetime import datetime,timezone
from dataclasses import asdict
from enum import Enum
from hashlib import sha256
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator
from forex.contracts import canonical
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

VERSION='fx-dataset-manifest-v7-1'


class Trust(str,Enum):
    SYNTHETIC_TEST='SYNTHETIC_TEST'
    DECLARED_HISTORICAL='DECLARED_HISTORICAL'
    SOURCE_VERIFIED='SOURCE_VERIFIED'
    POINT_IN_TIME_VERIFIED='POINT_IN_TIME_VERIFIED'
    UNAVAILABLE='UNAVAILABLE'


class RuleEpoch(BaseModel):
    model_config=ConfigDict(extra='forbid',frozen=True,allow_inf_nan=False)
    effective_from_ms:int=Field(ge=0,strict=True)
    effective_to_ms:int=Field(gt=0,strict=True)
    source:str=Field(min_length=1,max_length=200)
    rules:dict
    @model_validator(mode='after')
    def interval(self):
        if self.effective_from_ms>=self.effective_to_ms:raise ValueError('Empty rule epoch')
        if len(canonical(self.rules))>20000:raise ValueError('Rule epoch budget exceeded')
        return self


class DatasetDeclaration(BaseModel):
    model_config=ConfigDict(extra='forbid',frozen=True)
    retrieved_at:datetime
    timezone:str='UTC'
    license_declaration:str=Field(default='UNVERIFIED: no redistribution permission established',max_length=2000)
    usage_declaration:str=Field(default='local research only; source permission must be checked',max_length=2000)
    source_url:str|None=Field(default=None,max_length=2048)
    @field_validator('timezone')
    @classmethod
    def zone(cls,v):
        try:ZoneInfo(v)
        except (KeyError,ValueError):raise ValueError('IANA timezone required') from None
        return v
    @field_validator('source_url')
    @classmethod
    def public_url(cls,v):
        if v is None:return v
        p=urlsplit(v)
        if p.scheme!='https' or not p.hostname or p.username or p.password or p.query or p.fragment:raise ValueError('Public HTTPS source reference without credentials/query required')
        return v
    @field_validator('retrieved_at')
    @classmethod
    def utc(cls,v):
        if v.tzinfo is None:raise ValueError('Aware retrieval timestamp required')
        return v.astimezone(timezone.utc)


def normalize_epochs(rows):
    if not isinstance(rows,(list,tuple)) or len(rows)>100:raise ValueError('At most100 rule epochs')
    epochs=sorted((RuleEpoch.model_validate(r) for r in rows),key=lambda r:r.effective_from_ms)
    if any(a.effective_to_ms>b.effective_from_ms for a,b in zip(epochs,epochs[1:])):
        raise ValueError('Overlapping historical rule epochs')
    return [e.model_dump(mode='json') for e in epochs]


def rules_at(epochs,at_ms):
    matches=[e for e in epochs if e['effective_from_ms']<=at_ms<e['effective_to_ms']]
    if len(matches)!=1:raise ValueError('Point-in-time contract rules unavailable at requested timestamp')
    return matches[0]['rules']


def describe(dataset):
    """Trust cannot be raised by caller-supplied verification booleans/labels.

    SOURCE_VERIFIED and POINT_IN_TIME_VERIFIED are reserved for a future
    authenticated source verifier. Hash equality alone never grants either.
    """
    declaration=dataset.declaration
    start=min(rows[0].open_time_ms for rows in dataset.frames.values());end=max(rows[-1].close_time_ms for rows in dataset.frames.values())
    cursor=start
    for e in dataset.rule_epochs:
        if e['effective_from_ms']<=cursor<e['effective_to_ms']:cursor=e['effective_to_ms']
    frames={tf:dict(timeframe=tf,candle_count=len(rows),start_ms=rows[0].open_time_ms,
                    end_ms=rows[-1].close_time_ms,price_basis=dataset.identity.price_kind,
                    volume_kind=sorted({b.volume_kind for b in rows}),
                    sha256=sha256(canonical([asdict(b) for b in rows]).encode()).hexdigest())
            for tf,rows in dataset.frames.items()}
    payload=dict(version=VERSION,dataset_id=dataset.digest,source=dataset.source,
        venue=dataset.identity.venue,symbol=dataset.identity.symbol,
        broker_symbol=dataset.metadata().get('broker_symbol'),contract_type=dataset.identity.contract_type,
        data_version=dataset.data_version,frames=frames,**declaration,
        trust=Trust.SYNTHETIC_TEST.value if dataset.data_kind=='synthetic' else Trust.DECLARED_HISTORICAL.value,
        source_authenticated=False,point_in_time_authenticated=False,
        historical_rule_status='DECLARED_EPOCHS' if dataset.rule_epochs else 'STATIC_RULES_HISTORY_UNKNOWN',
        declared_epoch_coverage='FULL' if cursor>=end else 'PARTIAL' if dataset.rule_epochs else 'UNAVAILABLE',
        rule_epochs=[{**e,'rules_sha256':sha256(canonical(e['rules']).encode()).hexdigest()} for e in dataset.rule_epochs],
        quality_checks=['closed_candles','strict_identity','monotonic_no_duplicate','explicit_bid_basis','bounded_session_gaps'],
        limitations=['Hashes bind content, not source authenticity or license rights.','Declared historical rules are not authenticated broker archives.'])
    from .data_sides import describe as side_contract
    payload['price_side_evidence']=side_contract(dataset)
    payload['manifest_sha256']=sha256(canonical(payload).encode()).hexdigest()
    return payload
