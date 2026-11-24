"""Closed-market gaps are checked against trading windows, not UI labels."""
import unittest
from datetime import datetime, timedelta, timezone

from forex.contracts import _bars
from forex.core import DataError
from forex.sessions import broker_interval_closed, broker_status
from forex.unified import unified_analyze
from test_forex import NOW, fixture


def stamp(day, hour, minute=0):
    return int(datetime(2026, 11, day, hour, minute, tzinfo=timezone.utc).timestamp())


def rows_after_break(next_open=stamp(9, 23), previous_open=stamp(9, 21, 45)):
    times = [previous_open - (199-i)*900 for i in range(200)]
    times += [next_open + i*900 for i in range(20)]
    return [dict(time=t, open=100, high=101, low=99, close=100) for t in times]


class ExnessSessionGap(unittest.TestCase):
    def check(self, next_open=stamp(9, 23), hours=None):
        hours = hours if hours is not None else {
            'timezone': 'UTC',
            'weekly': {str(i): [['00:00', '22:00'], ['23:00', '24:00']] for i in range(7)},
        }
        rows = rows_after_break(next_open)
        return _bars(rows, 'M15', rows[-1]['time']+900,
                     {'source': 'fixture', 'broker_hours': hours}, 'XAUUSD', 'fixture')

    def test_opening_soon_is_still_closed_for_verified_gap(self):
        self.assertEqual(len(self.check()), 220)

    def test_gap_overlaps_open_session_is_rejected(self):
        with self.assertRaisesRegex(DataError, 'missing candle'):
            self.check(next_open=stamp(9, 23, 15))

    def test_off_grid_2301_open_is_not_discarded(self):
        policy = {'timezone': 'UTC', 'weekly': {str(i):
                  [['00:00', '22:00'], ['23:01', '24:00']] for i in range(7)}}
        self.assertEqual(len(self.check(next_open=stamp(9, 23, 1), hours=policy)), 220)
        with self.assertRaisesRegex(DataError, 'outside configured broker hours'):
            self.check(next_open=stamp(9, 23), hours=policy)

    def test_bucket_open_precedes_first_quote_with_tick_evidence(self):
        policy = {'timezone': 'UTC', 'weekly': {str(i):
                  [['00:00', '22:00'], ['23:01', '24:00']] for i in range(7)}}
        rows = rows_after_break(next_open=stamp(9, 23))
        rows[200]['tick_volume'] = 1
        parsed = _bars(rows, 'M15', rows[-1]['time'] + 900,
                       {'source': 'fixture', 'quote_hours': policy}, 'XAUUSD', 'fixture')
        self.assertEqual(parsed[200]['open_time_utc'], stamp(9, 23))
        self.assertEqual(parsed[200]['volume_kind'], 'tick')

    def test_quote_bucket_can_be_valid_while_trade_session_is_not_open(self):
        quote = {'timezone': 'UTC', 'weekly': {str(i):
                 [['00:00', '22:00'], ['23:01', '24:00']] for i in range(7)}}
        trade = {'timezone': 'UTC', 'weekly': {str(i):
                 [['00:00', '22:00'], ['23:05', '24:00']] for i in range(7)}}
        rows = rows_after_break()
        rows[200]['tick_volume'] = 1
        _bars(rows, 'M15', rows[-1]['time'] + 900,
              {'source': 'fixture', 'quote_hours': quote, 'broker_hours': trade},
              'XAUUSD', 'fixture')
        at = datetime(2026, 11, 9, 23, 2, tzinfo=timezone.utc)
        self.assertEqual(broker_status(at, 'XAUUSD', True, quote)['status'], 'OPEN')
        self.assertNotEqual(broker_status(at, 'XAUUSD', True, trade)['status'], 'OPEN')

    def test_opening_labels_and_exact_boundaries(self):
        policy = {'timezone': 'UTC', 'weekly': {str(i): [['23:00', '24:00']] for i in range(7)}}
        for minute, label in ((0, 'CLOSED'), (20, 'CLOSED'),
                              (40, 'OPENING_SOON'), (50, 'OPENING_SOON')):
            with self.subTest(minute=minute):
                at = datetime(2026, 11, 9, 22, minute, tzinfo=timezone.utc)
                self.assertEqual(broker_status(at, 'XAUUSD', True, policy)['status'], label)
                self.assertTrue(broker_interval_closed(at, at+timedelta(minutes=1), policy))
        opening = datetime(2026, 11, 9, 23, tzinfo=timezone.utc)
        self.assertFalse(broker_interval_closed(opening-timedelta(minutes=1),
                                                opening+timedelta(minutes=1), policy))

    def test_unknown_holiday_weekend_and_dst(self):
        utc = timezone.utc
        start = datetime(2026, 11, 7, tzinfo=utc)
        weekdays = {'timezone': 'UTC', 'weekly': {str(i): [['00:00', '24:00']] if i<5 else [] for i in range(7)}}
        self.assertTrue(broker_interval_closed(start, start+timedelta(days=2), weekdays))
        self.assertFalse(broker_interval_closed(start, start+timedelta(days=2), None))
        self.assertFalse(broker_interval_closed(start, start+timedelta(days=2),
                                                {'timezone': 'Bad/Zone', 'weekly': {}}))
        holiday = {'timezone': 'UTC', 'weekly': {str(i): [['00:00', '24:00']] if i==0 else [] for i in range(7)},
                   'date_overrides': {'2026-11-09': None}}
        monday = datetime(2026, 11, 9, tzinfo=utc)
        self.assertTrue(broker_interval_closed(monday, monday+timedelta(days=1), holiday))
        policy = {'timezone': 'Europe/London', 'weekly': {str(i): [['02:00', '04:00']] if i==6 else [] for i in range(7)}}
        spring = datetime(2026, 3, 29, 1, tzinfo=utc)
        self.assertTrue(broker_interval_closed(spring-timedelta(hours=1), spring, policy))
        self.assertFalse(broker_interval_closed(spring-timedelta(hours=1),
                                                spring+timedelta(minutes=1), policy))
        fall = datetime(2026, 10, 25, 2, tzinfo=utc)
        self.assertTrue(broker_interval_closed(fall-timedelta(hours=2), fall, policy))
        self.assertFalse(broker_interval_closed(fall-timedelta(hours=2),
                                                fall+timedelta(minutes=1), policy))

    def test_manual_opening_soon_does_not_make_a_plan(self):
        provider = fixture()
        provider.data['XAUUSD']['metadata']['broker_hours'] = {
            'timezone': 'UTC', 'weekly': {'4': [['08:15', '09:00']]}}
        report = unified_analyze(provider, 'XAUUSD', now=NOW, balance=10000)
        self.assertEqual(report.market_status, 'OPENING_SOON')
        self.assertEqual(report.final_decision, 'NO_TRADE')
        self.assertIsNone(report.entry_zone)
        self.assertIsNone(report.lot_size)

    def test_missing_weekday_coverage_is_not_closed_evidence(self):
        start = datetime(2026, 11, 7, tzinfo=timezone.utc)
        partial = {'timezone': 'UTC', 'weekly': {'0': [['00:00', '24:00']]}}
        self.assertFalse(broker_interval_closed(start, start+timedelta(days=1), partial))


if __name__ == '__main__':
    unittest.main()
