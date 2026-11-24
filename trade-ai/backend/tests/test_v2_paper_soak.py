"""Bounded soak, no remote services; audit at every mutation/recovery phase."""
from unittest import TestCase
from scripts.soak_v2_audit import run_soak


class PaperSoakTests(TestCase):
    def test_seeded_multi_account_lifecycle_recovery_and_restore(self):
        metrics = run_soak(cycles=3, seed=12)
        self.assertGreaterEqual(metrics['events'], 900)
        self.assertGreater(metrics['transactions'], 40)
        self.assertGreater(metrics['audits'], 40)
        self.assertEqual(metrics['injected_sqlite_failures'], 3)
        self.assertGreater(metrics['duplicate_responses'], 200)
        self.assertGreaterEqual(metrics['restarts'], 4)
        self.assertGreaterEqual(metrics['utc_days'], 2)
        self.assertEqual(metrics['financial_mismatches'], 0)
        self.assertEqual(metrics['unexpected_errors'], 0)
        self.assertLess(metrics['database_bytes'], 32*1024*1024)

    def test_soak_refuses_unbounded_or_invalid_work(self):
        for cycles in (0, -1, 9, True):
            with self.assertRaises(ValueError):
                run_soak(cycles=cycles)
