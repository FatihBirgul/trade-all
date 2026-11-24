"""Standalone immutable dataset evidence; checksums are not authenticity proofs."""
from dataclasses import dataclass
from hashlib import sha256
import json
import re
from itertools import islice
from urllib.parse import urlsplit
from .decision_record import _canonical


def digest(x):return sha256(_canonical(x).encode()).hexdigest()
def stamp(x):return type(x) is int and 0<=x<=10**16

def reference(x):
    if not isinstance(x,str) or len(x)>2048 or any(ord(c)<32 for c in x):return False
    if not x:return True
    u=urlsplit(x)
    return u.scheme=='https' and bool(u.hostname) and not (u.username or u.password or u.query or u.fragment)

def hash_value(x):return isinstance(x,str) and re.fullmatch('[a-f0-9]{64}',x) is not None

@dataclass(frozen=True,init=False)
class Manifest:
    body_json:str
    manifest_id:str
    def __init__(self,body):
        keys={'schema_version','dataset_digest','source','venue','captured_at_ms','normalization',
              'license_status','license_reference','rules','costs','raw_payload_sha256'}
        if (not isinstance(body,dict) or set(body)!=keys or type(body['schema_version']) is not int or body['schema_version']!=1
                or not hash_value(body['dataset_digest']) or not stamp(body['captured_at_ms'])
                or any(not isinstance(body[k],str) or not 1<=len(body[k])<=128 for k in ('source','venue','normalization'))
                or body['license_status'] not in ('UNVERIFIED','REVIEWED_DECLARATION') or not reference(body['license_reference'])
                or (body['license_status']=='REVIEWED_DECLARATION' and not body['license_reference'])
                or (body['raw_payload_sha256'] is not None and not hash_value(body['raw_payload_sha256']))
                or not isinstance(body['rules'],list) or not 1<=len(body['rules'])<=32):
            raise ValueError('Invalid manifest schema or evidence reference')
        fields={'kind','effective_from_ms','effective_to_ms','observed_at_ms','rules_digest','evidence_sha256','reference'}
        for r in body['rules']:
            if (not isinstance(r,dict) or set(r)!=fields or r['kind'] not in ('CURRENT_SNAPSHOT','ARCHIVED_REVIEWED')
                    or not all(stamp(r[k]) for k in ('effective_from_ms','effective_to_ms','observed_at_ms'))
                    or r['effective_to_ms']<=r['effective_from_ms'] or not hash_value(r['rules_digest'])
                    or not reference(r['reference']) or (r['evidence_sha256'] is not None and not hash_value(r['evidence_sha256']))
                    or (r['kind']=='ARCHIVED_REVIEWED' and (not r['reference'] or r['evidence_sha256'] is None))
                    or (r['kind']=='CURRENT_SNAPSHOT' and r['effective_from_ms']<r['observed_at_ms'])):
                raise ValueError('Invalid point-in-time rule evidence')
        from .research import number
        costs=body['costs']
        if (not isinstance(costs,dict) or set(costs)!={'fee_bps','spread_bps','slippage_bps','basis'}
                or costs['basis']!='SIMULATION_ASSUMPTION' or any(not 0<=number(costs[k])<=100 for k in costs if k!='basis')):
            raise ValueError('Explicit bounded simulation costs required')
        raw=_canonical(body)
        object.__setattr__(self,'body_json',raw);object.__setattr__(self,'manifest_id',sha256(raw.encode()).hexdigest())
    def body(self):return json.loads(self.body_json)


def verify_manifest(dataset,manifest,*,start_ms=None,end_ms=None,costs=None):
    checks=[]
    def check(ok,code,status='INCOMPLETE'):
        checks.append({'code':code,'status':'PASS' if ok else status})
    if manifest is None:
        return {'status':'INCOMPLETE','checks':[{'code':'manifest_missing','status':'INCOMPLETE'}],'market_performance_verified':False}
    if not isinstance(manifest,Manifest):raise ValueError('Validated manifest required')
    body=manifest.body();bars=dataset.frames['1m']
    start=bars[0].open_time_ms if start_ms is None else start_ms
    end=bars[-1].close_time_ms if end_ms is None else end_ms
    if not stamp(start) or not stamp(end) or not bars[0].open_time_ms<=start<end<=bars[-1].close_time_ms:
        raise ValueError('Evidence window outside dataset')
    check(body['dataset_digest']==dataset.digest,'dataset_hash','MISMATCH')
    check(body['source']==dataset.source and body['venue']==dataset.identity.venue,'source_identity','MISMATCH')
    check(body['captured_at_ms']>=end,'capture_after_closed_window','MISMATCH')
    check(body['license_status']=='REVIEWED_DECLARATION','license_review_missing')
    rules=sorted(body['rules'],key=lambda r:r['effective_from_ms']);cursor=start
    expected=digest(dict(dataset.rules))
    for r in rules:
        overlaps=r['effective_from_ms']<end and r['effective_to_ms']>start
        if overlaps:check(r['rules_digest']==expected,'rules_hash','MISMATCH')
        if r['kind']=='ARCHIVED_REVIEWED' and r['rules_digest']==expected and r['effective_from_ms']<=cursor<r['effective_to_ms']:
            cursor=max(cursor,r['effective_to_ms'])
    check(cursor>=end,'historical_rules_missing')
    check(False,'historical_fee_spread_slippage_unverified')
    if costs is not None:
        from .research import number
        check(all(number(costs[k])==number(body['costs'][k]) for k in ('fee_bps','spread_bps','slippage_bps')),'cost_assumption_binding','MISMATCH')
    order=('PASS','INCOMPLETE','MISMATCH','CORRUPT','ERROR')
    return {'status':max((c['status'] for c in checks),key=order.index),'manifest_id':manifest.manifest_id,
            'checks':checks,'market_performance_verified':False,
            'limitations':['Review declarations and SHA256 references are not authenticated evidence or legal certification.',
                           'Uniform archived instrument rules only; changing rules are not silently substituted.',
                           'Simulation costs are assumptions, not a verified historical broker schedule.']}


def capture_history(provider,symbol,start_ms,end_ms,*,as_of_ms):
    """At most four public pages. No output, partial persistence or fallback."""
    if (not all(stamp(x) for x in (start_ms,end_ms,as_of_ms)) or start_ms%60000 or end_ms%60000
            or not 250<= (end_ms-start_ms)//60000 <=1200 or end_ms>as_of_ms//60000*60000
            or symbol not in ('BTCUSDT','ETHUSDT','SOLUSDT')
            or (provider.name,provider.venue,provider.mode,provider.source_name)!=('binance_public_spot','binance','live','binance_spot')):
        raise ValueError('Bounded closed Binance spot window required')
    rules=provider.rules(symbol);bars=[]
    for start in range(start_ms,end_ms,300*60000):
        stop=min(start+300*60000,end_ms)
        page=tuple(islice(provider.candle_window(symbol,start,stop),301))
        if len(page)!=(stop-start)//60000 or any(b.open_time_ms!=start+i*60000 or b.close_time_ms!=start+(i+1)*60000 for i,b in enumerate(page)):
            raise ValueError('Incomplete or out-of-window historical page')
        bars.extend(page)
    from .research import HistoricalDataset
    d=HistoricalDataset({'1m':bars},rules,data_kind='historical',data_version='binance-normalized-capture-1')
    if d.identity.symbol!=symbol or d.identity.venue!='binance' or d.source!='binance_spot':
        raise ValueError('Historical source identity mismatch')
    m=Manifest({'schema_version':1,'dataset_digest':d.digest,'source':d.source,'venue':d.identity.venue,
        'captured_at_ms':as_of_ms,'normalization':'binance_spot_kline_exclusive_close_v1',
        'license_status':'UNVERIFIED','license_reference':'https://developers.binance.com/docs/binance-spot-api-docs',
        'rules':[{'kind':'CURRENT_SNAPSHOT','effective_from_ms':as_of_ms,'effective_to_ms':10**16,
                  'observed_at_ms':as_of_ms,'rules_digest':digest(dict(d.rules)),'evidence_sha256':None,'reference':''}],
        'costs':{'fee_bps':'5','spread_bps':'2','slippage_bps':'1','basis':'SIMULATION_ASSUMPTION'},'raw_payload_sha256':None})
    return d,m


def write_capture(dataset,manifest,dataset_path,manifest_path):
    """Exclusive new JSON pair; remove only files this call created on failure."""
    from pathlib import Path
    from dataclasses import asdict
    targets=(Path(dataset_path),Path(manifest_path))
    if targets[0].resolve()==targets[1].resolve() or any(p.suffix.lower()!='.json' or p.exists() for p in targets):
        raise FileExistsError('Two distinct new JSON outputs required')
    if verify_manifest(dataset,manifest)['status'] in ('MISMATCH','CORRUPT','ERROR'):
        raise ValueError('Capture evidence mismatch')
    frames={}
    for tf,bars in dataset.frames.items():
        rows=[]
        for b in bars:
            r=asdict(b);r.pop('instrument');r.pop('source');rows.append(r)
        frames[tf]=rows
    document={'schema_version':1,'data_kind':dataset.data_kind,'data_version':dataset.data_version,
              'instrument':asdict(dataset.identity),'source':dataset.source,'rules':dict(dataset.rules),'frames':frames}
    owned=[]
    try:
        for path,body in zip(targets,(document,manifest.body())):
            with path.open('x',encoding='utf-8') as f:
                owned.append(path);f.write(_canonical(body)+'\n')
    except BaseException:
        for path in owned:path.unlink(missing_ok=True)
        raise


def load_manifest(path):
    from pathlib import Path
    with Path(path).open('r',encoding='utf-8') as f:raw=f.read(262145)
    if len(raw)>262144:raise ValueError('Manifest budget exceeded')
    def unique(pairs):
        result={}
        for k,v in pairs:
            if k in result:raise ValueError('Duplicate manifest JSON key')
            result[k]=v
        return result
    return Manifest(json.loads(raw,object_pairs_hook=unique))
