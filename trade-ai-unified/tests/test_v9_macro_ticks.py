import unittest
from datetime import datetime,timezone
from unified_forex.official_calendar import parse_schedule
from unified_forex.data_sides import quote_archive


class V9SideAndCalendarContracts(unittest.TestCase):
    def test_fed_cross_month_and_year_preserves_date_only(self):
        for year,months,days,first,last in [(2026,'April/May','30-1','2026-04-30','2026-05-01'),(2026,'December/January','31-1','2026-12-31','2027-01-01')]:
            payload=f'<h4>{year} FOMC Meetings</h4><div class="fomc-meeting__month">{months}</div><div class="fomc-meeting__date">{days}</div>'
            r=parse_schedule(payload,'fed_calendar',retrieved_at=datetime.now(timezone.utc));e=r['events'][0]
            self.assertEqual((e['date_start'],e['date_end']),(first,last));self.assertIsNone(e['release_utc'])
    def test_quote_ticks_validate_sides_identity_and_time_but_no_tick_replay_claim(self):
        base={'time_ms':100,'symbol':'XAUUSD','venue':'synthetic','contract_type':'cfd','source':'test','bid':2000.,'ask':2000.2}
        kwargs=dict(symbol='XAUUSD',venue='synthetic',contract_type='cfd',source='test',as_of_ms=100)
        r=quote_archive([base],**kwargs);self.assertFalse(r['execution_replay_available'])
        for changes in ({'ask':1999.},{'source':'other'},{'time_ms':101},{'bid':float('nan')}):
            with self.assertRaises(ValueError):quote_archive([{**base,**changes}],**kwargs)
        with self.assertRaises(ValueError):quote_archive([base,base],**kwargs)
