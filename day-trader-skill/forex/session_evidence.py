"""Validate a read-only MQL5 session export; never authorize historical gaps.

The MQL5 session functions return a *current weekly* schedule. Their result
cannot establish a past holiday, DST regime, quote outage, or CLOSE_ONLY mode.
This module deliberately has no function that converts the export to
``broker_hours`` for candle acceptance.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from .core import DataError

SCHEMA_VERSION = 'mt5-session-evidence-1'
SOURCE_TYPE = 'MT5_CURRENT_WEEKLY_SCHEDULE'
SYMBOLS = ('XAUUSDc', 'EURUSDc', 'GBPUSDc', 'USDJPYc')
MAX_BYTES = 131_072
MAX_SESSIONS = 64
_SERVER = re.compile(r'[A-Za-z0-9_.-]{1,80}\Z')
_UTC = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z')


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DataError('duplicate session evidence key')
        result[key] = value
    return result


def _keys(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise DataError('invalid session evidence schema')


def _utc(value):
    if not isinstance(value, str) or not _UTC.fullmatch(value):
        raise DataError('invalid collection UTC timestamp')
    try:
        return datetime.fromisoformat(value[:-1] + '+00:00')
    except ValueError as exc:
        raise DataError('invalid collection UTC timestamp') from exc


def _sessions(value, declared_count):
    if (not isinstance(value, list) or len(value) > MAX_SESSIONS
            or type(declared_count) is not int or declared_count != len(value)):
        raise DataError('incomplete session enumeration')
    intervals = []
    for index, item in enumerate(value):
        _keys(item, ('index', 'from_seconds', 'to_seconds'))
        start, end = item['from_seconds'], item['to_seconds']
        if (type(item['index']) is not int or item['index'] != index
                or type(start) is not int or type(end) is not int
                or not 0 <= start < 86400 or not 0 <= end <= 86400):
            raise DataError('invalid session index or time')
        if end <= start:
            end += 86400
        if end - start > 86400:
            raise DataError('invalid session duration')
        intervals.append((start, end))
    ordered = sorted(intervals)
    if any(a[1] > b[0] for a, b in zip(ordered, ordered[1:])):
        raise DataError('conflicting session intervals')
    return intervals


def _weekly_overlap(days, kind):
    """Check cross-midnight overlap, including Saturday into Sunday."""
    intervals = []
    for day in days:
        for start, end in _sessions(day[kind + '_sessions'], day[kind + '_count']):
            intervals.append((day['day_of_week'] * 86400 + start,
                              day['day_of_week'] * 86400 + end))
    intervals.sort()
    if any(a[1] > b[0] for a, b in zip(intervals, intervals[1:])):
        raise DataError('conflicting session intervals')
    if intervals and intervals[-1][1] > 7 * 86400:
        if intervals[-1][1] - 7 * 86400 > intervals[0][0]:
            raise DataError('conflicting session intervals')


def parse_session_evidence(raw, *, expected_server, now=None):
    """Return a safe summary and digest, with no historical approval policy."""
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise DataError('session evidence file exceeds size limit')
    try:
        document = json.loads(raw.decode('utf-8'), object_pairs_hook=_no_duplicates,
                              parse_constant=lambda _: (_ for _ in ()).throw(
                                  DataError('invalid session evidence number')))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise DataError('invalid session evidence encoding or JSON') from exc
    _keys(document, ('schema_version', 'source_type', 'broker_server',
                     'collected_at_utc', 'time_representation',
                     'source_code_version', 'source_functions', 'provenance',
                     'effective_from_utc', 'effective_to_utc', 'symbols'))
    if document['schema_version'] != SCHEMA_VERSION or document['source_type'] != SOURCE_TYPE:
        raise DataError('unsupported session evidence version or source')
    server = document['broker_server']
    if (not isinstance(expected_server, str) or not _SERVER.fullmatch(expected_server)
            or not isinstance(server, str) or server != expected_server):
        raise DataError('broker server identity mismatch')
    if (document['time_representation'] != 'SECONDS_FROM_MIDNIGHT_SERVER_SESSION'
            or document['source_code_version'] != 'mt5-session-export-1'
            or document['source_functions'] != ['SymbolInfoSessionQuote',
                                                'SymbolInfoSessionTrade']
            or document['provenance'] != 'MQL5_SCRIPT_LOCAL_READ_ONLY'
            or document['effective_from_utc'] is not None
            or document['effective_to_utc'] is not None):
        raise DataError('unverified session provenance or effective period')
    collected = _utc(document['collected_at_utc'])
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or collected > now.astimezone(timezone.utc).replace(microsecond=0):
        raise DataError('session evidence collection time is in the future')
    symbols = document['symbols']
    if not isinstance(symbols, list) or len(symbols) != len(SYMBOLS):
        raise DataError('missing session evidence symbol')
    seen = set()
    counts = {}
    for item in symbols:
        _keys(item, ('broker_symbol', 'days'))
        symbol = item['broker_symbol']
        if not isinstance(symbol, str) or symbol not in SYMBOLS or symbol in seen:
            raise DataError('session evidence symbol identity mismatch')
        seen.add(symbol)
        days = item['days']
        if not isinstance(days, list) or len(days) != 7:
            raise DataError('missing session evidence day')
        seen_days = set()
        for day in days:
            _keys(day, ('day_of_week', 'quote_sessions', 'trade_sessions',
                        'quote_count', 'trade_count', 'enumeration_complete'))
            ordinal = day['day_of_week']
            if (type(ordinal) is not int or not 0 <= ordinal <= 6
                    or ordinal in seen_days or day['enumeration_complete'] is not True):
                raise DataError('incomplete session evidence day')
            seen_days.add(ordinal)
            _sessions(day['quote_sessions'], day['quote_count'])
            _sessions(day['trade_sessions'], day['trade_count'])
        if seen_days != set(range(7)):
            raise DataError('missing session evidence day')
        for kind in ('quote', 'trade'):
            _weekly_overlap(days, kind)
        counts[symbol] = {'quote_sessions': sum(d['quote_count'] for d in days),
                          'trade_sessions': sum(d['trade_count'] for d in days)}
    if seen != set(SYMBOLS):
        raise DataError('missing session evidence symbol')
    return {'status': SOURCE_TYPE, 'historical_gap_authorized': False,
            'effective_period': None, 'sha256': hashlib.sha256(raw).hexdigest(),
            'broker_server': server, 'collected_at_utc': document['collected_at_utc'],
            'symbols': counts, 'limitations': [
                'Current weekly windows do not prove the 2026-11-09 schedule',
                'Quote windows do not establish CLOSE_ONLY or holiday history']}


def load_session_evidence(path, *, expected_server, now=None):
    location = Path(path)
    if not location.is_file() or location.stat().st_size > MAX_BYTES:
        raise DataError('session evidence file unavailable or too large')
    return parse_session_evidence(location.read_bytes(), expected_server=expected_server,
                                  now=now)


def assess_session_evidence(raw, *, expected_server, now=None):
    """Give an audit state for rejected data without changing the safety gate."""
    try:
        return parse_session_evidence(raw, expected_server=expected_server, now=now)
    except DataError as exc:
        reason = str(exc)
        status = ('CONFLICTING' if 'conflicting' in reason
                  else 'INCOMPLETE' if 'incomplete' in reason or 'missing' in reason
                  else 'UNVERIFIED')
        return {'status': status, 'historical_gap_authorized': False,
                'reason': reason}


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Validate a local MT5 session export without applying it')
    parser.add_argument('file')
    parser.add_argument('--broker-server', required=True)
    args = parser.parse_args(argv)
    try:
        result = load_session_evidence(args.file, expected_server=args.broker_server)
    except (DataError, OSError) as exc:
        parser.exit(2, f'INVALID: {exc}\n')
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
