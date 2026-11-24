"""Read-only logical copy manifest. Not a signature, restore or archive deletion.

Use reviewed isolated copy-backups. Logical hashes include account sequence and
source body hashes, not physical SQLite pages (which can differ after backup).
Concurrent source changes conservatively return INCOMPLETE, never partial PASS.
"""
from contextlib import closing
from pathlib import Path
from hashlib import sha256
import json,sqlite3
from .paper_audit import audit_database
VERSION='v2-equity-archive-manifest-1'
def digest(value):return sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def build_manifest(path,*,max_snapshots=10000):
 if type(max_snapshots) is not int or not 1<=max_snapshots<=100000:raise ValueError('Bounded snapshot budget required')
 try:
  path=Path(path).resolve(strict=True)
  with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,isolation_level=None)) as c:
   steps=[0]
   def progress():
    steps[0]+=1
    return steps[0]>2000
   c.set_progress_handler(progress,1000)
   c.execute('PRAGMA trusted_schema=OFF')
   c.execute('PRAGMA query_only=ON');c.execute('PRAGMA busy_timeout=1000');c.execute('BEGIN')
   version=c.execute('PRAGMA data_version').fetchone()[0];tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
   def head():return c.execute('SELECT sequence,event_hash FROM domain_head WHERE id=1').fetchone() if 'domain_head' in tables else None
   before=head();mode=c.execute('SELECT mode FROM product_meta').fetchone()[0]
   meta=None
   if 'domain_meta' in tables:
    raw,h=c.execute('SELECT body,body_hash FROM domain_meta').fetchone();meta=json.loads(raw)
    if digest(meta)!=h:raise ValueError('domain_meta')
   if 'equity_snapshots' not in tables:return {'version':VERSION,'status':'INCOMPLETE','reason':'equity_history_unavailable'}
   accounts={a:{'count':0,'last_sequence':0,'body_chain_hash':'0'*64,'last_snapshot_hash':None,'minimum_recorded_at_ms':None,'maximum_recorded_at_ms':None} for a in ('AUTO','MANUAL')};count=total_bytes=0
   for account,seq,stamp,raw,h in c.execute("SELECT portfolio,sequence,recorded_ms,body,body_hash FROM equity_snapshots WHERE portfolio IN ('AUTO','MANUAL') ORDER BY portfolio,sequence LIMIT ?",(max_snapshots+1,)):
    count+=1;total_bytes+=len(raw.encode())
    if count>max_snapshots or len(raw)>65536 or total_bytes>32*1024*1024:return {'version':VERSION,'status':'INCOMPLETE','reason':'snapshot_budget','accounts':None}
    b=json.loads(raw);a=accounts[account]
    if digest(b)!=h or (b['portfolio_id'],b['sequence'],b['recorded_at_ms'],b['data_mode'])!=(account,seq,stamp,mode) or seq!=a['last_sequence']+1:raise ValueError('snapshot_identity')
    a.update(count=a['count']+1,last_sequence=seq,last_snapshot_hash=h,minimum_recorded_at_ms=min(a['minimum_recorded_at_ms'],stamp) if a['minimum_recorded_at_ms'] is not None else stamp,maximum_recorded_at_ms=max(a['maximum_recorded_at_ms'],stamp) if a['maximum_recorded_at_ms'] is not None else stamp,body_chain_hash=digest({'prior':a['body_chain_hash'],'sequence':seq,'body_hash':h}))
   audit=audit_database(path,require_domain=True,max_records=min(200000,max(10000,max_snapshots*20)),max_total_body_bytes=64*1024*1024)
   c.rollback();after=head();changed=c.execute('PRAGMA data_version').fetchone()[0]!=version or after!=before
   if changed:return {'version':VERSION,'status':'INCOMPLETE','reason':'source_changed_during_audit','accounts':None}
   body={'version':VERSION,'status':audit['status'],'coverage':'forward_only_no_backfill','data_mode':mode,'accounts':accounts,'domain_head':list(before) if before else None,'domain_coverage':meta.get('coverage') if meta else None,'legacy_cutoffs':meta.get('legacy_cutoffs') if meta else None,'audit_checks':audit['checks'],'physical_file_hash_available':False,'signature_available':False}
   return {**body,'manifest_id':digest(body)}
 except (ValueError,KeyError,TypeError):return {'version':VERSION,'status':'CORRUPT','reason':'invalid_manifest_source'}
 except sqlite3.OperationalError as exc:
  if 'interrupted' in str(exc):return {'version':VERSION,'status':'INCOMPLETE','reason':'query_budget','accounts':None}
  return {'version':VERSION,'status':'ERROR','reason':'source_unavailable_or_sqlite_error'}
 except (OSError,sqlite3.DatabaseError):return {'version':VERSION,'status':'ERROR','reason':'source_unavailable_or_sqlite_error'}
def verify_manifest(path,expected,**budget):
 actual=build_manifest(path,**budget)
 if not isinstance(expected,dict) or 'manifest_id' not in expected or digest({k:v for k,v in expected.items() if k!='manifest_id'})!=expected['manifest_id']:return {'status':'CORRUPT','reason':'manifest_checksum'}
 if actual.get('status')!='PASS':return {'status':actual['status'],'reason':'source_not_fully_verified'}
 return {'status':'PASS' if actual==expected else 'MISMATCH','reason':'logical_copy_comparison'}
