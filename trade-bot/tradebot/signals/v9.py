"""V9 motorunu kutuphane olarak yukler (spec §4, yaklasim A). V9 kodu degistirilmez."""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

from ..config import REPO_ROOT

DEFAULT_ROOT = REPO_ROOT / "trade-ai-unified"


def load_v9(root: Path | str | None = None):
    """`trade-ai-unified` kokunu yola ekler ve `unified_forex` paketini dondurur."""
    path = str(Path(root or DEFAULT_ROOT).resolve())
    if not (Path(path) / "unified_forex").is_dir():
        raise RuntimeError(f"V9 koku bulunamadi: {path}")
    if path not in sys.path:
        sys.path.insert(0, path)
    import unified_forex  # vendor yollarini kendisi ekler

    return unified_forex


@lru_cache(maxsize=1)
def engine():
    load_v9()
    from unified_forex.engine import AnalysisEngine

    return AnalysisEngine()


@lru_cache(maxsize=1)
def builtin_strategy_ids() -> frozenset[str]:
    load_v9()
    from unified_forex import strategies

    return frozenset(strategies.BUILTIN_IDS)
