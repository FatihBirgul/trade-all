import unittest
from dataclasses import replace
import unified_forex
from unified_forex.market import acquire,MarketFailure
from unified_forex.technical import compute
from forex.core import DataError
from market_ai.v2.market_data_contract import validate_series
from fixtures import fixture,NOW


class MarketContract(unittest.TestCase):
    def test_real_v2_contract_cfd_and_source_owned_snapshot(self):
        p=fixture();view=acquire(p,'XAUUSD','M15',NOW,('H4',))
        f=view.frame('M15')
        self.assertEqual(f.bars[0].instrument.contract_type,'cfd')
        self.assertIn('tick_volume',view.capabilities)
        self.assertNotIn('real_volume',view.capabilities)
        self.assertTrue(validate_series(f.bars,timeframe_ms=f.duration_ms,as_of_ms=f.as_of_ms,max_age_ms=f.duration_ms).ok)
        p.data['XAUUSD']['candles']['M15'][-1]['close']=1
        self.assertNotEqual(view.snapshot.payload()['frames']['M15'][-1]['close'],1)

    def test_data_failure_and_identity_rejection(self):
        for fields in ({'is_final':False},{'time':True},{'source':'foreign'},{'price_kind':'ask'},{'volume_kind':'real','volume':30}):
            p=fixture();p.data['XAUUSD']['candles']['M15'][-1].update(fields)
            with self.assertRaises(DataError):acquire(p,'XAUUSD','M15',NOW,('H4',))
        p=fixture();p.data['XAUUSD']['metadata']['contract_type']='spot'
        with self.assertRaises(MarketFailure):acquire(p,'XAUUSD','M15',NOW,('H4',))

    def test_technical_methods_execute_on_tick_volume(self):
        f=acquire(fixture(),'XAUUSD','M15',NOW,('H4',)).frame('M15');m=compute(f)
        self.assertEqual(m['research_methods']['status'],'available')
        self.assertEqual(m['research_methods']['methods']['adx14_wilder']['status'],'available')
        self.assertIsNotNone(m['rsi14_rolling'])
        self.assertAlmostEqual(m['rsi14_wilder'],100)

    def test_m30_and_lower_trigger_are_asof(self):
        view=acquire(fixture(frames=('M30','H4','M5')),'XAUUSD','M30',NOW,('H4',),'M5')
        self.assertEqual(view.frame('M30').duration_ms,1800000)
        self.assertTrue(all(b.close_time_ms<=NOW*1000 for b in view.frame('M5').bars))

    def test_schedule_provenance_controls_session(self):
        p=fixture();p.data['XAUUSD']['metadata']['broker_hours_verified']=False
        view=acquire(p,'XAUUSD','M15',NOW,('H4',))
        self.assertEqual(view.session()['broker']['status'],'UNKNOWN')
        self.assertNotIn('broker_calendar',view.capabilities)

    def test_explicit_contract_provider_and_interval_mismatches_are_rejected(self):
        for fields in ({'contract_type':'future'},{'market_type':'crypto_spot'},{'close_time_utc':NOW+900}):
            p=fixture();p.data['XAUUSD']['candles']['M15'][-1].update(fields)
            with self.assertRaises(DataError):acquire(p,'XAUUSD','M15',NOW,('H4',))
        p=fixture();p.data['XAUUSD']['quote']['provider']='foreign'
        with self.assertRaisesRegex(DataError,'provider identity'):acquire(p,'XAUUSD','M15',NOW,('H4',))
