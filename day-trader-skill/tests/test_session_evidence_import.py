"""Hostile import cases must never authorize historical candle gaps."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import unittest

from forex.core import DataError
from forex.session_evidence import (parse_session_evidence, assess_session_evidence,
                                    SYMBOLS, MAX_BYTES)


NOW = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)


def document():
    symbols = []
    for symbol in SYMBOLS:
        days = []
        for day in range(7):
            session = [{'index': 0, 'from_seconds': 60, 'to_seconds': 82800}]
            quote = copy.deepcopy(session) if day in range(1, 6) else []
            trade = copy.deepcopy(session) if day in range(1, 6) else []
            days.append({'day_of_week': day, 'quote_sessions': quote,
                         'trade_sessions': trade, 'quote_count': len(quote),
                         'trade_count': len(trade), 'enumeration_complete': True})
        symbols.append({'broker_symbol': symbol, 'days': days})
    return {'schema_version': 'mt5-session-evidence-1',
            'source_type': 'MT5_CURRENT_WEEKLY_SCHEDULE',
            'broker_server': 'Exness-MT5Real50',
            'collected_at_utc': '2026-11-10T10:00:00Z',
            'time_representation': 'SECONDS_FROM_MIDNIGHT_SERVER_SESSION',
            'source_code_version': 'mt5-session-export-1',
            'source_functions': ['SymbolInfoSessionQuote', 'SymbolInfoSessionTrade'],
            'provenance': 'MQL5_SCRIPT_LOCAL_READ_ONLY',
            'effective_from_utc': None, 'effective_to_utc': None,
            'symbols': symbols}


def validate(value):
    return parse_session_evidence(json.dumps(value).encode('utf-8'),
                                  expected_server='Exness-MT5Real50', now=NOW)


class SessionEvidenceImport(unittest.TestCase):
    def test_exporter_has_one_shot_entry_and_no_trade_or_terminal_mutation(self):
        source = (Path(__file__).resolve().parents[1] / 'tools' /
                  'mt5_session_export' / 'MT5SessionExport.mq5').read_text(encoding='utf-8')
        code = '\n'.join(line for line in source.splitlines()
                         if not line.lstrip().startswith('//'))
        self.assertEqual(len(re.findall(r'\bvoid\s+OnStart\s*\(', code)), 1)
        for forbidden in ('OnTick', 'OrderSend', 'OrderCheck', 'SymbolSelect',
                          'AccountInfoDouble', 'ACCOUNT_LOGIN', 'TerminalInfoString'):
            with self.subTest(forbidden=forbidden):
                self.assertNotRegex(code, r'\b' + forbidden + r'\b')

    def test_valid_current_weekly_is_not_historical_approval(self):
        result = validate(document())
        self.assertEqual(result['status'], 'MT5_CURRENT_WEEKLY_SCHEDULE')
        self.assertFalse(result['historical_gap_authorized'])
        self.assertIsNone(result['effective_period'])
        self.assertEqual(len(result['sha256']), 64)
        self.assertEqual(set(result['symbols']), set(SYMBOLS))

    def test_rejection_states_do_not_authorize_historical_gaps(self):
        value = document()
        value['symbols'][0]['days'].pop()
        incomplete = assess_session_evidence(json.dumps(value).encode(),
            expected_server='Exness-MT5Real50', now=NOW)
        self.assertEqual(incomplete['status'], 'INCOMPLETE')
        self.assertFalse(incomplete['historical_gap_authorized'])
        value = document()
        day = value['symbols'][0]['days'][1]
        day['quote_sessions'].append({'index': 1, 'from_seconds': 80000,
                                      'to_seconds': 85000})
        day['quote_count'] = 2
        conflicting = assess_session_evidence(json.dumps(value).encode(),
            expected_server='Exness-MT5Real50', now=NOW)
        self.assertEqual(conflicting['status'], 'CONFLICTING')
        self.assertFalse(conflicting['historical_gap_authorized'])

    def test_duplicate_key_and_oversized_file(self):
        raw = json.dumps(document()).encode()
        with self.assertRaisesRegex(DataError, 'duplicate'):
            parse_session_evidence(raw.replace(b'"schema_version":',
                b'"schema_version":"fake","schema_version":', 1),
                expected_server='Exness-MT5Real50', now=NOW)
        with self.assertRaisesRegex(DataError, 'size limit'):
            parse_session_evidence(b' '* (MAX_BYTES+1),
                                   expected_server='Exness-MT5Real50', now=NOW)

    def test_wrong_server_symbol_and_extra_personal_field(self):
        value = document()
        with self.assertRaisesRegex(DataError, 'server identity'):
            parse_session_evidence(json.dumps(value).encode(),
                                   expected_server='Other-Server', now=NOW)
        value['symbols'][0]['broker_symbol'] = 'XAUUSD'
        with self.assertRaisesRegex(DataError, 'symbol identity'):
            validate(value)
        value['symbols'][0]['broker_symbol'] = {'name': 'XAUUSDc'}
        with self.assertRaisesRegex(DataError, 'symbol identity'):
            validate(value)
        value = document()
        value['account_login'] = 123
        with self.assertRaisesRegex(DataError, 'schema'):
            validate(value)

    def test_missing_day_bad_count_or_index_and_incomplete_enumeration(self):
        for mutation in ('day', 'count', 'index', 'incomplete'):
            value = document()
            days = value['symbols'][0]['days']
            if mutation == 'day': days.pop()
            if mutation == 'count': days[1]['quote_count'] = 2
            if mutation == 'index': days[1]['quote_sessions'][0]['index'] = 1
            if mutation == 'incomplete': days[1]['enumeration_complete'] = False
            with self.subTest(mutation=mutation), self.assertRaises(DataError):
                validate(value)

    def test_conflicting_intervals_and_cross_midnight_overlap(self):
        value = document()
        day = value['symbols'][0]['days'][1]
        day['quote_sessions'].append({'index': 1, 'from_seconds': 80000,
                                      'to_seconds': 85000})
        day['quote_count'] = 2
        with self.assertRaisesRegex(DataError, 'conflicting'):
            validate(value)
        value = document()
        day = value['symbols'][0]['days'][1]
        day['quote_sessions'] = [{'index': 0, 'from_seconds': 82000,
                                  'to_seconds': 1000}]
        next_day = value['symbols'][0]['days'][2]
        next_day['quote_sessions'][0]['from_seconds'] = 500
        with self.assertRaisesRegex(DataError, 'conflicting'):
            validate(value)

    def test_historical_effective_date_and_timezone_cannot_be_forged(self):
        value = document()
        value['effective_from_utc'] = '2026-11-09T00:00:00Z'
        value['effective_to_utc'] = '2026-11-10T00:00:00Z'
        with self.assertRaisesRegex(DataError, 'effective period'):
            validate(value)
        value = document()
        value['time_representation'] = 'Europe/London'
        with self.assertRaisesRegex(DataError, 'provenance'):
            validate(value)
        value = document()
        value['collected_at_utc'] = '2026-11-10T10:00:00+03:00'
        with self.assertRaisesRegex(DataError, 'UTC'):
            validate(value)

    def test_future_collection_and_unknown_source(self):
        value = document()
        value['collected_at_utc'] = '2026-11-11T10:00:00Z'
        with self.assertRaisesRegex(DataError, 'future'):
            validate(value)
        value = document()
        value['source_type'] = 'OFFICIAL_SYMBOL_SPECIFIC'
        with self.assertRaisesRegex(DataError, 'unsupported'):
            validate(value)

    def test_boolean_seconds_and_nonfinite_number_rejected(self):
        value = document()
        value['symbols'][0]['days'][1]['quote_sessions'][0]['from_seconds'] = True
        with self.assertRaisesRegex(DataError, 'index or time'):
            validate(value)
        raw = json.dumps(document()).replace('"from_seconds": 60',
                                              '"from_seconds": NaN', 1).encode()
        with self.assertRaisesRegex(DataError, 'number'):
            parse_session_evidence(raw, expected_server='Exness-MT5Real50', now=NOW)


if __name__ == '__main__':
    unittest.main()
