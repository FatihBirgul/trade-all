"""One private analytical host; selected source packages are owned in this checkout."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
for path in (ROOT/'vendor/day_trader', ROOT/'vendor/trade_ai/backend'):
    value=str(path)
    if value not in sys.path:
        sys.path.insert(0,value)

__version__='9.0.0-rc1'
