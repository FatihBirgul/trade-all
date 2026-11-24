from dataclasses import replace
from decimal import localcontext
from datetime import datetime,timezone
from unittest import TestCase
from tests.test_v2_pattern_research import bars,TF
from market_ai.v2.session_research import session_research
DAY=86400000

def day(date='2026-11-01',n=30):
    start=int(datetime.fromisoformat(date).replace(tzinfo=timezone.utc).timestamp())*1000
    b=bars()[:1][0]
    return [replace(b,open_time_ms=start+i*TF,close_time_ms=start+(i+1)*TF,open=100,high=103,low=99,close=101,volume=10) for i in range(n)]
def session(b,**kw):return session_research(b,timeframe='1m',as_of_ms=b[-1].close_time_ms,max_age_ms=TF,**kw)
class SessionResearchTests(TestCase):
    def test_real_utc_session_vwap_anchor_and_closed_opening_range(self):
        b=day();r=session(b,anchor_ms=b[5].open_time_ms)
        self.assertEqual(r['status'],'available');self.assertEqual(r['session_high'],'103');self.assertEqual(r['session_low'],'99')
        self.assertEqual(r['session_vwap']['value'],r['anchored_vwap']['value']);self.assertEqual(r['orb']['status'],'available')
        self.assertEqual(r['orb']['known_at'],b[14].close_time_ms);self.assertEqual(r['orb']['state'],'inside')
        self.assertFalse(r['trade_permission'])
    def test_opening_range_is_not_known_early_or_with_unfinished_data(self):
        b=day(n=14);self.assertEqual(session(b)['orb']['status'],'unavailable')
        self.assertEqual(session(b[:-1]+[replace(b[-1],is_final=False)])['status'],'unavailable')
    def test_missing_prefix_gap_fake_volume_and_anchor_rejected(self):
        b=day();self.assertEqual(session(b[1:])['status'],'unavailable');self.assertEqual(session(b[:4]+b[5:])['status'],'unavailable')
        r=session([replace(x,volume=None,volume_kind='unavailable') for x in b])
        self.assertEqual(r['status'],'available');self.assertEqual(r['session_vwap']['status'],'unavailable')
        for anchor in (b[-1].close_time_ms,b[0].open_time_ms+1,True):self.assertEqual(session(b,anchor_ms=anchor)['anchored_vwap']['status'],'unavailable')
    def test_utc_day_does_not_apply_new_york_dst_or_assume_forex_calendar(self):
        for date in ('2026-03-08','2026-11-01'):
            b=day(date);r=session(b);self.assertEqual(r['session_started_at_ms'],b[0].open_time_ms);self.assertEqual(r['calendar_timezone'],'UTC')
            self.assertEqual(session(b,calendar_id='America/New_York')['status'],'unavailable')
        b=day();b=[replace(x,instrument=replace(x.instrument,market='forex',contract_type='spot')) for x in b]
        self.assertEqual(session(b)['reason'],'unsupported_calendar_or_market')
    def test_decimal_context_and_prefix_do_not_change_observed_session(self):
        b=day();before=session(b[:20])
        with localcontext() as c:c.prec=3;self.assertEqual(session(b[:20]),before)
        session(b);self.assertEqual(session(b[:20]),before)
    def test_closed_utc_midnight_belongs_to_previous_session(self):
        b=day(n=1440);r=session(b)
        self.assertEqual(r['session_started_at_ms'],b[0].open_time_ms)
        r=session(b+day('2026-11-02',n=1));self.assertEqual(r['previous_session']['status'],'available')
        self.assertEqual(r['previous_session']['high'],'103');self.assertEqual(r['session_started_at_ms'],b[-1].close_time_ms)

class AnchorResearchTests(TestCase):
    def test_explicit_anchor_does_not_require_midnight_session_prefix(self):
        from market_ai.v2.session_research import anchored_vwap
        b=day()[5:]
        r=anchored_vwap(b,timeframe='1m',as_of_ms=b[-1].close_time_ms,max_age_ms=TF,anchor_ms=b[0].open_time_ms)
        self.assertEqual(r['status'],'available')
        self.assertEqual(r['value'],session(day(),anchor_ms=b[0].open_time_ms)['anchored_vwap']['value'])
        self.assertFalse(r['trade_permission'])
    def test_invalid_anchor_gap_fake_volume_and_unfinished_fail_closed(self):
        from market_ai.v2.session_research import anchored_vwap
        b=day()[5:]
        def run(rows,anchor):return anchored_vwap(rows,timeframe='1m',as_of_ms=b[-1].close_time_ms,max_age_ms=TF,anchor_ms=anchor)
        for anchor in (True,b[-1].close_time_ms,b[0].open_time_ms+1,b[-1].open_time_ms):
            self.assertEqual(run(b,anchor)['status'],'unavailable')
        for rows in (b[:3]+b[4:],b[:-1]+[replace(b[-1],is_final=False)],[replace(x,volume_kind='tick') for x in b]):
            self.assertEqual(run(rows,b[0].open_time_ms)['status'],'unavailable')
