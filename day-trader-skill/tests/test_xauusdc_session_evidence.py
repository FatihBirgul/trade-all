"""9 Nov XAUUSDc timestamps are observations, never a session declaration."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from forex.contracts import _bars
from forex.core import DataError, validate_bars
from forex.providers import MT5Provider
from forex.sessions import broker_interval_closed, broker_status
from test_exness_cent import CentTerminal
from test_exness_session_gap import rows_after_break
from test_real_readonly import RealTerminal


def utc(hour, minute=0, second=0, millisecond=0):
    return datetime(2026, 11, 9, hour, minute, second, millisecond*1000,
                    tzinfo=timezone.utc)


class XauCentSessionEvidence(unittest.TestCase):
    def test_m1_m15_and_tick_times_do_not_prove_session(self):
        last_m1=utc(21,57)
        next_m1=utc(23,0)
        ticks=(utc(23,0,30,141),utc(23,1,0,199),utc(23,2,0,115))
        m15_open=utc(23,0)
        self.assertEqual((next_m1-last_m1).total_seconds(),63*60)
        self.assertEqual((next_m1-(last_m1+timedelta(minutes=1))).total_seconds(),62*60)
        self.assertTrue(all(t >= m15_open for t in ticks))
        self.assertTrue(all(t < m15_open.replace(minute=15) for t in ticks))
        self.assertEqual(ticks[0].microsecond,141000)
        self.assertFalse(broker_interval_closed(last_m1.replace(minute=58),next_m1,None))
        self.assertEqual(broker_status(utc(22,30),'XAUUSDc',True,None)['status'],'UNKNOWN')
        rows=rows_after_break()
        with self.assertRaisesRegex(DataError,'missing candle without verified broker hours'):
            _bars(rows,'M15',rows[-1]['time']+900,{'source':'fixture'},
                  'XAUUSD','fixture')

    def test_2300_m15_is_unfinished_at_observed_ticks(self):
        bar={'time':int(utc(23,0).timestamp()),'open':100,'high':101,'low':99,'close':100}
        for tick in (utc(23,0,30,141),utc(23,1,0,199),utc(23,2,0,115)):
            with self.subTest(tick=tick), self.assertRaisesRegex(DataError,'closed'):
                validate_bars([bar],'M15',tick.timestamp())

    def test_missing_buckets_and_first_tick_delay_are_distinct(self):
        missing_m1 = [utc(21,58)+timedelta(minutes=i) for i in range(62)]
        missing_m15 = [utc(22,0)+timedelta(minutes=15*i) for i in range(4)]
        self.assertEqual((missing_m1[0],missing_m1[-1]),(utc(21,58),utc(22,59)))
        self.assertEqual(missing_m15,[utc(22,0),utc(22,15),utc(22,30),utc(22,45)])
        first_tick = utc(23,0,30,141)
        self.assertEqual((first_tick-utc(23,0)).total_seconds(),30.141)
        self.assertLess(first_tick,utc(23,15))
        self.assertEqual((utc(23,1,0,199)-utc(23,1)).total_seconds(),.199)
        self.assertEqual((utc(23,2,0,115)-utc(23,2)).total_seconds(),.115)

    def test_xauusd_schedule_cannot_be_reused_for_xauusdc(self):
        declared={'broker_symbol':'XAUUSD','timezone':'UTC',
                  'weekly':{str(i):[] for i in range(7)}}
        demo=MT5Provider(CentTerminal(),{'XAUUSD':'XAUUSDc'})
        demo.hours={'XAUUSD':declared}
        self.assertIsNone(demo.metadata('XAUUSD')['broker_hours'])
        declared['broker_symbol']='XAUUSDc'
        self.assertEqual(demo.metadata('XAUUSD')['broker_hours_status'],'OPERATOR_DECLARED')

        provider=MT5Provider(RealTerminal(),{'XAUUSD':'XAUUSDc'})
        provider.hours={'XAUUSD': {'broker_symbol':'XAUUSD','timezone':'UTC',
                                   'weekly':{str(i):[] for i in range(7)}}}
        provider.account_preflight('REAL_READONLY_DATA','Real-Server','USC')
        meta=provider.metadata('XAUUSD')
        self.assertIsNone(meta['broker_hours'])
        self.assertEqual(meta['broker_hours_status'],'UNVERIFIED_REAL_SESSION')
        provider.hours['XAUUSD']['broker_symbol']='XAUUSDc'
        meta=provider.metadata('XAUUSD')
        self.assertIsNone(meta['broker_hours'])
        self.assertEqual(meta['broker_hours_status'],'UNVERIFIED_REAL_SESSION')
        with self.assertRaisesRegex(DataError,'missing candle without verified broker hours'):
            rows=rows_after_break()
            _bars(rows,'M15',rows[-1]['time']+900,meta,'XAUUSD',provider.name)

    def test_close_only_quotes_remain_readable_without_new_position(self):
        class CloseOnlyTerminal(RealTerminal):
            tick_ms=0
            def symbol_info(self,symbol):
                info=super().symbol_info(symbol)
                info.trade_mode=3  # MT5 CLOSE_ONLY symbol trade mode.
                return info
            def symbol_info_tick(self,symbol):
                return SimpleNamespace(bid=100.0,ask=100.1,time_msc=self.tick_ms)
        terminal=CloseOnlyTerminal()
        provider=MT5Provider(terminal,{'XAUUSD':'XAUUSDc'})
        provider.account_preflight('REAL_READONLY_DATA','Real-Server','USC')
        meta=provider.metadata('XAUUSD')
        self.assertEqual(meta['allowed_directions'],[])
        self.assertFalse(meta['trade_allowed'])
        self.assertEqual(broker_status(utc(23,1),'XAUUSDc',meta['trade_allowed'],
                                       meta['broker_hours'])['status'],'DISABLED')
        with patch('forex.providers.datetime') as clock:
            clock.now.return_value=utc(23,2,1)
            for observed in (utc(23,0,30,141),utc(23,1,0,199),utc(23,2,0,115)):
                terminal.tick_ms=int(observed.timestamp()*1000)
                quote=provider.quote('XAUUSD')
                self.assertEqual(quote['freshness'],'FRESH')
                self.assertAlmostEqual(quote['time'],observed.timestamp(),places=3)
        self.assertEqual(terminal.mutations,[])


if __name__=='__main__': unittest.main()
