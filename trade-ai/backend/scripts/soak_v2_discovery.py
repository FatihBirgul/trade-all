"""Bounded discovery rehearsal: temporary DB, labelled fixtures, no live services."""
import argparse,json,time,tracemalloc,sys
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from market_ai.v2.api import create_runtime
from market_ai.v2.discovery import DiscoveryWrite
from market_ai.v2.paper_audit import audit_database

def run(cycles=4):
 if type(cycles) is not int or not 1<=cycles<=12:raise ValueError('cycles must be 1..12')
 with TemporaryDirectory(prefix='trade-ai-discovery-rehearsal-') as directory:
  path=Path(directory)/'fixture.sqlite';now=[1800000000000]
  r=create_runtime(path,mode='fixture',token='fixture-discovery-rehearsal-not-secret',clock=lambda:now[0],domain_journal=True)
  for a in ('AUTO','MANUAL'):r.discovery.configure(a,DiscoveryWrite(idempotency_key='rehearsal-'+a,enabled=True,discovery=True,favorites=['BTCUSDT'],interval_seconds=60))
  samples=[];jobs=0;tracemalloc.start()
  try:
   for _ in range(cycles):
    start=time.monotonic();result=r.discovery.tick();samples.append(time.monotonic()-start)
    assert result['status']=='completed' and len(result['jobs'])<=2 and result['provider_calls']<=12
    jobs+=len(result['jobs']);now[0]+=300000
   _,peak=tracemalloc.get_traced_memory()
  finally:tracemalloc.stop()
  start=time.monotonic();audit=audit_database(path,require_domain=True);audit_seconds=time.monotonic()-start
  assert audit['status']=='PASS',audit['checks']
  chains={a:r.discovery.verify_events(a) for a in ('AUTO','MANUAL')};assert all(c['status']=='PASS' for c in chains.values())
  with r.db.transaction() as c:assert c.execute('SELECT count(*) FROM orders').fetchone()[0]==0
  return {'input':'controlled_fixture_not_market_capacity','cycles':cycles,'deep_analyses':jobs,'eligible_universe':3,'cycle_seconds_mean':round(sum(samples)/len(samples),4),'cycle_seconds_max':round(max(samples),4),'peak_traced_bytes':peak,'db_bytes':path.stat().st_size,'audit_seconds':round(audit_seconds,4),'financial_audit':audit['status'],'financial_checks':audit['checks'],'event_chains':chains,'automatic_orders':0,'push_delivery':'UNVERIFIED','live_capacity':'UNVERIFIED'}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cycles',type=int,default=4);p.add_argument('--output',type=Path);a=p.parse_args();result=run(a.cycles);out=json.dumps(result,indent=2,sort_keys=True)+'\n'
 if a.output:a.output.write_text(out)
 print(out,end='')
