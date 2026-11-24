import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone,timedelta
from unittest.mock import patch,Mock
from fixtures import fixture,multi_fixture,NOW
from unified_forex.engine import AnalysisEngine
from unified_forex.services import Alerts,scan
from unified_forex.diagnostics import diagnose
from unified_forex.macro import RevisedEvent,RevisionCalendar,information_context,parse_bls_ical,event_window
from unified_forex.strategies import Parameters,assess
from unified_forex.market import acquire
from unified_forex.technical import compute


class Operations(unittest.TestCase):
    def test_scanner_isolates_one_disconnected_symbol_and_provider_cache(self):
        p=multi_fixture();original=p.quote
        def quote(symbol):
            if symbol=='EURUSD':raise RuntimeError('private terminal detail')
            return original(symbol)
        with patch.object(p,'quote',side_effect=quote):
            reports=scan(p,('XAUUSD','EURUSD'),('M15',),now=NOW)['results']
        by={r['symbol']:r for r in reports}
        self.assertEqual(by['XAUUSD']['data_status'],'OK')
        self.assertEqual(by['EURUSD']['final_decision'],'PROVIDER_UNAVAILABLE')
        self.assertNotIn('private terminal detail',str(reports))
        other=fixture('SELL')
        self.assertEqual(scan(other,('XAUUSD',),now=NOW)['results'][0]['legacy_signal'],'SELL')

    def test_alert_same_setup_after_cooldown_concurrency_and_invalidation(self):
        p=fixture();r=AnalysisEngine().analyze(p,'XAUUSD',now=NOW)
        alerts=Alerts(cooldown_seconds=1);now=datetime.fromtimestamp(NOW,timezone.utc)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:alerts.evaluate(r,now=now),range(4)))
        self.assertEqual(sum(e['type']=='SETUP_CONFIRMED' for batch in results for e in batch),1)
        self.assertEqual(alerts.evaluate(r,now=now+timedelta(seconds=2)),[])
        p.data['XAUUSD']['metadata']['max_spread']=.01
        blocked=AnalysisEngine().analyze(p,'XAUUSD',now=NOW)
        events=alerts.evaluate(blocked,now=now+timedelta(seconds=3))
        self.assertIn('SETUP_INVALIDATED',{e['type'] for e in events})
        self.assertTrue(all('severity' in e and 'source_version' in e for e in events))
        self.assertLessEqual(len(alerts.seen),256)

    def test_readonly_diagnostic_enriches_fields_without_execution(self):
        p=fixture();p.health=Mock(return_value={'connected':True})
        r=diagnose(p,('XAUUSD',))
        self.assertFalse(r['execution_permission']);self.assertEqual(r['mt5_validation'],'UNVERIFIED')
        row=r['symbols']['XAUUSD'];self.assertEqual(row['schedule_provenance']['trust'],'DECLARED')
        self.assertEqual(len(row['readonly_profit_samples']),2)
        self.assertTrue(all(s['loss_sign_valid'] and not s['authoritative'] for s in row['readonly_profit_samples']))

    def test_calendar_revisions_are_known_asof_and_window_is_asymmetric(self):
        now=datetime.fromtimestamp(NOW,timezone.utc)
        row=dict(event_id='nfp',source='synthetic',url='https://example.org/nfp',currency='USD',event_type='NFP',
                 importance='HIGH',release_at=now-timedelta(hours=1),published_at=now-timedelta(hours=2),retrieved_at=now-timedelta(hours=2))
        later={**row,'published_at':now+timedelta(hours=1),'retrieved_at':now+timedelta(hours=1),'actual':10,'revision':1}
        p=RevisionCalendar([row,later])
        a=information_context(p,as_of=now);self.assertEqual(a['events'][0]['revision'],0)
        b=information_context(p,as_of=now+timedelta(hours=2));self.assertEqual(b['events'][0]['actual'],10)
        self.assertFalse(b['event_filter_verified'])
        w=event_window(row,10,30)
        self.assertEqual(w['end']-w['start'],timedelta(minutes=40))

    def test_ics_dst_and_malformed_event_do_not_fabricate_coverage(self):
        payload='BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:fixture-cpi\nDTSTAMP:20260301T120000Z\nDTSTART;TZID=America/New_York:20260310T083000\nSUMMARY:Consumer Price Index\nEND:VEVENT\nEND:VCALENDAR'
        now=datetime(2026,3,5,tzinfo=timezone.utc)
        r=parse_bls_ical(payload,retrieved_at=now)
        self.assertEqual(r['events'][0].release_at.hour,12) # DST in New York
        self.assertFalse(r['source_authenticated']);self.assertEqual(r['coverage_status'],'UNVERIFIED')
        bad=payload.replace('20260310T083000','20260308T023000')
        self.assertEqual(parse_bls_ical(bad,retrieved_at=now)['events'],[])
        self.assertTrue(parse_bls_ical(bad,retrieved_at=now)['issues'])
        official_shape=payload.replace('DTSTAMP:20260301T120000Z\n','').replace('America/New_York','US-Eastern')
        e=parse_bls_ical(official_shape,retrieved_at=now)['events'][0]
        self.assertIsNone(e.source_published_at)
        self.assertEqual(e.publication_basis,'FIRST_OBSERVED_RETRIEVAL')
        self.assertEqual(e.published_at,now)
        import httpx
        from unified_forex.macro import fetch_bls_calendar
        with patch('httpx.Client',side_effect=httpx.HTTPError('disconnected')):
            failed=fetch_bls_calendar(as_of=now)
        self.assertEqual(failed['events'],[]);self.assertEqual(failed['data_status'],'DATA_UNAVAILABLE')

    def test_versioned_strategy_parameters_and_duplicate_setup_identity(self):
        p=fixture();engine=AnalysisEngine()
        a=engine.analyze(p,'XAUUSD',now=NOW,strategy_parameters={'max_setup_age_bars':0})
        b=engine.analyze(p,'XAUUSD',now=NOW,strategy_parameters={'max_setup_age_bars':0})
        self.assertEqual([s['setup_id'] for s in a.strategies],[s['setup_id'] for s in b.strategies])
        with self.assertRaises(ValueError):Parameters.model_validate({'max_extension_atr':0})
        f=acquire(p,'XAUUSD','M15',NOW,('H4',)).frame('M15')
        from dataclasses import replace
        f=replace(f,as_of_ms=f.as_of_ms+2*f.duration_ms)
        rows=assess(f,compute(f),{'regime':'trend'},{},parameters={'max_setup_age_bars':0})
        self.assertTrue(all(s['status']=='WAIT' and 'age' in s['reason'] for s in rows))
