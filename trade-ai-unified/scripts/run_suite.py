"""Offline suite runner: sockets/DNS forbidden and SQLite limited to own temp root."""
from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util,os,sys,unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('source_offline_guard',ROOT/'vendor/trade_ai/backend/tests/v2_offline_guard.py')
guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
mode=sys.argv[1] if len(sys.argv)>1 else 'engine'
if mode=='v5':
    base=ROOT/'vendor/day_trader';pattern='test_*.py';top=None
elif mode=='v2':
    base=ROOT/'vendor/trade_ai/backend';pattern='test_v2_*.py';top=str(base)
elif mode=='engine':
    base=ROOT;pattern='test_*.py';top=None
else:raise SystemExit('engine/v5/v2 expected')
os.chdir(base);sys.path[:0]=[str(base),str(base/'tests'),str(ROOT)]
with TemporaryDirectory(prefix='v6-offline-tests-') as temporary:
    with guard.offline_test_environment(temporary):
        suite=unittest.defaultTestLoader.discover(str(base/'tests'),pattern=pattern,top_level_dir=top)
        result=unittest.TextTestRunner(verbosity=1).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
