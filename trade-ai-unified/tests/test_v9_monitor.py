import unittest
from datetime import datetime,timezone
from unified_forex.official_calendar import parse_schedule,coverage_snapshot


class MacroSchemaMonitoring(unittest.TestCase):
    def test_source_changes_and_empty_future_coverage_are_explicit(self):
        now=datetime(2026,11,6,tzinfo=timezone.utc)
        past=parse_schedule('<dt>01/01/2025</dt><dd>monetary policy meeting</dd>','ecb',retrieved_at=now)
        a=coverage_snapshot(past,source_id='ecb',retrieved_at=now)
        self.assertEqual(a['schedule_status'],'NO_UPCOMING_RECORDS_OBSERVED')
        future=parse_schedule('<dt>01/01/2027</dt><dd>monetary policy meeting</dd>','ecb',retrieved_at=now)
        b=coverage_snapshot(future,source_id='ecb',retrieved_at=now,previous=a)
        self.assertEqual(len(b['added']),1);self.assertEqual(len(b['removed']),1)
        self.assertFalse(b['coverage_complete'])
