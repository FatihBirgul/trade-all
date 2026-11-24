"""Bounded deterministic fixture-only durability run; never accepts a user DB.

Uses the real ASGI application and temporary SQLite files. No worker, public
provider, real sockets, private network or existing database is involved.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from unittest.mock import patch
import argparse
import json
from hashlib import sha256
import httpx
import random
import sqlite3
import sys
import tracemalloc

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from market_ai.v2.api import create_app
from market_ai.v2 import domain_journal as domain
from market_ai.v2.market_data_contract import Candle, Instrument
from market_ai.v2.paper_audit import audit_database
from market_ai.v2.spot_provider import FixtureSpotProvider
from scripts.backup_v2 import copy_database

TOKEN = 'soak-fixture-not-a-secret-token-32'
MINUTE = 60000
DAY = 86400000
START = 1800000000000//DAY*DAY+DAY-6*MINUTE
ALLOWED_INCOMPLETE = {'cancellation_timeline_not_persisted', 'stop_trigger_sequence_not_replayed'}


class _HistoryFixture(FixtureSpotProvider):
    def candle_window(self, symbol, start, end):
        identity = Instrument(symbol, 'crypto_spot', self.venue, 'last', 'spot', 'USDT')
        return [Candle(identity, t, t+MINUTE, True, 130, 130.1, 129.8, 130, 10000,
                       'real', self.source_name) for t in range(start, end, MINUTE)]

    def candles(self, symbol, tf, now):
        if tf == '1m':
            end = now//MINUTE*MINUTE
            return self.candle_window(symbol, end-300*MINUTE, end)
        return super().candles(symbol, tf, now)


class _Scenario:
    def __init__(self, path, seed, domain_journal=False):
        self.domain_journal = domain_journal
        self.path, self.now, self.rng = path, START, random.Random(seed)
        self.client = None
        self.financial_times = []
        self.metrics = {'seed': seed, 'audits': 0, 'audit_seconds': 0.0, 'duplicate_responses': 0,
                        'restarts': 0, 'injected_sqlite_failures': 0, 'lost_ack_recoveries': 0,
                        'domain_audit_seconds': 0.0, 'financial_mismatches': 0, 'unexpected_errors': 0, 'incomplete_checks': 0}
        self.restart()

    def restart(self):
        if self.client:
            self.client.close()
            self.metrics['restarts'] += 1
        self.app = create_app(self.path, mode='fixture', token=TOKEN, clock=lambda: self.now, domain_journal=self.domain_journal)
        self.client = TestClient(self.app, headers={'Authorization':'Bearer '+TOKEN})

    def post(self, path, body):
        started = perf_counter()
        r = self.client.post('/api/v2/'+path, json=body)
        if path.startswith(('portfolios/','paper/')):self.financial_times.append(perf_counter()-started)
        if r.status_code != 200:
            raise AssertionError('fixture request failed: '+path+' '+str(r.status_code))
        return r.json()

    def audit(self, path=None):
        start = perf_counter()
        timing = {}
        report = audit_database(path or self.path, require_domain=self.domain_journal, metrics=timing)
        self.metrics['domain_audit_seconds'] += timing.get('domain_seconds',0)
        self.metrics['audit_seconds'] += perf_counter()-start
        self.metrics['audits'] += 1
        self.metrics['records_last_audit'] = sum(report['records'].values())
        self.metrics['incomplete_checks'] += report['checks']['INCOMPLETE']
        if report['status'] not in ('PASS', 'INCOMPLETE') or (self.domain_journal and report['status']!='PASS'):
            self.metrics['financial_mismatches'] += report['checks']['MISMATCH']
            self.metrics['unexpected_errors'] += report['checks']['ERROR']+report['checks']['CORRUPT']
            raise AssertionError(report)
        if not {f['code'] for f in report['findings']}.issubset(ALLOWED_INCOMPLETE):
            raise AssertionError(report)
        return report

    def analyze(self, key):
        return self.post('analyze', {'data_mode':'fixture', 'idempotency_key':'analysis-'+key})

    def order(self, account, key, qty='10'):
        a = self.analyze(key)
        body = {'analysis_id':a['analysis_id'], 'quantity':qty, 'idempotency_key':key}
        path = 'portfolios/'+account+'/orders'
        lost = []
        def drop_ack(response):
            response.read()
            lost.append(response.json())
            raise httpx.ReadTimeout('controlled response loss after ASGI commit')
        self.client.event_hooks['response'].append(drop_ack)
        try:
            try:
                self.post(path, body)
            except httpx.ReadTimeout:
                pass
            else:
                raise AssertionError('response-loss fault did not execute')
        finally:
            self.client.event_hooks['response'].remove(drop_ack)
        first = self.post(path, body)
        if first != lost[0]:
            raise AssertionError('lost acknowledgement replay changed')
        self.metrics['lost_ack_recoveries'] += 1
        self.metrics['duplicate_responses'] += 1
        return first

    def bar(self, **changes):
        start = self.now
        self.now += MINUTE
        body = {'symbol':'BTCUSDT', 'open_time_ms':start, 'close_time_ms':self.now,
                'open':'129.9', 'high':'130.2', 'low':'129.5', 'close':'130', 'volume':'10000'}
        body.update(changes)
        return body

    def event(self, **changes):
        body = self.bar(**changes)
        receipt = self.post('paper/events', body)
        if self.post('paper/events', body) != receipt:
            raise AssertionError('event replay changed')
        self.metrics['duplicate_responses'] += 1
        return receipt

    def close(self, order, qty, key):
        self.post('portfolios/'+order['portfolio_id']+'/positions/'+order['order_id']+'/close',
                  {'quantity':qty, 'idempotency_key':key})

    def cycle(self, i):
        auto = self.order('AUTO', f'soak-auto-{i}')
        manual = self.order('MANUAL', f'soak-manual-{i}')
        body = self.bar(volume='200')
        with ThreadPoolExecutor(max_workers=2) as pool:
            receipts = list(pool.map(lambda _: self.post('paper/events', body), range(2)))
        if receipts[0] != receipts[1]:
            raise AssertionError('concurrent event receipt changed')
        self.metrics['duplicate_responses'] += 1
        self.audit()
        # One complete account has changed before the second journal write fails.
        failed = self.bar(volume='300')
        original = self.app.state.v2.ledger._journal
        calls = []
        def fail_second(*args, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                raise sqlite3.OperationalError('controlled fixture second-journal failure')
            return original(*args, **kwargs)
        before = self.audit()
        with patch.object(self.app.state.v2.ledger, '_journal', side_effect=fail_second):
            # Expected fault logged by the application; no source records are printed.
            r = self.client.post('/api/v2/paper/events', json=failed)
        if r.status_code != 503 or len(calls) != 2:
            raise AssertionError('fault injection did not hit the intended boundary')
        self.metrics['injected_sqlite_failures'] += 1
        if self.audit() != before:
            raise AssertionError('rollback changed financial audit')
        self.restart()
        ack = self.post('paper/events', failed)
        if self.post('paper/events', failed) != ack:
            raise AssertionError('restart retry changed')
        self.metrics['duplicate_responses'] += 1
        self.audit()
        self.event(volume='500')  # complete both entries (2+3+5).
        self.audit()
        self.event(open='130', high='132', low='129.8', close='131.8', volume='200')
        self.audit()
        self.close(manual, '6', f'soak-reduce-{i}')
        self.audit()
        self.event(open='130', high='130.5', low='129.8', close='130', volume='600')
        self.audit()
        self.event(open='130', high='132', low='129.8', close='131.8')
        self.audit()  # Task 11 residual TP1 clamp, MANUAL closes while AUTO stays open.
        self.event(open='132', high='134', low='131.8', close='133.8')
        self.audit()
        stopped = self.order('MANUAL', f'soak-stop-{i}')
        self.event(volume='200')
        self.audit()
        self.post('portfolios/MANUAL/orders/'+stopped['order_id']+'/cancel', {'idempotency_key':f'soak-cancel-{i}'})
        self.audit()
        self.close(stopped, '1', f'soak-small-close-{i}')
        self.event(open='130', high='130.5', low='129.8', close='130', volume='100')
        self.audit()
        self.event(open='127', high='128', low='126', close='127', volume='50')
        self.audit()
        self.event(open='129.2', high='130.2', low='129', close='130')
        self.audit()
        self.post('portfolios/MANUAL/pause', {'paused':False})
        # 60 sequential idle bars put AUTO's next order on a new 1H signal.
        for j in range(60):
            self.event(volume=str(self.rng.choice((0, 50, 200, 10000))))
            if j % 20 == 19:
                self.audit()

    def recovery_and_copy(self):
        pending = self.order('MANUAL', 'soak-recovery-order', qty='1')
        self.event()
        self.audit()
        self.app.state.v2.analysis.provider = _HistoryFixture()
        scanner = self.app.state.v2.scanner
        self.post('watchlist', {'symbol':'ETHUSDT', 'timeframe':'1H', 'enabled':True, 'auto_paper':False})
        scanner.pause(False)
        self.now += 720*MINUTE
        for expected in ('blocked', 'blocked', 'completed'):
            outcome = scanner.tick()
            if outcome['status'] != expected:
                raise AssertionError('bounded recovery phase: '+str(outcome['status']))
            self.audit()
        with scanner.db.transaction() as c:
            notes = scanner.db.rows(c, 'notifications')
            if not any(n['kind'] == 'paper_event' for n in notes):
                raise AssertionError('scanner financial outbox was not exercised')
        scanner.pause(True)
        self.close(pending, '1', 'soak-final-close')
        self.event()
        original = self.audit()
        backup, restored = self.path.with_name('backup.sqlite'), self.path.with_name('restored.sqlite')
        copy_database(self.path, backup)
        if self.audit(backup) != original:
            raise AssertionError('backup audit changed')
        copy_database(backup, restored)
        if self.audit(restored) != original:
            raise AssertionError('restored audit changed')
        self.path = restored
        self.restart()
        if self.audit() != original:
            raise AssertionError('restored restart audit changed')


def run_soak(*, cycles=3, seed=12, domain_journal=False):
    if type(cycles) is not int or not 1 <= cycles <= 8 or type(seed) is not int:
        raise ValueError('cycles must be 1..8 and seed must be an integer')
    if type(domain_journal) is not bool:raise ValueError('domain_journal must be a boolean')
    append_times = []
    original_append = domain.append
    def timed_append(*args, **kwargs):
        started = perf_counter()
        try:return original_append(*args, **kwargs)
        finally:append_times.append(perf_counter()-started)
    with TemporaryDirectory(prefix='v2-audit-soak-') as root, patch.object(domain,'append',side_effect=timed_append):
        scenario = _Scenario(Path(root)/'fixture.sqlite', seed, domain_journal)
        try:
            scenario.audit()
            for i in range(cycles):
                scenario.cycle(i)
            scenario.recovery_and_copy()
            with closing(sqlite3.connect(scenario.path.as_uri()+'?mode=ro', uri=True)) as c:
                for table in ('events', 'transactions', 'orders', 'positions', 'notifications'):
                    scenario.metrics[table] = c.execute('SELECT count(*) FROM '+table).fetchone()[0]
                checksum=sha256()
                for table in ('accounts','orders','positions','transactions','events'):
                    for key,h in c.execute('SELECT id,body_hash FROM '+table+' ORDER BY id'):
                        checksum.update((table+'\0'+key+'\0'+h+'\n').encode())
                scenario.metrics['financial_digest']=checksum.hexdigest()
                scenario.metrics['domain_events'] = c.execute('SELECT count(*) FROM domain_events').fetchone()[0] if domain_journal else 0
                scenario.metrics['utc_days'] = c.execute('SELECT count(DISTINCT close_ms/86400000) FROM events').fetchone()[0]
                queries = {
                    'event_tail': "SELECT MAX(close_ms) FROM events WHERE symbol='BTCUSDT'",
                    'account_journal': "SELECT body FROM transactions WHERE portfolio='MANUAL' ORDER BY rowid",
                    'analysis_history': 'SELECT id FROM analyses ORDER BY created_ms DESC,id LIMIT 20',
                    'source_order_journal': "SELECT body FROM transactions WHERE json_extract(body,'$.order_id')='test'",
                }
                scenario.metrics['query_plans'] = {name:[row[3] for row in c.execute('EXPLAIN QUERY PLAN '+sql)]
                                                  for name,sql in queries.items()}

            scenario.metrics.update(domain_journal=domain_journal, event_append_attempts=len(append_times),
                                    event_append_mean_ms=round(sum(append_times)/len(append_times)*1000,6) if append_times else 0,
                                    event_append_max_ms=round(max(append_times)*1000,6) if append_times else 0,
                                    financial_http_calls=len(scenario.financial_times),
                                    financial_http_mean_ms=round(sum(scenario.financial_times)/len(scenario.financial_times)*1000,6),
                                    financial_http_max_ms=round(max(scenario.financial_times)*1000,6),
                                    cycles=cycles, fixture_only=True, database_bytes=scenario.path.stat().st_size,
                                    audit_seconds=round(scenario.metrics['audit_seconds'], 6),
                                    domain_audit_seconds=round(scenario.metrics['domain_audit_seconds'],6))
            return scenario.metrics
        finally:
            scenario.client.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cycles', type=int, choices=range(1, 9), default=3)
    parser.add_argument('--seed', type=int, default=12)
    parser.add_argument('--domain-journal', action='store_true')
    parser.add_argument('--compare-domain', action='store_true', help='Paired same-binary legacy/journal fixture runs')
    args = parser.parse_args(argv)
    if args.compare_domain:
        results={}
        for name,enabled in (('legacy',False),('journal',True)):
            tracemalloc.start();started=perf_counter()
            try:
                result=run_soak(cycles=args.cycles,seed=args.seed,domain_journal=enabled)
                result['peak_python_bytes']=tracemalloc.get_traced_memory()[1]
                result['scenario_seconds']=round(perf_counter()-started,6)
                results[name]=result
            finally:tracemalloc.stop()
        if results['legacy']['financial_digest']!=results['journal']['financial_digest']:
            raise AssertionError('legacy and journal financial snapshots differ')
        results['financial_results_equal']=True
        results['measurement']='Single paired run, same binary/scenario; not a statistical or production benchmark. Append timings include rolled-back attempts; HTTP timings include ASGI and lock wait.'
        print(json.dumps(results,sort_keys=True));return
    tracemalloc.start()
    try:
        result = run_soak(cycles=args.cycles, seed=args.seed, domain_journal=args.domain_journal)
        result['peak_python_bytes'] = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
