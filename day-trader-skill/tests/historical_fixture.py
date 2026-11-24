"""SYNTHETIC_TEST_EVIDENCE. These invented times are NOT Exness evidence."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from forex.historical_sessions import (HistoricalEvidenceStore, SourceReview,
                                       load_historical_evidence)

ORIGINAL = b'SYNTHETIC_TEST_EVIDENCE: invented schedule, not a broker document.\n'
NOW = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)


def window(start, end):
    return {'start_utc': start, 'end_utc': end}


def document(symbol='XAUUSD'):
    start, end = '2026-11-06T00:00:00Z', '2026-11-12T00:00:00Z'
    quotes, trades, close_only, maintenance = [], [], [], []
    for day in (6, 8, 9, 10, 11):
        date = f'2026-11-{day:02d}'
        if day != 8:
            quotes.append(window(date+'T00:00:00Z', date+'T22:00:00Z'))
            trades.append(window(date+'T00:00:00Z', date+'T22:00:00Z'))
        if day != 6:
            next_date = f'2026-11-{day+1:02d}'
            quotes.append(window(date+'T23:00:30Z', next_date+'T00:00:00Z'))
            trades.append(window(date+'T23:02:00Z', next_date+'T00:00:00Z'))
            close_only.append(window(date+'T23:00:30Z', date+'T23:02:00Z'))
        if day in (9, 10, 11):
            maintenance.append(window(date+'T22:00:00Z', date+'T23:00:30Z'))
    return {
        'schema_version': 'broker-historical-sessions-1',
        'evidence_id': 'SYNTHETIC_TEST_EVIDENCE-'+symbol,
        'broker': 'Exness', 'server': 'Exness-MT5Real50', 'product': 'Standard Cent',
        'account_currency': 'USC', 'canonical_symbol': symbol, 'broker_symbol': symbol+'c',
        'source': {'kind': 'SYNTHETIC_TEST_EVIDENCE', 'organization': 'SYNTHETIC_TEST_EVIDENCE',
                   'reference': 'SYNTHETIC_TEST_EVIDENCE: not real broker verification',
                   'original_file': 'original.txt', 'original_sha256': hashlib.sha256(ORIGINAL).hexdigest()},
        'published_at_utc': '2026-11-05T00:00:00Z', 'acquired_at_utc': '2026-11-05T01:00:00Z',
        'effective_start_utc': start, 'effective_end_utc': end, 'source_timezone': 'UTC',
        'conversion_rule': 'EXPLICIT_UTC_WITH_OFFSET_REGIMES',
        'dst_regime': [{**window(start, end), 'offset_seconds': 0}],
        'completeness': {k: 'COMPLETE' for k in ('quote', 'trade', 'calendar', 'timezone')},
        'verification_status': 'FORMAT_VALIDATED', 'operator_review': 'PENDING', 'conflicts': [],
        'coverage': [window(start, end)], 'quote_open': quotes, 'trade_open': trades,
        'close_only': close_only, 'maintenance': maintenance,
        'weekend_closed': [window('2026-11-06T22:00:00Z', '2026-11-08T23:00:30Z')],
        'holidays': [], 'exceptional_closures': []}


def write_candidate(folder, doc=None, name='evidence.json'):
    root = Path(folder)
    (root/'original.txt').write_bytes(ORIGINAL)
    (root/name).write_bytes(json.dumps(doc or document(), sort_keys=True).encode())
    return load_historical_evidence(root, name, now=NOW)


def trusted_store(folder, doc=None):
    candidate = write_candidate(folder, doc)
    reviewed = (datetime.fromisoformat(candidate.document()['acquired_at_utc'].replace('Z','+00:00'))
                + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
    review = SourceReview(candidate.sha256, candidate.document()['source']['original_sha256'],
                          reviewed, 'SYNTHETIC_TEST_EVIDENCE: injected Python review')
    return HistoricalEvidenceStore([candidate], reviews=[review])


def evaluate(store, **changes):
    args = dict(broker='Exness', server='Exness-MT5Real50', product='Standard Cent',
                currency='USC', broker_symbol='XAUUSDc', canonical_symbol='XAUUSD',
                as_of=datetime(2026, 11, 10, 4, tzinfo=timezone.utc).timestamp())
    return store.evaluate(**{**args, **changes})
