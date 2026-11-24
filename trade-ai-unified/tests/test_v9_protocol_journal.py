import unittest
from datetime import datetime,timezone,timedelta
from dataclasses import replace
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch
from fixtures import fixture,NOW
from unified_forex.engine import AnalysisEngine
from unified_forex.decision_journal import DecisionJournal
from unified_forex.research_protocol import prepare,verify,TrialRegistry
from unified_forex.research import dataset_from_provider,run_oos
from unified_forex.research_control import CancellationToken,ResearchCancelled
from unified_forex.checkpoint_store import CheckpointStore
from market_ai.v2.walk_forward import WalkForwardConfig,Candidate
from unified_forex.strategies import TREND
import test_v8_structure_ledger as historical_fixtures
from unified_forex.structure_ledger import StructureLedger


class ProtocolAndObservation(unittest.TestCase):
    def test_preregistration_budget_cancel_and_cost_identity(self):
        d=dataset_from_provider(fixture(n=420,frames=('M15',)),'XAUUSD','M15',420)
        c=WalkForwardConfig(train_bars=330,test_bars=40,warmup_bars=250,max_folds=1,simulate_orders=True,timeframe='15m',
            candidates=(Candidate('one',(TREND,),10),),fee_bps='0',spread_bps='0',slippage_bps='0')
        p=prepare(d,c);self.assertEqual(verify(p,d,c),p['protocol_id'])
        with self.assertRaises(ValueError):verify(p,d,replace(c,fee_bps='1'))
        trials=TrialRegistry();trials.declare('golden',1)
        token=CancellationToken();token.cancel()
        with self.assertRaises(ResearchCancelled):run_oos(d,c,preregistration=p,trial_registry=trials,campaign_id='golden',cancellation=token)
        self.assertEqual(trials.export('golden')['attempts'][0]['status'],'CANCELLED')
        with self.assertRaisesRegex(ValueError,'budget exhausted'):run_oos(d,c,preregistration=p,trial_registry=trials,campaign_id='golden')
        self.assertFalse(trials.export('golden')['independent_market_evidence'])
    def test_decision_and_later_observation_are_separate_immutable_records(self):
        r=AnalysisEngine().analyze(fixture(),'XAUUSD',now=NOW);journal=DecisionJournal()
        record=journal.record(r);before=journal.export(r.analysis_id)['decision']
        when=datetime.fromtimestamp(NOW,timezone.utc)
        with self.assertRaises(ValueError):journal.observe(r.analysis_id,observed_at=when,price=2000,source='synthetic',as_of=when)
        journal.observe(r.analysis_id,observed_at=when+timedelta(minutes=1),price=2001,source='synthetic',as_of=when+timedelta(minutes=2))
        after=journal.export(r.analysis_id)
        self.assertEqual(before,after['decision']);self.assertEqual(record['decision_sha256'],after['decision_sha256'])
        altered=r.model_dump();altered['decision_reasons']=['retrospectively rewritten']
        with self.assertRaises(ValueError):journal.record(altered)
        self.assertFalse(after['forward_validated'])
    def test_optional_checkpoint_store_binds_expected_source_and_is_disabled_by_default(self):
        with self.assertRaises(ValueError):CheckpointStore().save('a'*64,StructureLedger())
        f=historical_fixtures.HistoricalFVG().frame();ledger=StructureLedger();ledger.consume(f,.01)
        with TemporaryDirectory() as root,patch('unified_forex.checkpoint_store.STATE_ROOT',Path(root)):
            store=CheckpointStore(root);store.save('a'*64,ledger)
            restored=store.load('a'*64,identity=ledger.identity,source=ledger.source,timeframe=ledger.timeframe)
            self.assertEqual(restored.view(),ledger.view())
            with self.assertRaises(ValueError):store.load('a'*64,identity=ledger.identity,source='another-provider',timeframe=ledger.timeframe)
