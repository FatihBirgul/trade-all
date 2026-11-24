"""Original test namespaces remain isolated, offline and unmodified."""
from pathlib import Path
import os,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
for name in ('v5','v2'):
    subprocess.run([sys.executable,str(ROOT/'scripts/run_suite.py'),name],cwd=ROOT,env=env,check=True)
