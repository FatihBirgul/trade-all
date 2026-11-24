"""Pinned V2 chart candidates as bounded, descriptive Forex context only."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import subprocess
from types import ModuleType

from .contracts import canonical
from .core import DataError
from .extensions import ExtensionResult

SOURCE_COMMIT = 'c80c97f227a2c233a610df669919ba2f464e4f9f'
SOURCE_PATH = 'backend/market_ai/engines/chart_patterns.py'
SOURCE_SHA256 = 'af69112c91938c4bd6fea3d16f43a333f63c35ea3715ed082069868e1018f1ba'
NUMPY_VERSION = '2.2.6'
BRIDGE_VERSION = 'v2-chart-pivot-descriptive-1'
PIVOT_RIGHT = 3
MAX_AGE_BARS = 20
# The other source families need independent positive, negative and first-known
# fixtures before they can be exposed, even as descriptive context.
FAMILIES = frozenset({'Double Top', 'Double Bottom'})


def _git(root, *args):
    try:
        result = subprocess.run(['git', '-C', str(root), *args], check=True,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                timeout=5)
    except (OSError, subprocess.SubprocessError) as exc:
        raise DataError('pinned V2 chart Git source unavailable') from exc
    if len(result.stdout) > 65_536:
        raise DataError('pinned V2 chart source exceeds budget')
    return result.stdout


def _load_source(source_root):
    try:
        root = Path(source_root).resolve(strict=True)
    except (OSError, ValueError) as exc:
        raise DataError('pinned V2 chart Git source unavailable') from exc
    if root.name != 'trade-ai-v2-antigravity':
        raise DataError('untrusted V2 chart root')
    bundle = Path(__file__).resolve().parents[2] / 'trade-ai-v2-antigravity'
    if root == bundle and (bundle / 'SOURCE.md').is_file():
        try:
            with (bundle / SOURCE_PATH).open('rb') as src:
                content = src.read(65_537)
        except OSError as exc:
            raise DataError('pinned V2 chart source unavailable') from exc
        if len(content) > 65_536:
            raise DataError('pinned V2 chart source exceeds budget')
    else:
        actual_root = Path(_git(root, 'rev-parse', '--show-toplevel').decode().strip()).resolve(strict=True)
        if actual_root != root:
            raise DataError('untrusted V2 chart root')
        commit = _git(root, 'rev-parse', SOURCE_COMMIT + '^{commit}').decode().strip()
        if commit != SOURCE_COMMIT:
            raise DataError('V2 chart source commit mismatch')
        content = _git(root, 'show', SOURCE_COMMIT + ':' + SOURCE_PATH)
    if hashlib.sha256(content).hexdigest() != SOURCE_SHA256:
        raise DataError('V2 chart source hash mismatch')
    tree = ast.parse(content, filename=SOURCE_PATH)
    allowed = {'__future__', 'typing', 'numpy'}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(alias.name not in allowed for alias in node.names):
            raise DataError('V2 chart import outside allowlist')
        if isinstance(node, ast.ImportFrom) and (node.level or node.module not in allowed):
            raise DataError('V2 chart import outside allowlist')
    try:
        import numpy as np
    except ImportError as exc:
        raise DataError('V2 chart NumPy dependency unavailable') from exc
    if np.__version__ != NUMPY_VERSION:
        raise DataError('V2 chart NumPy version mismatch')
    module = ModuleType('trade_ai_v2_chart_pinned')
    try:
        exec(compile(tree, SOURCE_PATH, 'exec'), module.__dict__)
    except ImportError as exc:
        raise DataError('V2 chart NumPy dependency unavailable') from exc
    detector = getattr(module, '_detect', None)
    if not callable(detector):
        raise DataError('V2 chart detector unavailable')
    return content, detector


class V2ChartPatternBridge:
    """Read the immutable Git blob, never the possibly dirty checkout file."""

    def __init__(self, source_root):
        content, self._detect = _load_source(source_root)
        self.source_sha = hashlib.sha1(content).hexdigest()  # Existing ABI shape.
        self.source_sha256 = SOURCE_SHA256

    def evaluate(self, snapshot, *, context_json):
        data = snapshot.payload()
        frame = data['frames'][data['timeframe']]
        if not 40 <= len(frame) <= 256:
            raise DataError('V2 chart candle budget exceeded')
        cutoff = data['decision_close_utc']
        if any(bar['is_final'] is not True or bar['close_time_utc'] > cutoff for bar in frame):
            raise DataError('V2 chart future or unfinished candle')
        rows = [{key: bar[key] for key in ('open', 'high', 'low', 'close')} for bar in frame]
        current = self._detect(rows)
        if not isinstance(current, list) or len(current) > 6:
            raise DataError('V2 chart output exceeds budget')
        wanted = set()
        for pattern in current:
            if not isinstance(pattern, dict):
                raise DataError('V2 chart pattern invalid')
            name, location = pattern.get('name'), pattern.get('location')
            if name not in FAMILIES:
                continue  # Legacy breakout range includes the current bar.
            if (type(location) is not int or not 0 <= location < len(frame)
                    or type(pattern.get('confirmed')) is not bool
                    or type(pattern.get('age_bars')) is not int
                    or pattern['age_bars'] != len(frame) - 1 - location
                    or pattern.get('classification') not in ('bullish', 'bearish', 'neutral')):
                raise DataError('V2 chart pattern metadata invalid')
            wanted.add((name, location))
        first_known, confirmed_at = {}, {}
        # A complete prefix replay keeps price-condition confirmation at the
        # actual first observation, never at the earlier geometric pivot.
        for length in range(40, len(frame) + 1):
            prefix = self._detect(rows[:length])
            if not isinstance(prefix, list) or len(prefix) > 6:
                raise DataError('V2 chart prefix output invalid')
            for pattern in prefix:
                if not isinstance(pattern, dict):
                    raise DataError('V2 chart prefix pattern invalid')
                key = (pattern.get('name'), pattern.get('location'))
                if key in wanted:
                    first_known.setdefault(key, length - 1)
                    if pattern.get('confirmed') is True:
                        confirmed_at.setdefault(key, length - 1)
        items = []
        for pattern in current:
            name, index = pattern.get('name'), pattern.get('location')
            key = (name, index)
            if key not in wanted:
                continue
            known = first_known.get(key)
            if known is None or known < index + PIVOT_RIGHT:
                raise DataError('V2 chart pivot known-at mismatch')
            confirmation = confirmed_at.get(key)
            if pattern['confirmed'] and (confirmation is None or confirmation < known):
                raise DataError('V2 chart confirmation mismatch')
            age = pattern['age_bars']
            expired = age > MAX_AGE_BARS
            left_censored = known == 39  # 40-bar V2 warm-up may hide earlier knowledge.
            event = {'source_sha256': SOURCE_SHA256, 'source_commit': SOURCE_COMMIT,
                     'symbol': data['symbol'], 'broker_symbol': data['broker_symbol'],
                     'provider': data['provider'], 'timeframe': data['timeframe'],
                     'name': name, 'pivot_close_utc': frame[index]['close_time_utc']}
            items.append({
                'pattern_id': hashlib.sha256(canonical(event).encode()).hexdigest()[:24],
                'name': name, 'family': 'PIVOT_STRUCTURE',
                'direction': pattern['classification'].upper(),
                'symbol': data['symbol'], 'broker_symbol': data['broker_symbol'],
                'provider': data['provider'], 'timeframe': data['timeframe'],
                'formed_at_utc': frame[index]['close_time_utc'],
                'first_known_utc': (None if left_censored else frame[known]['close_time_utc']),
                'confirmation_utc': (frame[confirmation]['close_time_utc']
                                     if confirmation is not None and not left_censored else None),
                'age_bars': age,
                'knowledge_scope': ('LEFT_CENSORED' if left_censored else
                                    'PREFIX_REPLAY_IN_CAPTURE_WINDOW'),
                'confirmation_state': ('LEFT_CENSORED' if left_censored else
                                       'EXPIRED' if expired else
                                       'STRUCTURAL_CONFIRMED' if pattern['confirmed']
                                       else 'UNCONFIRMED'),
                'invalidation_state': 'NOT_MODELED',
                'integration_status': 'DESCRIPTIVE_ONLY',
                'source_sha256': SOURCE_SHA256,
            })
        payload = {'chart_patterns': {'status': 'AVAILABLE', 'role': 'DESCRIPTIVE_ONLY',
                                      'version': BRIDGE_VERSION, 'source_commit': SOURCE_COMMIT,
                                      'source_sha256': SOURCE_SHA256, 'items': items},
                   'algorithm_versions': {'v2_chart_patterns': BRIDGE_VERSION},
                   'missing_capabilities': ['v2_strategy_routing', 'real_volume_methods']}
        return ExtensionResult(source_sha=self.source_sha, bridge_version=BRIDGE_VERSION,
                               snapshot_id=snapshot.snapshot_id, status='PARTIAL',
                               data_json=canonical(payload))


class V2DescriptiveComposite:
    """Preserve the existing candlestick bridge while adding chart context."""

    def __init__(self, candle, chart):
        self.candle, self.chart = candle, chart
        self.source_sha = hashlib.sha1((candle.source_sha + chart.source_sha).encode()).hexdigest()

    def evaluate(self, snapshot, *, context_json):
        candle = self.candle.evaluate(snapshot, context_json=context_json)
        chart = self.chart.evaluate(snapshot, context_json=context_json)
        left, right = json.loads(candle.data_json), json.loads(chart.data_json)
        left['chart_patterns'] = right['chart_patterns']
        left['algorithm_versions'].update(right['algorithm_versions'])
        left['missing_capabilities'] = sorted((set(left['missing_capabilities']) |
                                               set(right['missing_capabilities'])) -
                                              {'v2_chart_patterns'})
        return ExtensionResult(source_sha=self.source_sha,
                               bridge_version='v2-descriptive-composite-1',
                               snapshot_id=snapshot.snapshot_id, status='PARTIAL',
                               data_json=canonical(left))
