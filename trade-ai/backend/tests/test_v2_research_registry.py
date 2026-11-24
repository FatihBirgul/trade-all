from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from dataclasses import replace
from tests.test_v2_walk_forward import data,cfg
from market_ai.v2.walk_forward import run_walk_forward
from market_ai.v2.research_registry import ResearchRegistry
class ResearchRegistryTests(TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'research-only.sqlite'
        self.registry=ResearchRegistry.create(self.path)
    def test_pre_registered_frozen_result_is_cached_after_restart(self):
        r=run_walk_forward(data(),cfg(),registry=self.registry)
        self.assertEqual(r['registration']['scope'],'local_registry_only');self.assertEqual(r['evidence_status'],'INSUFFICIENT_EVIDENCE')
        with patch('market_ai.v2.walk_forward.run_backtest',side_effect=AssertionError('held-out must not be evaluated twice')):
            self.assertEqual(run_walk_forward(data(),cfg(),registry=ResearchRegistry(self.path)),r)
    def test_cross_protocol_heldout_overlap_rejected_before_any_training(self):
        run_walk_forward(data(),cfg(),registry=self.registry)
        with patch('market_ai.v2.walk_forward.run_backtest',side_effect=AssertionError('must reject before training')):
            with self.assertRaises(ValueError):run_walk_forward(data(),cfg(fee_bps='7'),registry=self.registry)
    def test_modified_heldout_data_cannot_bypass_same_stream_overlap(self):
        from market_ai.v2.research import HistoricalDataset
        run_walk_forward(data(),cfg(),registry=self.registry);d=data();b=list(d.frames['1m']);b[-2]=replace(b[-2],close=110.5)
        changed=HistoricalDataset({'1m':b},dict(d.rules),data_kind='synthetic',data_version='changed-test-dataset')
        with self.assertRaises(ValueError):run_walk_forward(changed,cfg(),registry=self.registry)
    def test_result_is_append_only_and_missing_financial_db_never_opened_as_registry(self):
        import sqlite3
        from contextlib import closing
        r=run_walk_forward(data(),cfg(),registry=self.registry)
        with self.assertRaises(ValueError):self.registry.save_result(r['experiment_id'],{**r,'evidence_status':'FAKE_PROFITABILITY'})
        with closing(sqlite3.connect(self.path)) as c:
            with self.assertRaises(sqlite3.DatabaseError):c.execute('DELETE FROM research_results')
        with self.assertRaises(FileExistsError):ResearchRegistry.create(self.path)
        with self.assertRaises(FileNotFoundError):ResearchRegistry(self.path.with_name('missing.sqlite'))
        original=self.path.read_bytes()
        financial=self.path.with_name('financial.sqlite')
        with closing(sqlite3.connect(financial)) as c:c.execute('CREATE TABLE product_meta(version INTEGER,mode TEXT)')
        financial_before=financial.read_bytes()
        with self.assertRaises(ValueError):ResearchRegistry(financial)
        self.assertEqual(financial.read_bytes(),financial_before)
        self.assertEqual(self.path.read_bytes(),original)
    def test_cli_uses_explicit_registry_and_returns_frozen_result_on_retry(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from scripts.walk_forward_v2 import main
        import json
        args=['synthetic-fixture.json','--train-bars','303','--test-bars','3','--horizon','1','--purge','1','--max-folds','1','--paper','--registry',str(self.path)]
        result=StringIO()
        with patch('scripts.walk_forward_v2.load_dataset',return_value=data()),redirect_stdout(result):self.assertEqual(main(args),0)
        first=json.loads(result.getvalue());result=StringIO()
        with patch('scripts.walk_forward_v2.load_dataset',return_value=data()),patch('market_ai.v2.walk_forward.run_backtest',side_effect=AssertionError('cached CLI result')),redirect_stdout(result):self.assertEqual(main(args),0)
        self.assertEqual(json.loads(result.getvalue()),first)
    def test_registration_window_failure_rolls_back_entire_preregistration(self):
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(self.path)) as c:
            c.execute("CREATE TRIGGER fixture_disk_failure BEFORE INSERT ON research_windows WHEN NEW.start_ms=20 BEGIN SELECT RAISE(ABORT,'controlled registry write failure'); END")
        with self.assertRaises(sqlite3.DatabaseError):self.registry.register({'fixture':'rollback'},'stream',[(1,10),(20,30)])
        with closing(sqlite3.connect(self.path)) as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM research_protocols').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM research_windows').fetchone()[0],0)
    def test_concurrent_overlapping_protocols_cannot_both_register(self):
        from concurrent.futures import ThreadPoolExecutor
        def run(i):
            try:self.registry.register({'fixture':i},'stream',[(1,10)]);return True
            except ValueError:return False
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,(1,2)))
        self.assertEqual(sum(results),1)
