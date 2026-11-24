"""Versioned operator spread limits, independent of observed broker spreads."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
import re

from .core import DataError, TIMEFRAMES

SCHEMA = 'forex-spread-policy-1'
VERSION = 'exness-cent-manual-spread-1'
ALIASES = {s: s+'c' for s in ('XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY')}


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DataError('spread numeric value unavailable')
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise DataError('spread numeric value unavailable') from exc
    if not result.is_finite():
        raise DataError('spread numeric value unavailable')
    try:
        if not math.isfinite(float(result)):
            raise DataError('spread numeric value unavailable')
    except OverflowError as exc:
        raise DataError('spread numeric value unavailable') from exc
    return result


def utc(value):
    try:
        if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', value):
            raise ValueError
        stamp = datetime.fromisoformat(value[:-1]+'+00:00')
        if stamp.utcoffset().total_seconds() != 0:
            raise ValueError
        return stamp.timestamp()
    except (TypeError, ValueError, OverflowError) as exc:
        raise DataError('spread policy UTC date invalid') from exc


def _unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise DataError('spread policy duplicate key')
        out[key] = value
    return out


def validate_policy(data):
    if (not isinstance(data, dict) or set(data) != {'schema_version', 'policy_version', 'rules'}
            or data['schema_version'] != SCHEMA or data['policy_version'] != VERSION):
        raise DataError('spread policy version or schema mismatch')
    if not isinstance(data['rules'], list) or not 1 <= len(data['rules']) <= 4:
        raise DataError('spread policy rules invalid')
    fields = {'broker_server', 'symbol', 'broker_symbol', 'account_currency', 'maximum', 'unit',
              'effective_from_utc', 'effective_to_utc', 'timeframes', 'approval_status', 'provenance'}
    seen = set()
    for rule in data['rules']:
        if not isinstance(rule, dict) or set(rule) != fields:
            raise DataError('spread policy rule schema mismatch')
        symbol = rule['symbol']
        if (not isinstance(symbol, str) or symbol not in ALIASES or symbol in seen
                or rule['broker_symbol'] != ALIASES[symbol]
                or rule['broker_server'] != 'Exness-MT5Real50' or rule['account_currency'] != 'USC'):
            raise DataError('spread policy broker identity mismatch')
        seen.add(symbol)
        if rule['unit'] not in ('PRICE', 'POINTS'):
            raise DataError('spread policy unit unsupported')
        approval = rule['approval_status']
        if approval not in ('UNAPPROVED', 'OPERATOR_APPROVED'):
            raise DataError('spread policy approval invalid')
        # Drafts deliberately allow null limits/dates; they never authorize analysis.
        if rule['maximum'] is not None and number(rule['maximum']) <= 0:
            raise DataError('spread policy maximum must be positive')
        start = utc(rule['effective_from_utc']) if rule['effective_from_utc'] is not None else None
        end = utc(rule['effective_to_utc']) if rule['effective_to_utc'] is not None else None
        if end is not None and (start is None or end <= start):
            raise DataError('spread policy effective interval invalid')
        frames = rule['timeframes']
        if (not isinstance(frames, list) or not frames or any(not isinstance(tf, str) or tf not in TIMEFRAMES for tf in frames)
                or len(frames) != len(set(frames))):
            raise DataError('spread policy timeframes invalid')
        provenance = rule['provenance']
        if (not isinstance(provenance, dict) or set(provenance) != {'kind', 'reference'}
                or provenance['kind'] != 'OPERATOR_CONFIGURATION'
                or not isinstance(provenance['reference'], str) or len(provenance['reference']) > 200):
            raise DataError('spread policy provenance invalid')
        if approval == 'OPERATOR_APPROVED' and (rule['maximum'] is None or start is None
                                               or not provenance['reference'].strip()):
            raise DataError('approved spread policy incomplete')
    return data


def load_policy(path):
    if path is None:
        return None
    try:
        with Path(path).open('rb') as stream:
            blob = stream.read(65_537)
        if len(blob) > 65_536:
            raise DataError('spread policy exceeds budget')
        data = json.loads(blob.decode('utf-8'), object_pairs_hook=_unique)
        validate_policy(data)
    except (OSError, UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise DataError('configured spread policy unavailable or invalid') from exc
    return data


def bind_rule(policy, symbol, broker_symbol, server, currency):
    if policy is None:
        return None
    for rule in policy['rules']:
        if rule['symbol'] == symbol:
            if (rule['broker_symbol'], rule['broker_server'], rule['account_currency']) != (broker_symbol, server, currency):
                return {'status': 'CONFLICTING', 'reason': 'spread policy broker identity mismatch'}
            # Do not expose local config paths or operator reference contents via API.
            safe = {k: v for k, v in rule.items() if k != 'provenance'}
            safe.update(policy_version=policy['policy_version'],
                        provenance_sha256=hashlib.sha256(json.dumps(rule['provenance'], sort_keys=True).encode()).hexdigest())
            return safe
    return None


def observed_spread(quote, meta, now):
    bid, ask, stamp = (number(quote.get(k)) for k in ('bid', 'ask', 'time'))
    if bid <= 0 or ask <= bid:
        raise DataError('spread invalid bid/ask')
    age = number(now)-stamp
    if age > 120 or age < -5:
        raise DataError('spread stale quote')
    spread = ask-bid
    points = None
    point = meta.get('point')
    digits = meta.get('digits')
    if point is not None and digits is not None:
        point = number(point)
        if type(digits) is not int or not 0 <= digits <= 12 or point != Decimal(10) ** -digits:
            raise DataError('spread point/digits mismatch')
        points = spread/point
    return {'price': float(spread), 'points': float(points) if points is not None else None,
            'symbol_spread_points': meta.get('symbol_spread_points')}


def spread_status(meta, quote, timeframe, now):
    result = {'decision': 'BLOCK', 'policy_status': 'UNVERIFIED', 'observed': None,
              'max_allowed_price': None, 'policy_version': None, 'reasons': []}
    try:
        result['observed'] = observed_spread(quote, meta, now)
        rule = meta.get('spread_policy')
        if not rule:
            if meta.get('spread_policy_required'):
                raise DataError('spread policy operator approval unavailable')
            # Existing test/demo providers retain their explicit legacy price limit.
            limit = number(meta.get('max_spread'))
            result['policy_status'] = 'LEGACY_EXPLICIT_LIMIT'
        else:
            if rule.get('status') == 'CONFLICTING':
                result['policy_status'] = 'CONFLICTING'
                raise DataError('spread policy broker identity mismatch')
            if rule.get('policy_version') != VERSION:
                raise DataError('spread policy version mismatch')
            if (rule.get('symbol'), rule.get('broker_symbol'), rule.get('broker_server'), rule.get('account_currency')) != (
                    meta.get('symbol'), meta.get('broker_symbol'), meta.get('broker_server'), meta.get('account_currency')):
                result['policy_status'] = 'CONFLICTING'
                raise DataError('spread policy broker identity mismatch')
            if rule.get('approval_status') != 'OPERATOR_APPROVED':
                result['policy_status'] = 'UNAPPROVED'
                raise DataError('spread policy operator approval unavailable')
            if timeframe not in rule.get('timeframes', []):
                raise DataError('spread policy timeframe unavailable')
            if now < utc(rule.get('effective_from_utc')) or (rule.get('effective_to_utc') is not None and now >= utc(rule['effective_to_utc'])):
                raise DataError('spread policy outside effective interval')
            limit = number(rule.get('maximum'))
            unit = rule.get('unit')
            if unit == 'POINTS':
                if result['observed']['points'] is None:
                    raise DataError('spread policy verified point unavailable')
                limit *= number(meta['point'])
            elif unit != 'PRICE':
                raise DataError('spread policy unit unsupported')
            result.update(policy_status='OPERATOR_APPROVED', policy_version=VERSION)
        if limit <= 0:
            raise DataError('spread policy maximum must be positive')
        result['max_allowed_price'] = float(limit)
        # Decimal price inputs provide an independent, exact boundary comparison.
        if number(quote['ask'])-number(quote['bid']) > limit:
            raise DataError('spread exceeds approved limit')
        result['decision'] = 'PASS'
    except (DataError, KeyError, TypeError) as exc:
        result['reasons'] = [str(exc) if isinstance(exc, DataError) else 'spread policy invalid']
    return result
