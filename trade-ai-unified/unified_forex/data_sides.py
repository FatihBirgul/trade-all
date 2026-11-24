"""Explicit historical side capabilities; content validation never authenticates a broker."""
from dataclasses import asdict
from hashlib import sha256
from forex.contracts import canonical
from market_ai.v2.market_data_contract import validate_series
from market_ai.v2.technical_adapter import TIMEFRAME_MS
from pydantic import BaseModel,ConfigDict,Field,model_validator

VERSION='fx-price-sides-v9-1'
CAPABILITIES={
 'BID_OHLC':{'analysis':True,'replay':'MODELLED_SPREAD_REQUIRED'},
 'ASK_OHLC':{'analysis':False,'replay':'UNAVAILABLE_NO_BID'},
 'BID_ASK_OHLC':{'analysis':True,'replay':'DECLARED_PAIRED_SIDE_OHLC'},
 'QUOTE_TICKS':{'analysis':False,'replay':'UNAVAILABLE_TICK_EXECUTOR_NOT_IMPLEMENTED'},
 'MID_ONLY':{'analysis':False,'replay':'UNAVAILABLE_EXECUTION_SIDE_UNKNOWN'},
 'MODELLED_SPREAD':{'analysis':False,'replay':'ASSUMPTION_ONLY'},
 'EXECUTION_COST_ARCHIVE':{'analysis':False,'replay':'REQUIRES_RULE_AND_PRICE_BINDING'}}
REPLAY_MODES={'VERIFIED_BID_ASK_REPLAY':'UNAVAILABLE_AUTHENTICATED_PRICE_AND_PIT_RULE_EVIDENCE_REQUIRED',
              'BID_ONLY_MODELLED_SPREAD':'AVAILABLE_DECLARED_ASSUMPTIONS',
              'DECLARED_COST_REPLAY':'AVAILABLE_PAIRED_OHLC_WITH_DECLARED_COSTS',
              'SYNTHETIC_MECHANICAL_TEST':'AVAILABLE_TEST_EVIDENCE_ONLY'}


def paired_frames(bid_frames,ask_frames):
    if set(bid_frames)!=set(ask_frames):raise ValueError('Paired timeframe coverage mismatch')
    for tf,bids in bid_frames.items():
        asks=ask_frames[tf]
        if len(bids)!=len(asks):raise ValueError('Paired candle count mismatch')
        q=validate_series(asks,timeframe_ms=TIMEFRAME_MS[tf],as_of_ms=asks[-1].close_time_ms,max_age_ms=0,
            permitted_gaps=tuple((a.close_time_ms,b.open_time_ms) for a,b in zip(asks,asks[1:]) if a.close_time_ms!=b.open_time_ms))
        if not q.ok:raise ValueError('Invalid closed ask series')
        for bid,ask in zip(bids,asks):
            bi=asdict(bid.instrument);ai=asdict(ask.instrument)
            if bi.pop('price_kind')!='bid' or ai.pop('price_kind')!='ask' or bi!=ai or bid.source!=ask.source:
                raise ValueError('Paired side identity/source mismatch')
            if bid.volume_kind!=ask.volume_kind:raise ValueError('Paired volume kind mismatch')
            if (bid.open_time_ms,bid.close_time_ms)!=(ask.open_time_ms,ask.close_time_ms):raise ValueError('Paired side timestamp mismatch')
            if any(getattr(ask,k)<getattr(bid,k) for k in ('open','high','low','close')):raise ValueError('Negative spread or crossed OHLC sides')
    return True


class QuoteTick(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,allow_inf_nan=False,frozen=True)
    time_ms:int=Field(ge=0)
    symbol:str=Field(min_length=1,max_length=32)
    venue:str=Field(min_length=1,max_length=128)
    contract_type:str
    source:str=Field(min_length=1,max_length=128)
    bid:float=Field(gt=0)
    ask:float=Field(gt=0)
    @model_validator(mode='after')
    def sides(self):
        if self.ask<self.bid:raise ValueError('Negative quote spread')
        return self


def quote_archive(rows,*,symbol,venue,contract_type,source,as_of_ms):
    if not isinstance(rows,(list,tuple)) or not 1<=len(rows)<=2000 or type(as_of_ms) is not int:raise ValueError('Bounded quote archive required')
    owned=tuple(QuoteTick.model_validate(row) for row in rows)
    for i,row in enumerate(owned):
        if (row.symbol,row.venue,row.contract_type,row.source)!=(symbol,venue,contract_type,source):raise ValueError('Quote archive identity mismatch')
        if row.time_ms>as_of_ms or (i and row.time_ms<=owned[i-1].time_ms):raise ValueError('Future, duplicate or nonchronological quote')
    raw=canonical([row.model_dump() for row in owned])
    return {'type':'QUOTE_TICKS','sha256':sha256(raw.encode()).hexdigest(),'count':len(owned),
        'capability':CAPABILITIES['QUOTE_TICKS'],'source_authenticated':False,'execution_replay_available':False}


def describe(dataset):
    paired=bool(dataset.ask_frames)
    return {'version':VERSION,'data_type':'BID_ASK_OHLC' if paired else 'BID_OHLC',
        'spread_evidence':'DECLARED_OBSERVED_SIDE_BARS' if paired else 'MODELLED_SPREAD',
        'historical_execution_verified':False,'cost_evidence':'DECLARED','source_authenticated':False,
        'capability':CAPABILITIES['BID_ASK_OHLC' if paired else 'BID_OHLC'],
        'ask_sha256':sha256(canonical({tf:[asdict(b) for b in bars] for tf,bars in dataset.ask_frames.items()}).encode()).hexdigest() if paired else None,
        'limitation':'Paired OHLC extrema are not synchronized ticks; intrabar path/order remains unknown.'}
