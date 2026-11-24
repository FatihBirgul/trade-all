from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from fastapi.testclient import TestClient
from market_ai.v2.api import create_app
from market_ai.v2.paper_audit import audit_database

class SnapshotResearchTests(TestCase):
 def setUp(self):
  self.root=TemporaryDirectory();self.addCleanup(self.root.cleanup)
  self.path=Path(self.root.name)/'snapshot.sqlite';self.now=1800000000000
  self.app=create_app(self.path,mode='fixture',token='fixture-research-test-32-not-secret',clock=lambda:self.now,domain_journal=True)
  self.client=TestClient(self.app,headers={'Authorization':'Bearer fixture-research-test-32-not-secret'});self.addCleanup(self.client.close)
  r=self.client.post('/api/v2/analyze',json={'data_mode':'fixture','timeframe':'1H','timeframes':['4H'],'risk_portfolio':'MANUAL','idempotency_key':'snapshot-research-fixture'})
  self.assertEqual(r.status_code,200,r.text);self.a=r.json();self.url='/api/v2/analyses/'+self.a['analysis_id']+'/research'
 def catalogue(self):
  r=self.client.get(self.url);self.assertEqual(r.status_code,200,r.text);return r.json()
 def command(self,c,**kw):
  return {'source_record_id':c['source_record_id'],'symbol':c['symbol'],'timeframe':c['timeframe'],'anchor_ms':c['anchors'][-2]['open_time_ms'],**kw}
 def test_source_bound_research_is_deterministic_read_only_and_restart_safe(self):
  c=self.catalogue();self.assertEqual(c['status'],'available',c);self.assertFalse(c['trade_permission'])
  before=audit_database(self.path,require_domain=True)
  raw=self.path.read_bytes()
  r=self.client.post(self.url,json=self.command(c));self.assertEqual(r.status_code,200,r.text);body=r.json()
  self.assertEqual(body['anchored_vwap']['status'],'available',body)
  self.assertEqual(body['indicator_research']['status'],'available');self.assertFalse(body['indicator_research']['trade_permission'])
  self.assertEqual(self.client.post(self.url,json=self.command(c)).json(),body)
  self.assertEqual(self.path.read_bytes(),raw)
  self.assertEqual(audit_database(self.path,require_domain=True),before)
  self.now+=86400000
  self.assertEqual(self.client.post(self.url,json=self.command(c)).json(),body)
  self.assertEqual(self.client.get('/api/v2/analyses/'+self.a['analysis_id']).json(),self.a)
 def test_mismatched_source_version_symbol_anchor_and_unknown_params_rejected(self):
  c=self.catalogue()
  for overrides,code in (({'source_record_id':'0'*64},409),({'symbol':'ETHUSDT'},409),({'implementation_version':'future'},422),({'anchor_ms':True},422),({'anchor_ms':c['anchors'][-1]['close_time_ms']},422),({'parameters':{'ema_period':True}},422),({'parameters':{'ema_period':999}},422),({'parameters':{'risk_override':True}},422)):
   r=self.client.post(self.url,json=self.command(c,**overrides));self.assertEqual(r.status_code,code,r.text)
 def test_parameter_selection_changes_identity_not_live_analysis(self):
  c=self.catalogue();a=self.client.post(self.url,json=self.command(c)).json()
  b=self.client.post(self.url,json=self.command(c,parameters={'ema_period':8})).json()
  self.assertNotEqual(a['configuration_id'],b['configuration_id']);self.assertNotEqual(a['parameter_id'],b['parameter_id'])
  self.assertEqual(a['anchored_vwap'],b['anchored_vwap'])
  bias=self.client.post(self.url,json=self.command(c,parameters={'bias_timeframe':'4H','bias_confirmation':True}))
  self.assertEqual(bias.status_code,200,bias.text);self.assertEqual(bias.json()['indicator_research']['status'],'available')
  self.assertEqual(bias.json()['indicator_research']['bias']['timeframe'],'4H')
  self.assertNotEqual(bias.json()['configuration_id'],a['configuration_id'])
  self.assertEqual(self.client.get('/api/v2/analyses/'+self.a['analysis_id']).json(),self.a)
 def test_absent_frame_authentication_and_quality_fail_closed(self):
  r=self.client.get(self.url,params={'timeframe':'5m'});self.assertEqual(r.status_code,404,r.text)
  self.assertEqual(self.client.get(self.url,headers={'Authorization':'Bearer invalid'}).status_code,401)
  r=self.client.post('/api/v2/analyze',json={'data_mode':'fixture','timeframe':'1H','fixture_case':'gap','idempotency_key':'snapshot-gap-test'})
  self.assertEqual(r.status_code,200,r.text)
  r=self.client.get('/api/v2/analyses/'+r.json()['analysis_id']+'/research')
  self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['status'],'unavailable');self.assertEqual(r.json()['anchors'],[])
 def test_real_restart_preserves_research_and_immutable_source(self):
  c=self.catalogue();command=self.command(c)
  before=self.client.post(self.url,json=command).json()
  restarted=create_app(self.path,mode='fixture',token='fixture-research-test-32-not-secret',clock=lambda:self.now+86400000,domain_journal=True)
  with TestClient(restarted,headers={'Authorization':'Bearer fixture-research-test-32-not-secret'}) as client:
   r=client.post(self.url,json=command)
   self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json(),before)
 def test_corrupted_source_is_rejected_without_financial_or_history_repair(self):
  from contextlib import closing
  import sqlite3
  c=self.catalogue()
  with closing(sqlite3.connect(self.path)) as db:
   guard=db.execute("SELECT sql FROM sqlite_master WHERE name='immutable_records_update'").fetchone()[0]
   db.execute('DROP TRIGGER immutable_records_update')
   db.execute('UPDATE decision_records SET body_json=? WHERE record_id=?',('{}',c['source_record_id']));db.execute(guard);db.commit()
  before=self.path.read_bytes();r=self.client.get(self.url)
  self.assertEqual(r.status_code,503,r.text);self.assertEqual(r.json()['error']['code'],'STORAGE_CORRUPT')
  self.assertEqual(self.path.read_bytes(),before)
 def test_sqlite_enforces_read_only_research_connection_and_missing_file_is_not_created(self):
  from market_ai.v2.snapshot_research import research_connection
  import sqlite3
  with research_connection(self.path) as c:
   with self.assertRaises(sqlite3.OperationalError):c.execute("UPDATE accounts SET body='{}'")
  missing=self.path.with_name('missing.sqlite')
  with self.assertRaises(FileNotFoundError):
   with research_connection(missing):pass
  self.assertFalse(missing.exists())
