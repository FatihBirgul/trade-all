import unittest
from unittest.mock import patch
from datetime import datetime,timezone,timedelta
from fixtures import fixture,NOW
from unified_forex.engine import AnalysisEngine
from unified_forex.services import scan,Alerts,ingest_news
from forex.macro import SuppliedCalendar


class LocalServices(unittest.TestCase):
    def test_scanner_reuses_reads_and_canonical_reports(self):
        p=fixture(frames=('M15','H4','H1'))
        with patch.object(p,'quote',wraps=p.quote) as quote,patch.object(p,'metadata',wraps=p.metadata) as meta,patch.object(p,'candles',wraps=p.candles) as candles:
            result=scan(p,('XAUUSD',),('M15','H1'),now=NOW)
        self.assertEqual(len(result['results']),2)
        self.assertTrue(all(r['integration_status']=='PRIVATE_INTEGRATED' for r in result['results']))
        self.assertEqual(quote.call_count,1);self.assertEqual(meta.call_count,1);self.assertEqual(candles.call_count,3)
        with self.assertRaises(ValueError):scan(p,('XAUUSD',)*5,('M15',),now=NOW)
    def test_retained_alerts_cooldown_and_no_execution(self):
        p=fixture();r=AnalysisEngine().analyze(p,'XAUUSD',now=NOW)
        alerts=Alerts();a=alerts.evaluate(r);b=alerts.evaluate(r)
        self.assertIn('SETUP_CONFIRMED',{e['type'] for e in a});self.assertEqual(b,[])
        p.data['XAUUSD']['metadata']['max_spread']=.01
        blocked=AnalysisEngine().analyze(p,'XAUUSD',now=NOW)
        self.assertIn('HIGH_SPREAD',{e['type'] for e in alerts.evaluate(blocked)})
    def test_declared_macro_veto_does_not_claim_verified_coverage(self):
        now=datetime.fromtimestamp(NOW,timezone.utc)
        row={'event_id':'fixture-nfp','source':'synthetic-calendar','url':'https://example.org/nfp',
             'published_at':now-timedelta(hours=2),'retrieved_at':now-timedelta(hours=1),'release_at':now+timedelta(minutes=5),
             'currency':'USD','event_type':'NFP','importance':'HIGH'}
        calendar=SuppliedCalendar([row])
        r=AnalysisEngine().analyze(fixture(),'XAUUSD',now=NOW,information_provider=calendar,macro_event_window_minutes=15)
        self.assertEqual(r.final_decision,'NO_TRADE');self.assertIsNone(r.entry_zone)
        self.assertFalse(r.information['event_filter_verified'])
        self.assertIn('HIGH_IMPACT_MACRO',{e['type'] for e in Alerts().evaluate(r)})

    def test_real_retained_news_parser_ingests_source_labelled_rss(self):
        now=datetime.fromtimestamp(NOW,timezone.utc)
        from email.utils import format_datetime
        payload=('<rss><channel><item><title>Federal Reserve FOMC decision</title>'
                 '<link>https://example.org/fomc</link><guid>fixture-fomc</guid><pubDate>'+
                 format_datetime(now-timedelta(hours=1))+'</pubDate></item></channel></rss>')
        result=ingest_news(payload,'synthetic-fixture-rss',now)
        self.assertEqual(len(result['items']),1)
        self.assertIn('retrieved_at',result['items'][0])
        self.assertFalse(result['coverage_verified'])

    def test_four_symbol_scanner_is_bounded_and_explainable(self):
        from fixtures import multi_fixture
        from forex.core import SYMBOLS
        result=scan(multi_fixture(),SYMBOLS,('M15',),now=NOW)
        self.assertEqual(len(result['results']),4)
        self.assertEqual(result['cached_resource_reads'],16)
        self.assertTrue(all(r['data_status']=='OK' for r in result['results']))
