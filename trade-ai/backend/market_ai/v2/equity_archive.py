"""Read-only, frozen-prefix archive windows. Cursors are checksummed, not signed.

Every returned point is an existing immutable observation. Min/max sampling keeps
eligible sequence endpoints and both extrema in each equal-count bucket. It does
not reconstruct prices, compute new accounting or imply continuous drawdown.
"""
import base64
from contextlib import closing
from decimal import Decimal,Context,localcontext,ROUND_HALF_EVEN
import json
import sqlite3
from typing import Literal
from .api_models import Model
from .equity_history import EquityPoint
from .errors import V2Error
from .product_db import encode,fingerprint

MAX_SCAN_ROWS=10000
MAX_SCANNED_BYTES=16*1024*1024
MAX_RESPONSE_BYTES=2*1024*1024

class EquityWindowResponse(Model):
    portfolio_id: Literal['AUTO','MANUAL']
    data_mode: Literal['fixture','live']
    points: list[EquityPoint]
    watermark: int
    request_cursor: str
    next_cursor: str | None
    has_more: bool
    sampling: Literal['raw','minmax']
    status: Literal['complete','incomplete_budget']
    observations_scanned: int
    excluded_incomplete: int
    ordering: Literal['account_sequence'] = 'account_sequence'
    note: str = 'Actual observations only. Frozen account prefix; sequence order, inclusive UTC recorded-time filter. Min/max preserves eligible endpoints and bucket extrema, not every turn or continuous drawdown. Cursor checksum is not authorization or a signature.'

def _pack(state):
    return base64.urlsafe_b64encode(encode({'state':state,'checksum':fingerprint(state)}).encode()).decode().rstrip('=')

def _unpack(cursor):
    try:
        if len(cursor)>1600:raise ValueError()
        data=json.loads(base64.b64decode(cursor+'='*(-len(cursor)%4),altchars=b'-_',validate=True))
        state=data['state']
        if set(data)!={'state','checksum'} or data['checksum']!=fingerprint(state):raise ValueError()
        if set(state)!={'version','account','mode','from','to','watermark','before','anchor'} or (type(state['version']) is not int or state['version']!=1):raise ValueError()
        if any(type(state[k]) is not int or not 0<=state[k]<=9223372036854775807 for k in ('from','to','watermark','before')):raise ValueError()
        if not 0<state['before']<=state['watermark']+1 or not isinstance(state['anchor'],str):raise ValueError()
        return state
    except (ValueError,KeyError,TypeError,UnicodeError):raise V2Error('INVALID_HISTORY_CURSOR','Invalid or incompatible history cursor',422) from None

def read_window(db,account,*,limit=100,from_ms=0,to_ms=9223372036854775807,cursor=None,sampling='raw'):
    if from_ms>to_ms or sampling=='minmax' and limit<6:
        raise V2Error('INVALID_HISTORY_RANGE','Ordered range and minmax limit >=6 required',422)
    with closing(sqlite3.connect(db.path.as_uri()+'?mode=ro',uri=True)) as c:
        c.execute('BEGIN')
        latest=c.execute('SELECT sequence,body_hash FROM equity_snapshots WHERE portfolio=? ORDER BY sequence DESC LIMIT 1',(account,)).fetchone()
        state=_unpack(cursor) if cursor else {'version':1,'account':account,'mode':db.mode,'from':from_ms,'to':to_ms,'watermark':latest[0] if latest else 0,'before':latest[0]+1 if latest else 1,'anchor':latest[1] if latest else ''}
        if (state['account'],state['mode'],state['from'],state['to'])!=(account,db.mode,from_ms,to_ms):
            raise V2Error('INVALID_HISTORY_CURSOR','Cursor account/mode/range mismatch',422)
        anchor=c.execute('SELECT body_hash FROM equity_snapshots WHERE portfolio=? AND sequence=?',(account,state['watermark'])).fetchone()
        if (anchor[0] if anchor else '')!=state['anchor']:
            raise V2Error('INVALID_HISTORY_CURSOR','Cursor source prefix no longer available',422)
        request_cursor=_pack(state);budget=[0]
        def progress():
            budget[0]+=1
            return budget[0]>1000
        c.set_progress_handler(progress,1000)
        try:
            where='portfolio=? AND sequence<=? AND sequence<? AND recorded_ms BETWEEN ? AND ?'
            args=(account,state['watermark'],state['before'],from_ms,to_ms)
            scanned_bytes=[0]
            def point(row):
                scanned_bytes[0]+=len(row[0].encode())
                if len(row[0])>65536 or scanned_bytes[0]>MAX_SCANNED_BYTES:raise V2Error('HISTORY_RESPONSE_BUDGET','Observation payload budget exceeded; narrow the range',503)
                p=db.decode(row[:2])
                if (p['sequence'],p['recorded_at_ms'],p['snapshot_id'])!=tuple(row[2:]):raise V2Error('STORAGE_CORRUPT','Equity index/source mismatch',503)
                if p['portfolio_id']!=account or p['data_mode']!=db.mode:raise V2Error('STORAGE_CORRUPT','Equity account/mode mismatch',503)
                return EquityPoint.model_validate(p).model_dump(mode='json')
            if sampling=='raw':
                rows=c.execute('SELECT body,body_hash,sequence,recorded_ms,id FROM equity_snapshots WHERE '+where+' ORDER BY sequence DESC LIMIT ?',(*args,limit+1)).fetchall()
                points=[point(r) for r in rows[:limit]];more=len(rows)>limit
                if sum(len(encode(p)) for p in points)>MAX_RESPONSE_BYTES:raise V2Error('HISTORY_RESPONSE_BUDGET','Reduce the page size',503)
                next_cursor=_pack({**state,'before':points[-1]['sequence']}) if more else None
                return EquityWindowResponse(portfolio_id=account,data_mode=db.mode,points=list(reversed(points)),watermark=state['watermark'],request_cursor=request_cursor,next_cursor=next_cursor,has_more=more,sampling=sampling,status='complete',observations_scanned=len(rows),excluded_incomplete=0)
            # Count only a bounded prefix; do not deserialize or retain 10k payloads.
            count=sum(1 for _ in c.execute('SELECT sequence FROM equity_snapshots WHERE '+where+' ORDER BY sequence ASC LIMIT ?',(*args,MAX_SCAN_ROWS+1)))
            if count>MAX_SCAN_ROWS:
                return EquityWindowResponse(portfolio_id=account,data_mode=db.mode,points=[],watermark=state['watermark'],request_cursor=request_cursor,next_cursor=None,has_more=True,sampling=sampling,status='incomplete_budget',observations_scanned=count,excluded_incomplete=0)
            buckets={};first=last=earliest=latest_time=None;excluded=0;bucket_count=(limit-4)//2
            with localcontext(Context(prec=60,rounding=ROUND_HALF_EVEN)):
                for i,row in enumerate(c.execute('SELECT body,body_hash,sequence,recorded_ms,id FROM equity_snapshots WHERE '+where+' ORDER BY sequence ASC LIMIT ?',(*args,MAX_SCAN_ROWS))):
                    p=point(row)
                    if not p['chart_eligible'] or p['quality_status']!='complete' or p['equity_quote'] is None:
                        excluded+=1;continue
                    value=Decimal(p['equity_quote'])
                    if not value.is_finite():raise V2Error('STORAGE_CORRUPT','Invalid equity value',503)
                    first=first or p;last=p
                    if earliest is None or p['recorded_at_ms']<earliest['recorded_at_ms']:earliest=p
                    if latest_time is None or p['recorded_at_ms']>latest_time['recorded_at_ms']:latest_time=p
                    b=min(i*bucket_count//max(count,1),bucket_count-1)
                    low,high=buckets.get(b,((value,p),(value,p)))
                    if value<low[0]:low=(value,p)
                    if value>high[0]:high=(value,p)
                    buckets[b]=(low,high)
            selected={p['sequence']:p for pair in buckets.values() for _,p in pair}
            for p in (first,last,earliest,latest_time):
                if p:selected[p['sequence']]=p
            if sum(len(encode(p)) for p in selected.values())>MAX_RESPONSE_BYTES:raise V2Error('HISTORY_RESPONSE_BUDGET','Reduce sampling size',503)
            return EquityWindowResponse(portfolio_id=account,data_mode=db.mode,points=[selected[k] for k in sorted(selected)],watermark=state['watermark'],request_cursor=request_cursor,next_cursor=None,has_more=False,sampling=sampling,status='complete',observations_scanned=count,excluded_incomplete=excluded)
        except sqlite3.OperationalError as exc:
            if 'interrupt' in str(exc):raise V2Error('HISTORY_QUERY_BUDGET','History query budget exceeded; narrow the UTC range',503) from None
            raise
        finally:c.set_progress_handler(None,0)
