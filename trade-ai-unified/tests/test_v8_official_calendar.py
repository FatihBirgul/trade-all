import unittest
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
from fixtures import NOW,fixture
from unified_forex.official_calendar import parse_schedule,parse_official,fetch_official,ScheduleProvider
from unified_forex.macro import information_context
from unified_forex.engine import AnalysisEngine


class OfficialSources(unittest.TestCase):
    def test_all_date_adapters_keep_unknown_release_time_and_source_hash(self):
        now=datetime.fromtimestamp(NOW,timezone.utc)
        cases={
          'fed_calendar':'<h4>2027 FOMC Meetings</h4><div class="fomc-meeting__month">January</div><div class="fomc-meeting__date">26-27</div>',
          'ecb':'<dl><dt>27/01/2027</dt><dd>Governing Council monetary policy meeting (Day 2)</dd></dl>',
          'boe':'<h2>2027 confirmed dates</h2><table><tr><td>Thursday 4 February</td><td>MPC</td></tr></table>',
          'boj':'<h2>2027</h2><table><tr><td>Jan. 21 (Thurs.), 22 (Fri.)</td><td>Report</td></tr></table>'}
        for source,payload in cases.items():
            r=parse_schedule(payload,source,retrieved_at=now)
            self.assertEqual(len(r['events']),1,(source,r))
            e=r['events'][0];self.assertIsNone(e['release_utc']);self.assertIsNone(e['published_utc'])
            self.assertEqual(e['known_at'],e['retrieved_utc']);self.assertEqual(e['time_precision'],'DATE_ONLY')
            self.assertEqual(parse_schedule('schema changed',source,retrieved_at=now)['events'],[])
        extra='<dl><dt>27/01/2027</dt><dd>non-monetary policy meeting</dd></dl>'
        self.assertEqual(parse_schedule(extra,'ecb',retrieved_at=now)['events'],[])
    def test_bea_ics_and_date_only_asof_risk_veto(self):
        now=datetime.fromtimestamp(NOW,timezone.utc)
        ics='BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:synthetic-gdp\nDTSTART;VALUE=DATE-TIME:20270101T133000Z\nSUMMARY:Gross Domestic Product\nEND:VEVENT\nEND:VCALENDAR'
        r=parse_official(ics,'bea',retrieved_at=now)
        self.assertEqual(r['events'][0].event_type,'GDP');self.assertIsNone(r['events'][0].source_published_at)
        stamped=ics.replace('SUMMARY:','DTSTAMP;VALUE=DATE-TIME:20260101T120000Z\nSUMMARY:')
        e=parse_official(stamped,'bea',retrieved_at=now)['events'][0]
        self.assertIsNone(e.source_published_at);self.assertIsNotNone(e.source_record_timestamp)
        self.assertEqual(e.published_at,now) # legacy field is explicitly first knowledge, not source publication
        local=now.date().strftime('%d/%m/%Y')
        payload='<dl><dt>'+local+'</dt><dd>monetary policy meeting</dd></dl>'
        dates=parse_schedule(payload,'ecb',retrieved_at=now-timedelta(hours=1))['events']
        for e in dates:e['currency']='USD';e['source_timezone']='UTC'
        provider=ScheduleProvider(date_only=dates)
        context=information_context(provider,as_of=now)
        self.assertIsNone(context['date_only_events'][0]['release_utc'])
        self.assertEqual(information_context(provider,as_of=now-timedelta(hours=2))['date_only_events'],[])
        a=AnalysisEngine().analyze(fixture(),'XAUUSD',now=NOW,information_provider=provider,macro_event_window_minutes=15)
        self.assertEqual(a.final_decision,'NO_TRADE');self.assertIn('clock unknown',a.decision_reasons[0])
    def test_failure_terms_schema_and_rate_limit_do_not_fallback(self):
        import httpx
        self.assertEqual(fetch_official('boj')['data_status'],'USAGE_REVIEW_REQUIRED')
        with patch('httpx.Client',side_effect=httpx.HTTPError('rate limit')):
            self.assertEqual(fetch_official('ecb',usage_reviewed=True)['events'],[])
        with self.assertRaises(ValueError):fetch_official('https://localhost/secrets',usage_reviewed=True)
        with self.assertRaises(ValueError):parse_schedule('x'*512001,'ecb',retrieved_at=datetime.now(timezone.utc))
