"""Explicit allowlist discovery; never collects legacy remote API test files."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

# Support `python tests/run_v2_offline_tests.py` from backend on both CI OSes.
BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from tests.v2_offline_guard import offline_test_environment


if __name__ == "__main__":
    with TemporaryDirectory(prefix="trade-ai-v2-offline-") as root:
        with offline_test_environment(root):
            suite = unittest.defaultTestLoader.discover(str(BACKEND / "tests"), pattern="test_v2_*.py")
            result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
