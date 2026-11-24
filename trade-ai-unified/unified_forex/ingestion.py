"""Explicit local read-only historical import. No API file paths or archive extraction."""
from pathlib import Path,PureWindowsPath,PurePosixPath
from hashlib import sha256
from datetime import datetime,timezone
from typing import Literal
import csv,io,json,os,re,stat
from pydantic import BaseModel,ConfigDict,Field,field_validator
from market_ai.v2.market_data_contract import Candle,Instrument
from market_ai.v2.technical_adapter import TIMEFRAME_MS
from .provenance import DatasetDeclaration,describe
from .research import HistoricalDataset

VERSION='fx-local-import-v8-1'
LIMIT=8_000_000


class ImportDeclaration(BaseModel):
    model_config=ConfigDict(extra='forbid',frozen=True,strict=True)
    dataset_id:str=Field(min_length=1,max_length=120)
    symbol:Literal['XAUUSD','EURUSD','GBPUSD','USDJPY']
    market:Literal['forex_spot','gold_spot','cfd']
    contract_type:Literal['spot','cfd']
    venue:str=Field(min_length=1,max_length=128)
    broker_symbol:str=Field(min_length=1,max_length=128)
    source:str=Field(min_length=1,max_length=128)
    timeframe:Literal['5m','15m','30m','1H','4H','1D']
    price_basis:Literal['bid'] # ask/mid require an explicit execution model first
    volume_kind:Literal['tick','unavailable']='unavailable'
    data_kind:Literal['synthetic','historical']='historical'
    data_version:str=Field(min_length=1,max_length=120)
    acquisition:DatasetDeclaration
    rules:dict
    rule_epochs:list[dict]=Field(default_factory=list,max_length=100)
    expected_raw_sha256:str|None=Field(default=None,pattern='^[a-f0-9]{64}$')
    require_descriptor_boundary:bool=False
    data_type:Literal['BID_OHLC','BID_ASK_OHLC']='BID_OHLC'


def _unique(pairs):
    result={}
    for k,v in pairs:
        if k in result:raise ValueError('Duplicate JSON key')
        result[k]=v
    return result


def _signature(info,*,cross_path=False,platform=None):
    fields=(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns)
    # CPython Windows stat/fstat can disagree on ctime for an unchanged file.
    # Same-handle comparisons retain ctime; only cross-API comparison omits it.
    return fields if cross_path and (platform or os.name)=='nt' else (*fields,info.st_ctime_ns)


def bounded_json(text):
    depth=0;quoted=False;escaped=False
    for c in text:
        if quoted:
            if escaped:escaped=False
            elif c=='\\':escaped=True
            elif c=='"':quoted=False
        elif c=='"':quoted=True
        elif c in '[{':
            depth+=1
            if depth>32:raise ValueError('JSON nesting exceeds32 levels')
        elif c in ']}':depth-=1
    try:return json.loads(text,object_pairs_hook=_unique,parse_constant=lambda s:(_ for _ in ()).throw(ValueError('Nonfinite JSON constant')))
    except (RecursionError,OverflowError):raise ValueError('Invalid bounded JSON') from None


def _read(root,relative_path,*,require_descriptor=False):
    text=os.fspath(relative_path);p=Path(text);windows=PureWindowsPath(text);posix=PurePosixPath(text)
    if p.is_absolute() or windows.root or windows.drive or posix.is_absolute() or '..' in windows.parts or '..' in posix.parts or ':' in text or not p.parts:
        raise ValueError('Relative import path inside configured root required')
    try:base=Path(root).resolve(strict=True)
    except OSError:raise ValueError('Configured import root unavailable') from None
    selected=base/p
    if any((base/Path(*p.parts[:i])).is_symlink() for i in range(1,len(p.parts)+1)):raise ValueError('Symlink imports forbidden')
    try:resolved=selected.resolve(strict=True)
    except OSError:raise ValueError('Import file unavailable') from None
    if not resolved.is_relative_to(base) or resolved.suffix.lower() not in ('.csv','.json','.parquet'):raise ValueError('Unsupported or escaped import path')
    descriptor_supported=os.open in os.supports_dir_fd and hasattr(os,'O_DIRECTORY') and hasattr(os,'O_NOFOLLOW')
    if require_descriptor and not descriptor_supported:raise ValueError('Descriptor boundary unavailable on this platform')
    descriptors=[]
    before=resolved.stat();parent_before=base.stat()
    try:
        if descriptor_supported:
            parent=os.open(base,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);descriptors.append(parent)
            if (os.fstat(parent).st_dev,os.fstat(parent).st_ino)!=(parent_before.st_dev,parent_before.st_ino):raise ValueError('Import root replaced')
            for part in p.parts[:-1]:
                parent=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent);descriptors.append(parent)
            fd=os.open(p.parts[-1],os.O_RDONLY|os.O_NOFOLLOW,dir_fd=parent)
        else:fd=os.open(resolved,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    except OSError:raise ValueError('Import descriptor refused') from None
    finally:
        for directory in reversed(descriptors):os.close(directory)
    with os.fdopen(fd,'rb') as handle:
        info=os.fstat(handle.fileno())
        if _signature(info,cross_path=True)!=_signature(before,cross_path=True):raise ValueError('Import file replaced before open')
        if not stat.S_ISREG(info.st_mode) or not 0<info.st_size<=LIMIT:raise ValueError('Regular bounded import file required')
        raw=handle.read(LIMIT+1)
        after=os.fstat(handle.fileno())
        if len(raw)>LIMIT or len(raw)!=info.st_size or _signature(after)!=_signature(info):raise ValueError('Import changed or exceeded budget')
        try:path_after=resolved.stat()
        except OSError:raise ValueError('Import path replaced during read') from None
        if _signature(path_after,cross_path=True)!=_signature(after,cross_path=True) or resolved.resolve()!=resolved:raise ValueError('Import path replaced during read')
    return resolved.suffix.lower(),raw


def import_file(root,relative_path,declaration,*,as_of=None):
    req=declaration if isinstance(declaration,ImportDeclaration) else ImportDeclaration.model_validate(declaration)
    extension,raw=_read(root,relative_path,require_descriptor=req.require_descriptor_boundary);raw_hash=sha256(raw).hexdigest()
    if req.expected_raw_sha256 is not None and req.expected_raw_sha256!=raw_hash:raise ValueError('Raw input hash mismatch')
    if extension=='.parquet':
        # Do not silently install an engine or decompress an untrusted columnar
        # file before enforcing decoded row/size bounds. Optional future adapter.
        raise ValueError('PARQUET_UNAVAILABLE: bounded decoder not installed; export CSV/JSON')
    text=raw.decode('utf-8-sig')
    if extension=='.json':
        rows=bounded_json(text)
        if not isinstance(rows,list):raise ValueError('JSON import requires a candle array')
    else:
        reader=csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or len(set(reader.fieldnames))!=len(reader.fieldnames):raise ValueError('Duplicate or missing CSV headers')
        rows=[]
        try:
            for i,row in enumerate(reader):
                if i>=2000:raise ValueError('Import exceeds2000 candles')
                rows.append(row)
        except csv.Error:raise ValueError('Malformed or oversized CSV field') from None
    if not rows or len(rows)>2000:raise ValueError('Import requires1..2000 candles')
    now=as_of or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError('Aware import as-of required')
    acquisition=req.acquisition.retrieved_at
    if acquisition>now:raise ValueError('Future acquisition declaration')
    instrument=Instrument(req.symbol,req.market,req.venue,req.price_basis,req.contract_type,req.symbol[-3:])
    bars=[];asks=[];duration=TIMEFRAME_MS[req.timeframe]
    required={'open_time_ms','close_time_ms','open','high','low','close','is_final','symbol','source','contract_type'}
    allowed=required|{'volume'}
    if req.data_type=='BID_ASK_OHLC':
        required|={'ask_open','ask_high','ask_low','ask_close','ask_source'};allowed|=required
    def stamp(v):
        if extension=='.csv':
            if not isinstance(v,str) or not re.fullmatch(r'[0-9]{1,16}',v):raise ValueError('Integer UTC milliseconds required')
            return int(v)
        if type(v) is not int:raise ValueError('Integer UTC milliseconds required')
        return v
    for row in rows:
        if not isinstance(row,dict) or not required<=row.keys() or set(row)-allowed:raise ValueError('Strict candle fields required')
        if (row['symbol'],row['source'],row['contract_type'])!=(req.symbol,req.source,req.contract_type):raise ValueError('Row identity/source/contract mismatch')
        start,end=stamp(row['open_time_ms']),stamp(row['close_time_ms'])
        final=row['is_final']=='true' if extension=='.csv' else row['is_final'] is True
        if not final or (extension=='.csv' and row['is_final']!='true'):raise ValueError('Explicit closed candle required')
        if start%duration or end-start!=duration or end>int(now.timestamp()*1000):raise ValueError('Timeframe, UTC alignment or future candle mismatch')
        from forex.core import finite
        if extension=='.json' and any(type(row[k]) not in (int,float) for k in ('open','high','low','close')):raise ValueError('JSON OHLC requires numeric scalars')
        prices=[finite(row[k],k) for k in ('open','high','low','close')]
        volume=None if req.volume_kind=='unavailable' else finite(row.get('volume'),'tick volume')
        if req.volume_kind=='unavailable' and row.get('volume') not in (None,''):raise ValueError('Undeclared volume data')
        bars.append(Candle(instrument,start,end,True,*prices,volume,req.volume_kind,req.source))
        if req.data_type=='BID_ASK_OHLC':
            if row['ask_source']!=req.source:raise ValueError('Ask/bid source mismatch')
            if extension=='.json' and any(type(row[k]) not in (int,float) for k in ('ask_open','ask_high','ask_low','ask_close')):raise ValueError('JSON ask OHLC requires numeric scalars')
            ask_prices=[finite(row['ask_'+k],'ask '+k) for k in ('open','high','low','close')]
            ask_instrument=Instrument(req.symbol,req.market,req.venue,'ask',req.contract_type,req.symbol[-3:])
            asks.append(Candle(ask_instrument,start,end,True,*ask_prices,volume,req.volume_kind,req.source))
    rules={**req.rules}
    expected={'broker_symbol':req.broker_symbol,'symbol':req.symbol,'broker_server':req.venue,
              'source':req.source,'market_type':req.market,'contract_type':req.contract_type,'price_kind':req.price_basis}
    if any(rules.get(k)!=v for k,v in expected.items()):raise ValueError('Broker rules identity mismatch')
    dataset=HistoricalDataset({req.timeframe:bars},rules,data_kind=req.data_kind,data_version=req.data_version,
        declaration=req.acquisition.model_dump(mode='json'),rule_epochs=req.rule_epochs,ask_frames={req.timeframe:asks} if asks else None)
    manifest=describe(dataset)
    return dataset,{'version':VERSION,'declared_dataset_id':req.dataset_id,'raw_file_sha256':raw_hash,
        'normalized_dataset_sha256':dataset.digest,'manifest':manifest,'read_only_import':True,
        'spread_history':'DECLARED_PAIRED_OHLC' if asks else 'UNAVAILABLE_MODEL_REQUIRED','parquet_status':'UNAVAILABLE_BOUNDED_DECODER_REQUIRED',
        'quality_status':'PASS_CLOSED_IDENTITY_OHLC_CHRONOLOGY_SESSION_GAPS'}
