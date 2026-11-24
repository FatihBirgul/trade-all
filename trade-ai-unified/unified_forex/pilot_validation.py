"""Bounded untrusted pilot JSON validation. Hashes/redaction flags do not authenticate a broker."""
from datetime import datetime,timezone
from hashlib import sha256
from typing import Literal
from math import isfinite
from pydantic import BaseModel,ConfigDict,Field,model_validator
from .ingestion import bounded_json
from .pilot import FIELDS
from forex.contracts import canonical

VERSION='fx-pilot-evidence-check-v9-1'


class ProfitSample(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,allow_inf_nan=False)
    direction:Literal['BUY','SELL']
    lots:float=Field(gt=0)
    entry:float=Field(gt=0)
    stop:float=Field(gt=0)
    pnl_account_currency:float
    loss_sign_valid:bool


class MarginSample(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,allow_inf_nan=False)
    direction:Literal['BUY','SELL']
    lots:float=Field(gt=0)
    account_currency:str
    margin:float=Field(ge=0)
    basis:Literal['READONLY_BROKER_CALCULATION_NOT_ORDER_APPROVAL']


class SymbolEvidence(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    status:str
    contract:dict
    quote:dict
    schedule_trust:Literal['DECLARED','UNAVAILABLE']
    schedule_authenticated:Literal[False]
    missing_configuration:list[str]=Field(max_length=20)
    profit_samples:list[ProfitSample]=Field(max_length=2)
    margin_samples:list[MarginSample]=Field(max_length=2)
    margin_status:str|None=None
    swap_status:Literal['UNVERIFIED']
    @model_validator(mode='after')
    def whitelist(self):
        if set(self.contract)-set(FIELDS) or set(self.quote)-{'bid','ask','time','age_seconds'}:raise ValueError('Unknown/sensitive broker field')
        for key,value in self.contract.items():
            if isinstance(value,str) and (len(value)>128 or any(c in value for c in ('@','/','\\'))):raise ValueError('Unsafe broker text field')
            numeric=set(FIELDS)-{'broker_symbol','broker_server','account_currency','profit_currency','margin_currency','allowed_directions'}
            if value is not None and key in numeric and (type(value) not in (int,float) or not isfinite(value) or value<0):raise ValueError('Invalid pilot numeric contract field')
        for key in ('contract_size','tick_size','tick_value','point','volume_min','volume_max','volume_step'):
            value=self.contract.get(key)
            if self.status=='OK' and (type(value) not in (int,float) or value<=0):raise ValueError('Pilot financial contract incomplete')
        directions=self.contract.get('allowed_directions')
        if directions is not None and (not isinstance(directions,list) or len(directions)>2 or any(not isinstance(d,str) or d not in ('BUY','SELL') for d in directions)):raise ValueError('Invalid pilot direction permissions')
        bid,ask=self.quote.get('bid'),self.quote.get('ask')
        if bid is not None or ask is not None:
            if type(bid) not in (int,float) or type(ask) not in (int,float) or not 0<bid<=ask:raise ValueError('Invalid pilot quote sides')
        for sample in self.profit_samples:
            if sample.pnl_account_currency>=0 or not sample.loss_sign_valid:raise ValueError('Pilot stop sample is not a loss')
        return self


class PilotEvidence(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    version:Literal['fx-windows-pilot-v8-1']
    timestamp:datetime
    code_sha256:str=Field(pattern='^[a-f0-9]{64}$')
    execution_permission:Literal[False]
    mt5_validation:Literal['UNVERIFIED']
    terminal_connected:bool
    account_number_exported:Literal[False]
    symbols:dict[str,SymbolEvidence]
    recommended_next_test:str=Field(max_length=1000)
    status:str
    evidence_sha256:str=Field(pattern='^[a-f0-9]{64}$')
    @model_validator(mode='after')
    def symbol_set(self):
        if not set(self.symbols)<= {'XAUUSD','EURUSD','GBPUSD','USDJPY'} or len(self.symbols)>4:raise ValueError('Unexpected pilot symbols')
        if self.timestamp.tzinfo is None:raise ValueError('Aware collection timestamp required')
        if self.account_number_exported is not False or self.execution_permission is not False:raise ValueError('Pilot privacy/execution flags invalid')
        return self


def validate(payload,*,as_of=None,expected_code_sha256=None,max_age_seconds=86400):
    if isinstance(payload,(str,bytes)):
        if len(payload)>262144:raise ValueError('Pilot input exceeds256KB')
        raw=bounded_json(payload.decode('utf-8-sig') if isinstance(payload,bytes) else payload)
    else:raw=payload
    if len(canonical(raw))>262144:raise ValueError('Pilot input exceeds256KB')
    if not isinstance(raw,dict) or raw.get('execution_permission') is not False or raw.get('account_number_exported') is not False or type(raw.get('terminal_connected')) is not bool:
        raise ValueError('Explicit pilot privacy/execution booleans required')
    body={k:v for k,v in raw.items() if k!='evidence_sha256'}
    if raw.get('evidence_sha256')!=sha256(canonical(body).encode()).hexdigest():raise ValueError('Pilot checksum mismatch')
    e=PilotEvidence.model_validate(raw);now=as_of or datetime.now(timezone.utc)
    if now.tzinfo is None or type(max_age_seconds) is not int or not 1<=max_age_seconds<=86400:raise ValueError('Bounded pilot freshness policy required')
    age=(now-e.timestamp).total_seconds()
    if not 0<=age<=max_age_seconds:raise ValueError('Pilot evidence future or stale')
    if expected_code_sha256 is not None and e.code_sha256!=expected_code_sha256:raise ValueError('Pilot source code mismatch')
    stale=[]
    for symbol,row in e.symbols.items():
        stamp=row.quote.get('time')
        if stamp is not None and (type(stamp) not in (int,float) or not 0<=now.timestamp()-stamp<=120):stale.append(symbol)
    return {'version':VERSION,'schema_status':'VALID_UNTRUSTED_LOCAL_EVIDENCE','source_authenticated':False,
        'real_terminal_validated':False,'code_matched':expected_code_sha256 is not None,
        'stale_or_future_quotes':stale,'eligible_for_review':e.terminal_connected and not stale,
        'automatic_contract_override':False,'symbols':list(e.symbols)}
