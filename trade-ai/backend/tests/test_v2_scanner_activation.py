"""Activation is configuration, never a process-start or financial grant."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from market_ai.v2.api import create_runtime
from market_ai.v2.discovery import DiscoveryService,DiscoveryWrite
from market_ai.v2.product_db import fingerprint
from market_ai.v2.profile_product import ProfileWrite,ProfileSelection
from market_ai.v2.errors import V2Error

class ScannerActivationTests(TestCase):
 def setUp(self):
  self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.now=1800000000000
  self.r=create_runtime(Path(self.tmp.name)/'fixture.sqlite',mode='fixture',token='fixture-activation-test-not-secret',clock=lambda:self.now,domain_journal=True)
  self.s=self.r.discovery
 def request(self,**kw):return DiscoveryWrite(idempotency_key='activation-command',name='İş günü',runtime_mode='supported_markets',discovery=True,**kw)
 def test_named_configuration_is_persisted_but_never_starts_worker(self):
  with patch.object(self.s,'start',side_effect=AssertionError('must never start')):
   result=self.s.configure('MANUAL',self.request(favorites=['BTCUSDT'],timeframe='15m'))
   self.assertFalse(result['config']['enabled']);self.assertEqual(result['config']['name'],'İş günü')
   self.assertEqual(DiscoveryService(self.r).view('MANUAL')['config']['timeframe'],'15m')
   self.assertFalse(self.s.view('MANUAL')['runtime']['worker_active'])
 def test_activation_without_explicit_host_runtime_is_rejected_atomically(self):
  with self.assertRaises(V2Error) as error:self.s.configure('MANUAL',self.request(enabled=True))
  self.assertEqual(error.exception.code,'DISCOVERY_ACTIVATION_BLOCKED');self.assertEqual(self.s.view('MANUAL')['config']['revision'],0)
 def test_activation_then_pause_never_touches_paper_or_starts_process(self):
  self.s.configure('MANUAL',self.request())
  self.s.start()
  try:
   self.s.configure('MANUAL',DiscoveryWrite(idempotency_key='explicit-account-start',expected_revision=1,name='İş günü',runtime_mode='supported_markets',discovery=True,enabled=True))
   self.assertEqual(self.s.view('MANUAL')['runtime']['activation']['state'],'active')
   self.s.configure('MANUAL',DiscoveryWrite(idempotency_key='explicit-account-stop',expected_revision=2,name='İş günü',runtime_mode='off'))
   self.assertFalse(self.s.view('MANUAL')['config']['enabled'])
  finally:self.s.stop()
  with self.r.db.transaction() as c:self.assertEqual(len(self.r.db.rows(c,'orders')),0)
 def test_invalid_mode_empty_name_and_conflicting_activation_fail_closed(self):
  for values in ({'runtime_mode':'unsupported'},{'name':'   '},{'name':'x\nsecret'},{'runtime_mode':'off','enabled':True}):
   with self.assertRaises(ValueError):DiscoveryWrite(idempotency_key='invalid-activation',**values)
 def test_selected_profile_is_account_owned_and_revision_frozen(self):
  selection=ProfileSelection(bias_timeframe='1H',setup_timeframe='15m',trigger_timeframe='5m')
  profile=self.r.analysis.profiles.write('MANUAL',ProfileWrite(idempotency_key='activation-profile',selection=selection))
  args=dict(runtime_mode='selected_profile',profile_id=profile['profile_id'],timeframe='15m',favorites=['ETHUSDT'])
  self.s.configure('MANUAL',DiscoveryWrite(idempotency_key='bind-old-revision',**args))
  self.r.analysis.profiles.write('MANUAL',ProfileWrite(idempotency_key='profile-next-version',selection=selection),profile['profile_id'])
  cfg=self.s.view('MANUAL')['config'];self.assertEqual(cfg['profile_id'],profile['profile_id'])
  with self.assertRaises(V2Error):self.s.configure('AUTO',DiscoveryWrite(idempotency_key='cross-account-profile',**args))
 def test_runtime_lease_expiration_and_clock_rollback_are_not_ready(self):
  self.s.configure('MANUAL',self.request())
  self.assertIn('runtime_not_running',self.s.view('MANUAL')['runtime']['activation']['reasons'])
  with self.r.db.transaction() as c:
   g=self.r.db.get(c,'discovery_runtime','global');g.update(worker_owner='fixture',worker_until_ms=self.now+120000,worker_heartbeat_ms=self.now);self.s._save(c,'discovery_runtime','global',g)
  self.assertEqual(self.s.view('MANUAL')['runtime']['activation']['state'],'ready_to_activate')
  self.now-=1;self.assertIn('runtime_not_running',self.s.view('MANUAL')['runtime']['activation']['reasons'])
 def test_legacy_idempotency_receipt_survives_optional_field_extension(self):
  request=DiscoveryWrite(idempotency_key='legacy-lost-ack',enabled=True,favorites=['BTCUSDT'])
  legacy=request.model_dump(exclude={'name','runtime_mode'});result={'portfolio_id':'MANUAL','data_mode':'fixture','config':{'revision':1,'enabled':True}}
  key=fingerprint({'account':'MANUAL','key':request.idempotency_key})
  with self.r.db.transaction() as c:self.r.db.put(c,'discovery_receipts',key,{'portfolio_id':'MANUAL','digest':fingerprint(legacy),'result':result})
  self.assertEqual(self.s.configure('MANUAL',request),result)
 def test_repeated_stop_is_idempotent_and_does_not_leave_false_stopping_state(self):
  self.s.configure('MANUAL',self.request())
  self.s.start();self.s.stop();self.s.stop()
  self.assertFalse(self.s.view('MANUAL')['runtime']['worker_stopping'])
  self.assertFalse(self.s.view('MANUAL')['runtime']['worker_active'])
 def test_legacy_edit_cannot_erase_named_mode_or_bypass_new_activation_gate(self):
  self.s.configure('MANUAL',self.request())
  # An older client knows enabled/discovery, but not name/runtime_mode.
  with self.assertRaises(V2Error) as error:self.s.configure('MANUAL',DiscoveryWrite(idempotency_key='legacy-new-mode-start',expected_revision=1,enabled=True,discovery=True))
  self.assertEqual(error.exception.code,'DISCOVERY_ACTIVATION_BLOCKED')
  cfg=self.s.configure('MANUAL',DiscoveryWrite(idempotency_key='legacy-new-mode-edit',expected_revision=1,enabled=False,discovery=True))['config']
  self.assertEqual(cfg['name'],'İş günü');self.assertEqual(cfg['runtime_mode'],'supported_markets')
