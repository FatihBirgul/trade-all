"""Journal-enabled bounded soak, preserving the original legacy scenario."""
from unittest import TestCase
from scripts.soak_v2_audit import run_soak


class DomainSoakTests(TestCase):
    def test_domain_chain_survives_scanner_recovery_failures_and_restore(self):
        result=run_soak(cycles=1,seed=12,domain_journal=True)
        self.assertGreater(result['domain_events'],1000)
        self.assertGreater(result['transactions'],10)
        self.assertEqual(result['incomplete_checks'],0)
        self.assertEqual(result['financial_mismatches'],0)
        self.assertEqual(result['unexpected_errors'],0)
        self.assertEqual(result['injected_sqlite_failures'],1)
        self.assertGreater(result['event_append_attempts'],result['domain_events'])
        self.assertGreater(result['event_append_max_ms'],0)
        self.assertLess(result['database_bytes'],64*1024*1024)
