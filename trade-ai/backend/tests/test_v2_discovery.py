from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from market_ai.v2.api import create_runtime
from market_ai.v2.discovery import DiscoveryService,DiscoveryWrite

class DiscoveryTests(TestCase):
 def setUp(self):
  self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.now=1800000000000
  self.r=create_runtime(Path(self.tmp.name)/'fixture.sqlite',mode='fixture',token='fixture-discovery-test-not-secret-32',clock=lambda:self.now,domain_journal=True)
  self.s=DiscoveryService(self.r)
 def enable(self,account='MANUAL',**kw):
  return self.s.configure(account,DiscoveryWrite(idempotency_key='configure-'+account,enabled=True,favorites=['BTCUSDT'],**kw))
 def test_default_disabled_and_no_financial_authority(self):
  self.assertFalse(self.s.view('MANUAL')['config']['enabled'])
  self.assertEqual(self.s.tick('MANUAL')['status'],'disabled')
  self.enable();self.s.tick('MANUAL')
  with self.r.db.transaction() as c:self.assertEqual(c.execute('SELECT count(*) FROM orders').fetchone()[0],0)
 def test_favorite_discovery_overlap_one_analysis_and_restart_dedup(self):
  self.enable(discovery=True);r=self.s.tick('MANUAL');self.assertEqual(r['status'],'completed')
  view=self.s.view('MANUAL');btc=[j for j in view['jobs'] if j['symbol']=='BTCUSDT']
  self.assertEqual(len(btc),1);self.assertEqual(set(btc[0]['modes']),{'favorites','discovery'})
  before=self.s.opportunities('MANUAL');self.now+=60000
  restarted=DiscoveryService(self.r);restarted.tick('MANUAL');self.assertEqual(restarted.opportunities('MANUAL'),before)
 def test_account_isolation_config_cas_and_idempotent_receipt(self):
  write=DiscoveryWrite(idempotency_key='same-config-key',enabled=True,favorites=['ETHUSDT'])
  a=self.s.configure('MANUAL',write);self.assertEqual(self.s.configure('MANUAL',write),a)
  self.assertFalse(self.s.view('AUTO')['config']['enabled'])
  with self.assertRaises(Exception):self.s.configure('MANUAL',DiscoveryWrite(idempotency_key='conflicting-key',enabled=True))
 def test_discovery_only_bounded_queue_and_provider_budget(self):
  self.s.configure('MANUAL',DiscoveryWrite(idempotency_key='discovery-only-key',enabled=True,discovery=True))
  r=self.s.tick('MANUAL');self.assertLessEqual(len(r['jobs']),2);self.assertLessEqual(r['provider_calls'],12)
  v=self.s.view('MANUAL');self.assertEqual(v['runtime']['eligible'],3)
  self.assertEqual(len(v['runtime']['queue']),3);self.assertEqual(v['runtime']['backlog'],1)
  self.assertTrue(all(j['modes']==['discovery'] for j in r['jobs']))
 def test_same_closed_boundary_is_not_false_outage_or_duplicate_alert(self):
  self.enable(interval_seconds=60,notify_confirmed=True);self.s.tick('MANUAL')
  first=self.s.opportunities('MANUAL');self.now+=60000;self.s.tick('MANUAL')
  self.assertEqual(self.s.opportunities('MANUAL'),first)
  self.assertEqual(self.s.view('MANUAL')['runtime']['provider_status'],'reachable')
  with self.r.db.transaction() as c:self.assertEqual(len(self.r.db.rows(c,'notifications')),1)
 def test_outage_recovery_not_market_invalidation_or_reconfirmed_alert(self):
  from unittest.mock import patch
  from market_ai.v2.spot_provider import ProviderUnavailable
  self.enable(interval_seconds=60,notify_confirmed=True);self.s.tick('MANUAL')
  key=self.s.opportunities('MANUAL')['items'][0]['opportunity_id']
  self.now+=300000
  with patch.object(self.r.analysis.provider,'candles',side_effect=ProviderUnavailable('controlled')):self.s.tick('MANUAL')
  self.assertEqual(self.s.detail('MANUAL',key)['opportunity']['state'],'UNAVAILABLE')
  self.now+=300000;self.s.tick('MANUAL')
  self.assertEqual(self.s.detail('MANUAL',key)['opportunity']['state'],'CONFIRMED')
  with self.r.db.transaction() as c:self.assertEqual(len(self.r.db.rows(c,'notifications')),1)
  self.assertEqual(self.s.verify_events('MANUAL')['status'],'PASS')
 def test_actual_evidence_change_invalidates_and_ttl_expires_without_backfill(self):
  self.enable(interval_seconds=60,ttl_seconds=300);self.s.tick('MANUAL');key=self.s.opportunities('MANUAL')['items'][0]['opportunity_id']
  self.now+=600000;self.s.tick('MANUAL')
  self.assertEqual(self.s.detail('MANUAL',key)['opportunity']['state'],'EXPIRED')
  self.assertEqual(len(self.s.opportunities('MANUAL')['items']),1)
  self.assertEqual(self.s.verify_events('MANUAL')['status'],'PASS')
 def test_config_changed_during_fetch_fences_old_analysis(self):
  from unittest.mock import patch
  self.enable();original=self.r.analysis.provider.candles;changed=[]
  def edit(*args):
   if not changed:
    changed.append(True);self.s.configure('MANUAL',DiscoveryWrite(idempotency_key='edit-during-scan',expected_revision=1,enabled=False,favorites=[]))
   return original(*args)
  with patch.object(self.r.analysis.provider,'candles',side_effect=edit):r=self.s.tick('MANUAL')
  self.assertEqual(r['status'],'superseded');self.assertEqual(self.s.opportunities('MANUAL')['items'],[])
 def test_overlapping_tick_and_stale_lease_recovery(self):
  self.enable()
  with self.r.db.transaction() as c:
   g=self.r.db.get(c,'discovery_runtime','global');g.update(owner='old-fixture',lease_until_ms=self.now+1000);self.s._save(c,'discovery_runtime','global',g)
  self.assertEqual(self.s.tick('MANUAL')['status'],'busy');self.now+=2000
  self.assertEqual(self.s.tick('MANUAL')['status'],'completed');self.assertEqual(self.s.view('MANUAL')['runtime']['recovered_leases'],1)
 def test_invalid_source_and_unsupported_favorites_fail_closed(self):
  from dataclasses import replace
  from unittest.mock import patch
  self.enable();original=self.r.analysis.provider.candles
  def unfinished(*args):
   b=original(*args);return b[:-1]+[replace(b[-1],is_final=False)]
  with patch.object(self.r.analysis.provider,'candles',side_effect=unfinished):self.s.tick('MANUAL')
  self.assertEqual(self.s.opportunities('MANUAL')['items'],[]);self.assertEqual(self.s.view('MANUAL')['runtime']['provider_status'],'unavailable')
  for bad in ({'favorites':['EURUSD']},{'interval_seconds':True},{'favorites':['BTCUSDT','BTCUSDT']},{'ttl_seconds':0}):
   with self.assertRaises(ValueError):DiscoveryWrite(idempotency_key='bad-request-key',**bad)
 def test_runtime_worker_is_explicit_and_graceful(self):
  import time
  self.assertFalse(self.s.view('MANUAL')['runtime']['worker_active']);self.enable()
  self.s.start()
  try:
   deadline=time.monotonic()+3
   while not self.s.view('MANUAL')['runtime']['last_attempt_ms'] and time.monotonic()<deadline:time.sleep(.02)
   self.assertTrue(self.s.view('MANUAL')['runtime']['worker_active'])
   with self.assertRaises(Exception):DiscoveryService(self.r).start()
  finally:self.s.stop()
  self.assertFalse(self.s.view('MANUAL')['runtime']['worker_active'])
 def test_wait_cannot_be_confirmed_and_early_uses_closed_reclaim_only(self):
  import json
  from market_ai.v2.api_models import AnalysisResponse
  from market_ai.v2.discovery import observation
  from market_ai.v2.strategies import BUILTIN_IDS
  a=AnalysisResponse.model_validate(json.loads((Path(__file__).resolve().parents[2]/'docs/v2_examples/sweep_setup.json').read_text()))
  self.assertEqual(observation(a,a.created_at_ms,BUILTIN_IDS)['state'],'CONFIRMED')
  b=a.model_copy(deep=True);b.direction='WAIT';b.strategy_setups['failed_breakout_v2']['status']='wait';b.strategy_setups['failed_breakout_v2']['reason']='entry_confirmation_missing'
  b.technical_methods['liquidity_sweep'].update(status='available',direction='bullish',as_of_ms=b.price_time_ms)
  self.assertEqual(observation(b,b.created_at_ms,BUILTIN_IDS)['state'],'EARLY')
  b.quality['ok']=False;self.assertEqual(observation(b,b.created_at_ms,BUILTIN_IDS)['state'],'UNAVAILABLE')
 def test_financial_audit_and_legacy_watchlist_quota_unchanged(self):
  from market_ai.v2.paper_audit import audit_database
  before=audit_database(self.r.db.path,require_domain=True);self.enable(discovery=True);self.s.tick('MANUAL')
  after=audit_database(self.r.db.path,require_domain=True)
  self.assertEqual(before['status'],'PASS');self.assertEqual(after['status'],'PASS',after)
  with self.r.db.transaction() as c:
   self.assertEqual(len(self.r.db.rows(c,'watchlist')),0);self.assertEqual(len(self.r.db.rows(c,'orders')),0)
 def test_one_faulty_instrument_does_not_block_other_candidates(self):
  from unittest.mock import patch
  self.s.configure('MANUAL',DiscoveryWrite(idempotency_key='isolate-instrument',enabled=True,discovery=True))
  original=self.r.analysis.provider.rules
  def faulty(symbol):
   if symbol=='ETHUSDT':raise RuntimeError('sensitive-provider-message-never-persisted')
   return original(symbol)
  with patch.object(self.r.analysis.provider,'rules',side_effect=faulty):result=self.s.tick('MANUAL')
  self.assertEqual(result['status'],'completed');self.assertTrue(result['jobs'])
  self.assertNotIn('sensitive-provider-message',str(self.s.view('MANUAL')))
 def test_configuration_edit_supersedes_old_queue_and_no_stale_backlog(self):
  self.enable(discovery=True);self.s.tick('MANUAL');self.assertEqual(self.s.view('MANUAL')['runtime']['backlog'],1)
  self.s.configure('MANUAL',DiscoveryWrite(idempotency_key='disable-old-queue',expected_revision=1,enabled=False))
  self.assertEqual(self.s.view('MANUAL')['runtime']['backlog'],0)
  self.assertEqual(self.s.tick('MANUAL')['status'],'disabled')
 def test_event_write_failure_rolls_back_projection_and_retries_same_analysis(self):
  from unittest.mock import patch
  import sqlite3
  self.enable(interval_seconds=60)
  with patch.object(self.s,'_event',side_effect=sqlite3.OperationalError('controlled-disk-error')):
   with self.assertRaises(sqlite3.OperationalError):self.s.tick('MANUAL')
  self.assertEqual(self.s.opportunities('MANUAL')['items'],[])
  self.assertEqual(self.s.verify_events('MANUAL')['events'],0)
  self.now+=60000;self.s.tick('MANUAL')
  self.assertEqual(len(self.s.opportunities('MANUAL')['items']),1)
  self.assertEqual(self.s.verify_events('MANUAL')['events'],1)
 def test_clock_rollback_and_old_source_never_retroactively_create(self):
  self.enable(interval_seconds=60);self.s.tick('MANUAL');before=self.s.opportunities('MANUAL')
  self.now-=300000;self.assertEqual(self.s.tick('MANUAL')['status'],'clock_rollback')
  after=self.s.opportunities('MANUAL');self.assertEqual([x['opportunity_id'] for x in before['items']],[x['opportunity_id'] for x in after['items']])
  self.assertTrue(after['items'][0]['stale'])
 def test_chain_corruption_detected_on_disposable_fixture_only(self):
  from market_ai.v2.product_db import encode,fingerprint
  self.enable();self.s.tick('MANUAL')
  with self.r.db.transaction() as c:
   c.execute('DROP TRIGGER opportunity_events_update')
   row=c.execute('SELECT id,body,body_hash FROM opportunity_events LIMIT 1').fetchone();e=self.r.db.decode(row[1:])
   e['previous_hash']='f'*64
   c.execute('UPDATE opportunity_events SET body=?,body_hash=? WHERE id=?',(encode(e),fingerprint(e),row[0]))
  self.assertEqual(self.s.verify_events('MANUAL')['status'],'CORRUPT')
 def test_provider_minute_budget_is_durable_after_restart(self):
  from market_ai.v2.spot_provider import ProviderUnavailable
  for _ in range(24):self.s._reserve()
  with self.assertRaises(ProviderUnavailable):DiscoveryService(self.r)._reserve()
  self.now+=60000;DiscoveryService(self.r)._reserve()
 def test_same_source_new_discovery_provenance_keeps_one_opportunity_and_one_alert(self):
  self.enable(interval_seconds=60,notify_confirmed=True);self.s.tick('MANUAL')
  self.s.configure('MANUAL',DiscoveryWrite(idempotency_key='add-discovery-mode',expected_revision=1,enabled=True,favorites=['BTCUSDT'],discovery=True,interval_seconds=60,notify_confirmed=True))
  self.now+=60000;self.s.tick('MANUAL')
  btc=[o for o in self.s.opportunities('MANUAL')['items'] if o['symbol']=='BTCUSDT']
  self.assertEqual(len(btc),1);self.assertEqual(set(btc[0]['modes']),{'favorites','discovery'})
  with self.r.db.transaction() as c:
   notices=[n for n in self.r.db.rows(c,'notifications') if n['details'].get('opportunity_id')==btc[0]['opportunity_id']]
  self.assertEqual(len(notices),1)
 def test_manual_tick_after_gracefully_stopped_worker_can_observe_outage(self):
  from unittest.mock import patch
  from market_ai.v2.spot_provider import ProviderUnavailable
  import time
  self.enable(interval_seconds=60);self.s.start()
  try:
   deadline=time.monotonic()+3
   while not self.s.opportunities('MANUAL')['items'] and time.monotonic()<deadline:time.sleep(.02)
  finally:self.s.stop()
  key=self.s.opportunities('MANUAL')['items'][0]['opportunity_id'];self.now+=300000
  with patch.object(self.r.analysis.provider,'candles',side_effect=ProviderUnavailable('controlled')):result=self.s.tick('MANUAL')
  self.assertEqual(result['status'],'completed');self.assertEqual(self.s.detail('MANUAL',key)['opportunity']['state'],'UNAVAILABLE')
 def test_real_fresh_range_evidence_invalidates_previous_trend(self):
  self.enable(interval_seconds=60);self.s.tick('MANUAL');key=self.s.opportunities('MANUAL')['items'][0]['opportunity_id']
  self.now+=300000;self.r.analysis.provider.case='range';self.s.tick('MANUAL')
  self.assertEqual(self.s.detail('MANUAL',key)['opportunity']['state'],'INVALIDATED')
 def test_concurrent_configuration_lost_ack_has_one_revision(self):
  from concurrent.futures import ThreadPoolExecutor
  request=DiscoveryWrite(idempotency_key='concurrent-config-key',enabled=True,favorites=['BTCUSDT'])
  with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.s.configure('MANUAL',request),range(2)))
  self.assertEqual(results[0],results[1]);self.assertEqual(self.s.view('MANUAL')['config']['revision'],1)
 def test_old_but_within_age_boundary_candle_is_not_new_opportunity(self):
  from unittest.mock import patch
  self.enable();original=self.r.analysis.provider.candles
  with patch.object(self.r.analysis.provider,'candles',side_effect=lambda *args:original(*args)[:-1]):self.s.tick('MANUAL')
  self.assertEqual(self.s.opportunities('MANUAL')['items'],[])
 def test_first_known_is_actual_evaluation_not_backdated_source_close(self):
  self.now+=45000;self.enable();self.s.tick('MANUAL')
  opp=self.s.opportunities('MANUAL')['items'][0]
  self.assertEqual(opp['first_known_ms'],self.now);self.assertLess(opp['first_source_ms'],opp['first_known_ms'])
 def test_slow_provider_does_not_hold_sqlite_or_block_health_reads(self):
  from concurrent.futures import ThreadPoolExecutor
  from threading import Event
  from unittest.mock import patch
  entered,release=Event(),Event();original=self.r.analysis.provider.candles;self.enable()
  def slow(*args):
   entered.set();release.wait(3);return original(*args)
  with ThreadPoolExecutor(max_workers=2) as pool:
   with patch.object(self.r.analysis.provider,'candles',side_effect=slow):
    scanning=pool.submit(self.s.tick,'MANUAL')
    try:
     self.assertTrue(entered.wait(2));view=pool.submit(self.s.view,'MANUAL').result(2)
     self.assertGreater(view['runtime']['lease_until_ms'],self.now)
    finally:release.set()
    self.assertEqual(scanning.result(5)['status'],'completed')
 def test_actual_closed_reclaim_early_to_confirmed_without_classifier_mock(self):
  from dataclasses import replace
  from scripts.v2_scenario_fixtures import fixture
  from market_ai.v2.spot_provider import FixtureSpotProvider
  first=self.now
  class ClosedSweep(FixtureSpotProvider):
   def candles(provider,symbol,tf,now):
    initial=fixture('sweep',tf,first,symbol);sweep=initial[-2]
    initial[-2]=replace(initial[-3],open_time_ms=initial[-2].open_time_ms,close_time_ms=initial[-2].close_time_ms)
    initial[-1]=replace(sweep,open_time_ms=initial[-1].open_time_ms,close_time_ms=initial[-1].close_time_ms,volume=100)
    return initial if now==first else initial[1:]+[fixture('sweep',tf,now,symbol)[-1]]
  provider=ClosedSweep();self.r.analysis.provider=provider;self.enable(interval_seconds=60,notify_early=True,notify_confirmed=True)
  self.s.tick('MANUAL');opp=self.s.opportunities('MANUAL')['items'][0];key=opp['opportunity_id']
  self.assertEqual(opp['state'],'EARLY')
  with self.r.db.transaction() as c:early=self.r.db.get(c,'analyses',opp['last_analysis_id'])
  self.assertEqual(early['direction'],'WAIT');self.assertIsNone(early['levels'])
  before=provider.candles('BTCUSDT','5m',first);self.now+=300000
  self.assertEqual(before[1:],provider.candles('BTCUSDT','5m',self.now)[:-1])
  self.s.tick('MANUAL');detail=self.s.detail('MANUAL',key)
  self.assertEqual(detail['opportunity']['state'],'CONFIRMED');self.assertEqual([e['state'] for e in reversed(detail['events'])],['EARLY','CONFIRMED'])
  self.assertFalse(detail['opportunity']['trade_permission']);self.assertEqual(self.s.verify_events('MANUAL')['status'],'PASS')
  self.now+=60000;self.s.tick('MANUAL')
  with self.r.db.transaction() as c:self.assertEqual(len(self.r.db.rows(c,'notifications')),2);self.assertEqual(len(self.r.db.rows(c,'orders')),0)
 def test_slow_worker_stop_recovers_after_bounded_join_timeout(self):
  from threading import Event
  from unittest.mock import patch
  entered,release=Event(),Event();original=self.r.analysis.provider.candles;self.enable(interval_seconds=60)
  def blocked(*args):
   entered.set();release.wait(6);return original(*args)
  with patch.object(self.r.analysis.provider,'candles',side_effect=blocked):
   self.s.start()
   try:
    self.assertTrue(entered.wait(2));self.s.stop();self.assertTrue(self.s.worker.is_alive())
   finally:release.set();self.s.worker.join(3)
  self.assertFalse(self.s.worker.is_alive());self.now+=300000
  self.assertEqual(self.s.tick('MANUAL')['status'],'completed')
