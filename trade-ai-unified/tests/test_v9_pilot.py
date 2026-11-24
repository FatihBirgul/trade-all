import unittest,json
from datetime import datetime,timezone,timedelta
from hashlib import sha256
from unittest.mock import Mock
from fixtures import fixture,NOW
from unified_forex.pilot import export
from unified_forex.pilot_validation import validate
from forex.contracts import canonical


class UntrustedPilotInput(unittest.TestCase):
    def test_source_fingerprint_matches_portable_repository_paths(self):
        from pathlib import Path
        import hashlib
        from unified_forex.engine import code_digest,ROOT
        paths=list((ROOT/'unified_forex').glob('*.py'))+list((ROOT/'vendor/trade_ai/backend/market_ai').rglob('*.py'))+list((ROOT/'vendor/day_trader/forex').glob('*.py'))
        entries={ '/'.join(p.relative_to(ROOT).parts):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        self.assertEqual(code_digest(),hashlib.sha256(canonical(entries).encode()).hexdigest())
    def evidence(self):
        p=fixture();p.health=Mock(return_value={'connected':True});r=export(p,('XAUUSD',))
        r['timestamp']=datetime.fromtimestamp(NOW,timezone.utc).isoformat()
        r['evidence_sha256']=sha256(canonical({k:v for k,v in r.items() if k!='evidence_sha256'}).encode()).hexdigest()
        return r
    def test_valid_hash_does_not_promote_broker_or_override_metadata(self):
        r=self.evidence();now=datetime.fromtimestamp(NOW,timezone.utc)
        result=validate(json.dumps(r),as_of=now,expected_code_sha256=r['code_sha256'])
        self.assertTrue(result['eligible_for_review']);self.assertFalse(result['real_terminal_validated'])
        self.assertFalse(result['automatic_contract_override'])
        with self.assertRaises(ValueError):validate(r,as_of=now,expected_code_sha256='0'*64)
    def test_rehashed_sensitive_fields_future_stale_and_bad_profit_refused(self):
        now=datetime.fromtimestamp(NOW,timezone.utc)
        for mutate in (lambda r:r.update(login=123),lambda r:r['symbols']['XAUUSD']['contract'].update(password='secret'),
                       lambda r:r.update(mt5_validation='VERIFIED'),lambda r:r['symbols']['XAUUSD']['profit_samples'][0].update(pnl_account_currency=1)):
            r=self.evidence();mutate(r);r['evidence_sha256']=sha256(canonical({k:v for k,v in r.items() if k!='evidence_sha256'}).encode()).hexdigest()
            with self.assertRaises(ValueError):validate(r,as_of=now)
        with self.assertRaises(ValueError):validate(self.evidence(),as_of=now-timedelta(seconds=1))
        with self.assertRaises(ValueError):validate(self.evidence(),as_of=now+timedelta(days=2))
