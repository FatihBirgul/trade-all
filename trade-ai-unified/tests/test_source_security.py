import ast,json,hashlib,sys,unittest
from pathlib import Path
import unified_forex
from unified_forex.engine import AnalysisEngine
from fixtures import fixture,NOW
ROOT=Path(__file__).resolve().parents[1]


class SourceSafety(unittest.TestCase):
    def test_migrated_hashes_and_license_are_accounted(self):
        rows=json.loads((ROOT/'docs/source_manifest.json').read_text())
        for row in rows:
            if not row.get('destination'):
                self.assertTrue(row['exclusion_reason']);continue
            path=ROOT/row['destination'];self.assertTrue(path.is_file(),str(path))
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),row['destination_sha256'],str(path))
        self.assertIn('Copyright (c) 2026 Jake Schincariol',(ROOT/'vendor/day_trader/LICENSE').read_text(encoding='utf-8'))
    def test_no_order_or_product_dependency_in_runtime(self):
        AnalysisEngine().analyze(fixture(),'XAUUSD',now=NOW)
        for name in ('paper_ledger','product_db','analysis_service','domain_journal','market_poller'):
            self.assertNotIn('market_ai.v2.'+name,sys.modules)
        paths=list((ROOT/'unified_forex').glob('*.py'))+list((ROOT/'vendor/trade_ai/backend/market_ai').rglob('*.py'))
        for path in paths:
            tree=ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node,ast.Call):
                    name=node.func.attr if isinstance(node.func,ast.Attribute) else node.func.id if isinstance(node.func,ast.Name) else ''
                    self.assertNotIn(name,('order_send','order_check','place_order','submit_order','close_position'),str(path))
                if isinstance(node,ast.ImportFrom):
                    self.assertFalse((node.module or '').endswith(('paper_ledger','product_db','analysis_service')),str(path))
    def test_zero_spread_is_explicitly_simulation_only(self):
        p=fixture();p.data['XAUUSD']['quote']['ask']=p.data['XAUUSD']['quote']['bid']
        r=AnalysisEngine().analyze(p,'XAUUSD',now=NOW)
        self.assertEqual(r.final_decision,'INSUFFICIENT_DATA')

    def test_operator_declaration_cannot_replace_broker_contract_size(self):
        from unittest.mock import patch
        from unified_forex.providers import ContractMT5Provider
        from forex.core import DataError
        with patch('forex.providers.MT5Provider.__init__',return_value=None),patch('forex.providers.MT5Provider.metadata',return_value={}):
            p=ContractMT5Provider(instruments={'XAUUSD':{'contract_size':1}})
            with self.assertRaises(DataError):p.metadata('XAUUSD')

    def test_broker_boundary_rejects_order_before_sdk_call(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from forex.providers import MT5Provider
        from forex.core import DataError
        send=Mock()
        provider=MT5Provider(SimpleNamespace(order_send=send))
        with self.assertRaisesRegex(DataError,'read-only boundary'):
            provider._call('order_send',{'action':'forbidden-test'})
        send.assert_not_called()
