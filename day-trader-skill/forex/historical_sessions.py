"""Dated quote evidence, with a separate deployment-owned source review gate.

JSON is data, never an approval authority. Production reviews are deliberately
empty until original broker documents are independently authenticated. Tests
inject immutable reviews in Python; neither API nor environment accepts them.
All intervals use [start, end), with second precision and explicit date coverage.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .core import DataError, SYMBOLS
from .session_evidence import _keys, _no_duplicates, _utc

SCHEMA = 'broker-historical-sessions-1'
MAX_BYTES = 262_144
MAX_INTERVALS = 2048
MAX_DOCUMENT_BYTES = 8_388_608
MAX_RECORDS = 32
STATES = ('SOURCE_NOT_SUPPLIED', 'FORMAT_VALIDATED', 'OPERATOR_DECLARED',
          'CURRENT_WEEKLY_ONLY', 'HISTORICAL_SCOPE_INCOMPLETE',
          'HISTORICAL_SOURCE_VERIFIED', 'CONFLICTING_EVIDENCE', 'REJECTED')
KINDS = ('quote_open', 'trade_open', 'close_only', 'maintenance',
         'weekend_closed', 'holidays', 'exceptional_closures')
_HASH = re.compile(r'[0-9a-f]{64}\Z')
_ID = re.compile(r'[A-Za-z0-9_.-]{1,100}\Z')


def utc(value):
    return _utc(value).timestamp()


def local_to_utc(value, zone, *, fold=None):
    """Resolve source local times; reject nonexistent or unresolved fold times."""
    try:
        local = datetime.fromisoformat(value)
        if local.tzinfo is not None:
            raise ValueError()
        tz = ZoneInfo(zone)
        possible = []
        for choice in (0, 1):
            aware = local.replace(tzinfo=tz, fold=choice)
            converted = aware.astimezone(timezone.utc)
            if converted.astimezone(tz).replace(tzinfo=None) == local:
                possible.append((choice, converted))
        if not possible:
            raise DataError('nonexistent source local time')
        if len({stamp for _, stamp in possible}) > 1 and fold is None:
            raise DataError('ambiguous source local time requires fold')
        if fold is not None and (type(fold) is not int or fold not in (0, 1)):
            raise DataError('invalid source local fold')
        return next(stamp for choice, stamp in possible if fold is None or choice == fold)
    except DataError:
        raise
    except (ValueError, TypeError, ZoneInfoNotFoundError, StopIteration) as exc:
        raise DataError('invalid source local time or timezone') from exc


def _text(value, name, maximum=256):
    if (not isinstance(value, str) or not 1 <= len(value) <= maximum
            or any(ord(c) < 32 for c in value)):
        raise DataError('invalid historical ' + name)


def _intervals(items, lower, upper):
    if not isinstance(items, list) or len(items) > MAX_INTERVALS:
        raise DataError('historical interval count exceeds limit')
    intervals = []
    for item in items:
        _keys(item, ('start_utc', 'end_utc'))
        start, end = utc(item['start_utc']), utc(item['end_utc'])
        if not lower <= start < end <= upper:
            raise DataError('historical interval outside effective scope')
        intervals.append((start, end))
    intervals.sort()
    if any(a[1] > b[0] for a, b in zip(intervals, intervals[1:])):
        raise DataError('duplicate or overlapping historical intervals')
    return tuple(intervals)


def _overlap(left, right):
    left, right = sorted(left), sorted(right)
    i = j = 0
    while i < len(left) and j < len(right):
        a, b = left[i]
        c, d = right[j]
        if a < d and c < b:
            return True
        if b <= d:
            i += 1
        else:
            j += 1
    return False


@dataclass(frozen=True)
class Candidate:
    sha256: str
    payload_json: str
    original_checked: bool = False

    def document(self):
        return json.loads(self.payload_json)


def parse_historical_evidence(raw, *, now=None):
    """Strict syntax validation only. Returns no trusted schedule capability."""
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise DataError('historical evidence exceeds size limit')
    try:
        doc = json.loads(raw.decode('utf-8'), object_pairs_hook=_no_duplicates,
                         parse_constant=lambda _: (_ for _ in ()).throw(DataError('invalid JSON number')))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise DataError('invalid historical evidence JSON') from exc
    _keys(doc, ('schema_version', 'evidence_id', 'broker', 'server', 'product',
                'account_currency', 'broker_symbol', 'canonical_symbol', 'source',
                'published_at_utc', 'acquired_at_utc', 'effective_start_utc',
                'effective_end_utc', 'source_timezone', 'conversion_rule', 'dst_regime',
                'completeness', 'verification_status', 'operator_review', 'conflicts',
                'coverage', *KINDS))
    if doc['schema_version'] != SCHEMA:
        raise DataError('unsupported historical schema')
    for key in ('evidence_id', 'server', 'broker_symbol'):
        if not isinstance(doc[key], str) or not _ID.fullmatch(doc[key]):
            raise DataError('invalid historical identity')
    for key in ('broker', 'product', 'account_currency'):
        _text(doc[key], key)
    if doc['canonical_symbol'] not in SYMBOLS:
        raise DataError('unsupported historical canonical symbol')
    if doc['broker_symbol'] != doc['canonical_symbol'] + 'c':
        raise DataError('historical exact Cent symbol mismatch')
    source = doc['source']
    _keys(source, ('kind', 'organization', 'reference', 'original_file', 'original_sha256'))
    if source['kind'] not in ('BROKER_HISTORICAL_DOCUMENT', 'SYNTHETIC_TEST_EVIDENCE',
                               'OPERATOR_DECLARED', 'CURRENT_WEEKLY_ONLY'):
        raise DataError('unsupported historical source kind')
    for key in ('organization', 'reference', 'original_file'):
        _text(source[key], 'source ' + key)
    if not isinstance(source['original_sha256'], str) or not _HASH.fullmatch(source['original_sha256']):
        raise DataError('invalid original document hash')
    lower, upper = utc(doc['effective_start_utc']), utc(doc['effective_end_utc'])
    published, acquired = utc(doc['published_at_utc']), utc(doc['acquired_at_utc'])
    current = (now or datetime.now(timezone.utc))
    if current.tzinfo is None or current.utcoffset() is None:
        raise DataError('aware evidence acquisition clock required')
    if lower >= upper or upper - lower > 366 * 86400:
        raise DataError('invalid historical effective range')
    if published > acquired or acquired > current.timestamp():
        raise DataError('future or inconsistent evidence acquisition')
    try:
        ZoneInfo(doc['source_timezone'])
    except (ZoneInfoNotFoundError, TypeError, ValueError) as exc:
        raise DataError('invalid historical source timezone') from exc
    if doc['conversion_rule'] != 'EXPLICIT_UTC_WITH_OFFSET_REGIMES':
        raise DataError('unsupported historical timezone conversion')
    regimes = doc['dst_regime']
    if not isinstance(regimes, list) or not 1 <= len(regimes) <= 32:
        raise DataError('invalid historical DST regimes')
    regime_spans = []
    for regime in regimes:
        _keys(regime, ('start_utc', 'end_utc', 'offset_seconds'))
        a, b = utc(regime['start_utc']), utc(regime['end_utc'])
        offset = regime['offset_seconds']
        if (not lower <= a < b <= upper or type(offset) is not int
                or not -50400 <= offset <= 50400):
            raise DataError('invalid historical DST regime')
        # Both sides of every explicit boundary, plus hourly probes throughout
        # the dated regime, must agree with installed IANA timezone rules.
        probes = [a, b - 1] + list(range(int(a), int(b), 3600))
        if any(datetime.fromtimestamp(t, timezone.utc).astimezone(
                ZoneInfo(doc['source_timezone'])).utcoffset().total_seconds() != offset for t in probes):
            raise DataError('historical DST offset mismatch')
        regime_spans.append((a, b))
    regime_spans.sort()
    if (any(a[1] != b[0] for a, b in zip(regime_spans, regime_spans[1:]))
            or regime_spans[0][0] != lower or regime_spans[-1][1] != upper):
        raise DataError('incomplete or overlapping historical DST regimes')
    if doc['verification_status'] not in STATES or doc['operator_review'] not in ('PENDING', 'APPROVED', 'REJECTED'):
        raise DataError('invalid historical review state')
    _keys(doc['completeness'], ('quote', 'trade', 'calendar', 'timezone'))
    if any(v not in ('COMPLETE', 'INCOMPLETE') for v in doc['completeness'].values()):
        raise DataError('invalid historical completeness')
    if (not isinstance(doc['conflicts'], list) or len(doc['conflicts']) > 16
            or any(not isinstance(c, str) or len(c) > 256 for c in doc['conflicts'])):
        raise DataError('invalid historical conflicts')
    coverage = _intervals(doc['coverage'], lower, upper)
    windows = {kind: _intervals(doc[kind], lower, upper) for kind in KINDS}
    if sum(len(doc[kind]) for kind in (*KINDS, 'coverage')) > MAX_INTERVALS:
        raise DataError('historical interval count exceeds limit')
    for kind, spans in windows.items():
        if any(not _covered(a, b, coverage) for a, b in spans):
            raise DataError('historical interval lacks explicit coverage')
    if (doc['completeness']['quote'] == doc['completeness']['trade'] == 'COMPLETE'
            and any(not _covered(a, b, windows['quote_open']) for a, b in windows['trade_open'])):
        raise DataError('historical trade-open outside proven quote availability')
    if (_overlap(windows['trade_open'], windows['close_only'])
            or any(_overlap(windows['quote_open'], windows[k]) for k in
                   ('maintenance', 'weekend_closed', 'holidays', 'exceptional_closures'))):
        raise DataError('conflicting historical quote/trade windows')
    # Trade-only sources must mark completeness INCOMPLETE; a fully closed
    # day legitimately has no quote_open entries and is explicit via coverage.
    return Candidate(hashlib.sha256(raw).hexdigest(), json.dumps(doc, sort_keys=True))


def _covered(start, end, spans):
    cursor = start
    for a, b in spans:
        if a > cursor:
            break
        cursor = max(cursor, b)
        if cursor >= end:
            return True
    return False


def _read_local(root, relative, limit):
    """Reject links/reparse points, escapes and special files before bounded I/O.

    The allowlisted directory must be operator-owned, not writable by untrusted
    concurrent processes. It is never inferred from an uploaded file's path.
    """
    try:
        base = Path(root).resolve(strict=True)
        part = Path(relative)
        if (part.is_absolute() or part.drive or part.root or not part.parts
                or any(p in ('.', '..') or ':' in p for p in part.parts)):
            raise DataError('historical evidence path refused')
        location = base
        for component in part.parts:
            location = location / component
            info = location.lstat()
            if (stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400):
                raise DataError('historical evidence link refused')
        location.resolve(strict=True).relative_to(base)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit or info.st_nlink != 1:
            raise DataError('historical evidence file refused')
        with location.open('rb') as handle:
            opened = os.fstat(handle.fileno())
            if (opened.st_ino, opened.st_dev) != (info.st_ino, info.st_dev):
                raise DataError('historical evidence file changed during import')
            raw = handle.read(limit + 1)
        if len(raw) > limit:
            raise DataError('historical evidence exceeds size limit')
        return raw
    except (OSError, ValueError, TypeError) as exc:
        raise DataError('historical evidence local file refused') from exc


def load_historical_evidence(root, relative, *, now=None):
    candidate = parse_historical_evidence(_read_local(root, relative, MAX_BYTES), now=now)
    source = candidate.document()['source']
    original = _read_local(root, source['original_file'], MAX_DOCUMENT_BYTES)
    if hashlib.sha256(original).hexdigest() != source['original_sha256']:
        raise DataError('historical original document hash mismatch')
    return Candidate(candidate.sha256, candidate.payload_json, True)


@dataclass(frozen=True)
class SourceReview:
    """Deployment-owned attestation, never parsed from evidence or API input.

    Digest pins *all* scope, source identity, timezone and holiday assertions.
    Authenticity must be checked independently before adding a production pin.
    """
    evidence_sha256: str
    original_sha256: str
    reviewed_at_utc: str
    review_reference: str


# No real Exness documents have been supplied. Changes require source review,
# tests and a separately authorized deployment, not a JSON approval switch.
PRODUCTION_REVIEWS: tuple[SourceReview, ...] = ()


@dataclass(frozen=True)
class HistoricalPolicy:
    records: tuple[str, ...]
    summary_json: str

    def summary(self):
        return json.loads(self.summary_json)

    def _spans(self, kind):
        return tuple(sorted((utc(s['start_utc']), utc(s['end_utc']))
                            for raw in self.records for s in json.loads(raw)[kind]))

    def covered(self, start, end):
        return (start < end <= self.summary()['decision_as_of_utc']
                and _covered(start, end, self._spans('coverage')))

    def quote_closed(self, start, end):
        return self.covered(start, end) and not _overlap(((start, end),), self._spans('quote_open'))

    def quote_present(self, start, end):
        return self.covered(start, end) and _overlap(((start, end),), self._spans('quote_open'))

    def trade_hours(self):
        # Dated second-resolution policy. Never converted into recurring hours.
        return {'kind': 'VERIFIED_HISTORICAL_TRADE',
                'coverage': tuple(sorted((utc(s['start_utc']), utc(s['end_utc']))
                                        for raw in self.records for d in [json.loads(raw)]
                                        if d['completeness']['trade'] == 'COMPLETE' for s in d['coverage'])),
                'open': tuple(sorted((utc(s['start_utc']), utc(s['end_utc']))
                                    for raw in self.records for d in [json.loads(raw)]
                                    if d['completeness']['trade'] == 'COMPLETE' for s in d['trade_open'])),
                'close_only': self._spans('close_only')}


class HistoricalEvidenceStore:
    def __init__(self, candidates=(), *, reviews=None):
        self.candidates = tuple(candidates)
        self.reviews = tuple(PRODUCTION_REVIEWS if reviews is None else reviews)
        self._injected_reviews = reviews is not None
        if len(self.candidates) > MAX_RECORDS:
            raise DataError('too many historical evidence records')

    def evaluate(self, *, broker, server, product, currency, broker_symbol,
                 canonical_symbol, as_of, knowledge_as_of=None, retrospective=False):
        """Replay defaults to knowledge available then; retrospective is explicit.

        Retrospective capability is only for reconciliation tools. Providers do
        not expose it, so later retrieval/review cannot approve an old decision.
        """
        knowledge = as_of if knowledge_as_of is None else knowledge_as_of
        if not retrospective and knowledge > as_of:
            raise DataError('historical look-ahead refused')
        matched, states, stages, reconciliation = [], [], [], []
        for candidate in self.candidates:
            doc = candidate.document()
            state = 'FORMAT_VALIDATED'
            scope = (doc['broker'], doc['server'], doc['product'], doc['account_currency'],
                     doc['broker_symbol'], doc['canonical_symbol']) == (
                         broker, server, product, currency, broker_symbol, canonical_symbol)
            review = next((r for r in self.reviews if
                           r.evidence_sha256 == candidate.sha256 and
                           r.original_sha256 == doc['source']['original_sha256'] and
                           r.review_reference and utc(doc['acquired_at_utc']) <=
                           utc(r.reviewed_at_utc) <= knowledge), None)
            if doc['source']['kind'] == 'SYNTHETIC_TEST_EVIDENCE' and not self._injected_reviews:
                review = None
            known = max(utc(doc['published_at_utc']), utc(doc['acquired_at_utc'])) <= knowledge
            if (scope and known and candidate.original_checked
                    and doc['source']['kind'] in ('BROKER_HISTORICAL_DOCUMENT', 'SYNTHETIC_TEST_EVIDENCE')
                    and doc['verification_status'] != 'REJECTED'
                    and doc['operator_review'] != 'REJECTED'):
                reconciliation.append(doc)
            if doc['source']['kind'] == 'CURRENT_WEEKLY_ONLY' or doc['verification_status'] == 'CURRENT_WEEKLY_ONLY':
                state = 'CURRENT_WEEKLY_ONLY'
            elif doc['source']['kind'] == 'OPERATOR_DECLARED' or doc['verification_status'] == 'OPERATOR_DECLARED':
                state = 'OPERATOR_DECLARED'
            elif doc['verification_status'] == 'REJECTED' or doc['operator_review'] == 'REJECTED':
                state = 'REJECTED'
            elif doc['conflicts'] or doc['verification_status'] == 'CONFLICTING_EVIDENCE':
                state = 'CONFLICTING_EVIDENCE'
            elif (doc['verification_status'] in ('SOURCE_NOT_SUPPLIED', 'HISTORICAL_SCOPE_INCOMPLETE')
                  or not scope or not doc['coverage'] or any(
                    doc['completeness'][k] != 'COMPLETE' for k in ('quote', 'calendar', 'timezone'))):
                state = 'HISTORICAL_SCOPE_INCOMPLETE'
            elif review and candidate.original_checked and known:
                state = 'HISTORICAL_SOURCE_VERIFIED'
                matched.append(doc)
            stages.append({'evidence_sha256': candidate.sha256, 'file_received': True,
                           'schema_validated': True, 'original_hash_checked': candidate.original_checked,
                           'source_identity_checked': review is not None,
                           'instrument_scope_checked': scope, 'historical_dates_known': known,
                           'intervals_checked': True, 'operator_reviewed': review is not None,
                           'state': state})
            # A mismatching record cannot approve; it must not revoke unrelated
            # symbol evidence. Conflicting matching declarations always block.
            if scope:
                states.append(state)
        conflict = 'CONFLICTING_EVIDENCE' in states
        for i, left in enumerate(reconciliation):
            for right in reconciliation[i+1:]:
                # Overlapping independently approved records require explicit
                # reconciliation, even if apparently identical (conservative).
                a = [(utc(s['start_utc']), utc(s['end_utc'])) for s in left['coverage']]
                b = [(utc(s['start_utc']), utc(s['end_utc'])) for s in right['coverage']]
                if _overlap(a, b):
                    conflict = True
        if conflict:
            matched = []
        state = ('CONFLICTING_EVIDENCE' if conflict else 'HISTORICAL_SOURCE_VERIFIED' if matched
                 else states[0] if states else 'HISTORICAL_SCOPE_INCOMPLETE' if stages
                 else 'SOURCE_NOT_SUPPLIED')
        summary = {'status': state, 'historical_gap_authorized': bool(matched),
                   'evaluation_mode': 'RETROSPECTIVE_DATA_QUALITY' if retrospective else 'DECISION_AS_OF',
                   'decision_as_of_utc': as_of, 'knowledge_as_of_utc': knowledge,
                   'stages': stages, 'cross_source_reconciled': not conflict,
                   'authorized_coverage': [{'evidence_id': d['evidence_id'],
                                            'broker_symbol': d['broker_symbol'],
                                            'server': d['server'], 'coverage': d['coverage']}
                                           for d in matched],
                   'evidence_ids': [d['evidence_id'] for d in matched]}
        return HistoricalPolicy(tuple(json.dumps(d, sort_keys=True) for d in matched),
                                json.dumps(summary, sort_keys=True))


def configured_historical_store():
    """Optional file selection has no power to add source review attestations."""
    root = os.environ.get('MT5_HISTORICAL_EVIDENCE_ROOT')
    raw = os.environ.get('MT5_HISTORICAL_EVIDENCE_FILES')
    if root is None and raw is None:
        return HistoricalEvidenceStore()
    if not root or not raw or len(raw) > 8192:
        raise DataError('invalid historical evidence configuration')
    try:
        files = json.loads(raw)
    except (ValueError, RecursionError) as exc:
        raise DataError('invalid historical evidence file selection') from exc
    if (not isinstance(files, list) or not 1 <= len(files) <= MAX_RECORDS
            or any(not isinstance(name, str) for name in files)
            or len(set(files)) != len(files)):
        raise DataError('invalid historical evidence file selection')
    return HistoricalEvidenceStore([load_historical_evidence(root, name) for name in files])


def main(argv=None):
    """One read-only validate/reconcile/report command. Never writes approvals."""
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, help='Explicit operator-owned allowlisted directory')
    parser.add_argument('--file', action='append', required=True)
    parser.add_argument('--symbol', required=True, choices=SYMBOLS)
    parser.add_argument('--server', default='Exness-MT5Real50')
    parser.add_argument('--as-of', required=True)
    parser.add_argument('--gap-start')
    parser.add_argument('--gap-end')
    args = parser.parse_args(argv)
    try:
        if len(args.file) > MAX_RECORDS:
            raise DataError('too many historical evidence records')
        candidates = [load_historical_evidence(args.root, name) for name in args.file]
        policy = HistoricalEvidenceStore(candidates).evaluate(
            broker='Exness', server=args.server, product='Standard Cent', currency='USC',
            broker_symbol=args.symbol+'c', canonical_symbol=args.symbol,
            as_of=utc(args.as_of), knowledge_as_of=datetime.now(timezone.utc).timestamp(),
            retrospective=True)
        result = policy.summary()
        if bool(args.gap_start) != bool(args.gap_end):
            raise DataError('both gap endpoints required')
        if args.gap_start:
            start, end = utc(args.gap_start), utc(args.gap_end)
            if start >= end:
                raise DataError('invalid gap interval')
            result['gap'] = {'start_utc': args.gap_start, 'end_utc': args.gap_end,
                             'quote_closed': policy.quote_closed(start, end)}
        result['dry_run'] = True
        result['external_status'] = ('READY_FOR_SCOPED_RECONCILIATION' if policy.records
                                     else 'BLOCKED_BY_EXTERNAL_EVIDENCE')
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if policy.records else 3
    except (DataError, OSError) as exc:
        print(json.dumps({'status': 'REJECTED', 'dry_run': True, 'reason': str(exc)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
