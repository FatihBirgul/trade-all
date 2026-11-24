"""Explicit, pinned read-only adapter for the V2 OHLC candlestick detector."""
import hashlib
import os
from functools import lru_cache
from pathlib import Path
from types import ModuleType

from .contracts import canonical
from .core import DataError
from .extensions import ExtensionResult

BRIDGE_VERSION = 'v2-candlestick-bridge-1'


class V2CandlestickBridge:
    """Load only a trusted V2 detector file; never import its product services."""

    def __init__(self, source_file, expected_sha256):
        path = Path(source_file).resolve(strict=True)
        if path.name != 'candlestick.py' or path.parent.name != 'engines':
            raise DataError('V2 candlestick source path invalid')
        if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
            raise DataError('V2 source pin required')
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest != expected_sha256.lower():
            raise DataError('V2 source hash mismatch')
        module = ModuleType('trade_ai_v2_candlestick_pinned')
        exec(compile(content, str(path), 'exec'), module.__dict__)
        if not callable(getattr(module, 'detect', None)):
            raise DataError('V2 candlestick detector unavailable')
        self._detect = module.detect
        self.source_sha = hashlib.sha1(content).hexdigest()  # Existing extension ABI is SHA-1-shaped.
        self.source_sha256 = digest

    def evaluate(self, snapshot, *, context_json):
        data = snapshot.payload()
        frame = data['frames'][data['timeframe']]
        # Snapshot capture already checked finality, OHLC, identity, age and broker gaps.
        rows = [{key: bar[key] for key in ('open', 'high', 'low', 'close')} for bar in frame]
        raw = self._detect(rows)
        if not isinstance(raw, list) or len(raw) > 8:
            raise DataError('V2 detector result invalid')
        patterns = []
        for item in raw:
            if not isinstance(item, dict) or type(item.get('location')) is not int:
                raise DataError('V2 pattern location invalid')
            index = item['location']
            if not 0 <= index < len(frame) or item.get('classification') not in ('bullish', 'bearish', 'neutral'):
                raise DataError('V2 pattern identity invalid')
            if type(item.get('confirmed')) is not bool or type(item.get('age_bars')) is not int:
                raise DataError('V2 pattern confirmation invalid')
            if item['age_bars'] != len(frame) - 1 - index:
                raise DataError('V2 pattern age mismatch')
            known_index = index + 1 if item['confirmed'] else index
            if known_index >= len(frame):
                raise DataError('V2 pattern future confirmation')
            patterns.append({'name': str(item.get('name', ''))[:120],
                             'direction': item['classification'].upper(),
                             'formed_at_utc': frame[index]['close_time_utc'],
                             'known_at_utc': frame[known_index]['close_time_utc'],
                             'confirmed': item['confirmed'], 'age_bars': item['age_bars']})
        payload = {'candlestick_patterns': {'status': 'AVAILABLE', 'version': BRIDGE_VERSION,
                                            'role': 'DESCRIPTIVE_ONLY', 'items': patterns},
                   'algorithm_versions': {'v2_candlestick': BRIDGE_VERSION},
                   'missing_capabilities': ['v2_chart_patterns', 'v2_strategy_routing',
                                            'real_volume_methods']}
        return ExtensionResult(source_sha=self.source_sha, bridge_version=BRIDGE_VERSION,
                               snapshot_id=snapshot.snapshot_id, status='PARTIAL',
                               data_json=canonical(payload))


def configured_v2_extension():
    source = os.environ.get('V2_CANDLESTICK_FILE')
    digest = os.environ.get('V2_CANDLESTICK_SHA256')
    chart_root = os.environ.get('V2_CHART_GIT_ROOT')
    if source is None and digest is None and chart_root is None:
        return None
    if (source is None) != (digest is None) or (source is not None and (not source or not digest)):
        raise DataError('V2 candlestick configuration incomplete')
    candle = V2CandlestickBridge(source, digest) if source else None
    if chart_root is None:
        return candle
    if not chart_root:
        raise DataError('V2 chart source root required')
    chart = _configured_chart(chart_root)
    if candle is None:
        return chart
    from .v2_chart_bridge import V2DescriptiveComposite
    return V2DescriptiveComposite(candle, chart)


@lru_cache(maxsize=2)
def _configured_chart(root):
    from .v2_chart_bridge import V2ChartPatternBridge
    return V2ChartPatternBridge(root)
