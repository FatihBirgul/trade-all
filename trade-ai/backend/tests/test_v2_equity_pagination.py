"""Bounded archive reads: real immutable fixtures, never a live DB."""
from tests import test_v2_equity_history as fixtures
from unittest import TestCase
from market_ai.v2.api import create_app
from fastapi.testclient import TestClient
from market_ai.v2.paper_audit import audit_database
from decimal import localcontext
import time,tracemalloc

class EquityPaginationTests(TestCase):
    setUp=fixtures.EquityHistoryTests.setUp
    # Reuse fixture helpers, not inherited test cases (runner filters below).
    def points(self,n):
        h=self.app.state.v2.ledger.history
        with h.db.transaction() as c:
            for i in range(n):
                self.now+=1;h.capture(c,'MANUAL',{'kind':'test_observation','index':i},self.now)
    def page(self,**params):
        return self.c.get('/api/v2/portfolios/MANUAL/equity-history-window',params=params)
    def test_pages_exceed_200_and_ignore_new_appends_without_duplicates(self):
        self.points(241);r=self.page(limit=100);self.assertEqual(r.status_code,200,r.text);a=r.json()
        self.points(3);b=self.page(limit=100,cursor=a['next_cursor']).json();c=self.page(limit=100,cursor=b['next_cursor']).json()
        seq=[p['sequence'] for d in (c,b,a) for p in d['points']]
        self.assertEqual(seq,list(range(1,242)));self.assertFalse(c['has_more']);self.assertIsNone(c['next_cursor'])
        self.assertEqual(a,self.page(limit=100,cursor=a['request_cursor']).json())
    def test_cursor_is_account_range_bound_malformed_and_restart_safe(self):
        self.points(5);a=self.page(limit=2).json();cursor=a['next_cursor']
        self.assertEqual(self.page(limit=2,cursor=cursor,from_ms=1).status_code,422)
        self.assertEqual(self.c.get('/api/v2/portfolios/AUTO/equity-history-window',params={'cursor':cursor}).status_code,422)
        for bad in ('not-json','x'*2000,cursor[:-2]+'xx'):
            self.assertEqual(self.page(cursor=bad).status_code,422)
        app=create_app(self.path,mode='fixture',token='fixture-equity-history-token-32',clock=lambda:self.now)
        with TestClient(app,headers=self.c.headers) as c:
            self.assertEqual(self.page(cursor=cursor).json(),c.get('/api/v2/portfolios/MANUAL/equity-history-window',params={'cursor':cursor}).json())
    def test_utc_inclusive_edges_empty_and_no_get_writes(self):
        self.points(5);before=self.path.read_bytes()
        d=self.page(from_ms=self.now-3,to_ms=self.now-1).json();self.assertEqual([p['sequence'] for p in d['points']],[2,3,4])
        self.assertEqual(self.page(from_ms=self.now+1).json()['points'],[])
        self.assertEqual(self.page(from_ms=2,to_ms=1).status_code,422)
        self.assertEqual(self.path.read_bytes(),before)
    def test_minmax_selects_real_extrema_boundaries_and_is_deterministic(self):
        # Writer seam: controlled wrong account values, not historical market prices.
        h=self.app.state.v2.ledger.history;original=h._value
        def value(c,account,now):
            a=original(c,account,now);a['equity_quote']=str(9000 if now%29==0 else 12000 if now%31==0 else 10000);return a
        from unittest.mock import patch
        with patch.object(h,'_value',side_effect=value):self.points(301)
        d=self.page(sampling='minmax',limit=20).json();self.assertEqual(d['status'],'complete');self.assertLessEqual(len(d['points']),20)
        self.assertEqual((d['points'][0]['sequence'],d['points'][-1]['sequence']),(1,301))
        self.assertEqual(min(float(p['equity_quote']) for p in d['points']),9000);self.assertEqual(max(float(p['equity_quote']) for p in d['points']),12000)
        with localcontext() as ctx:
            ctx.prec=3;self.assertEqual(d,self.page(sampling='minmax',limit=20).json())
        # Sampling-only synthetic sources are not execution evidence. Independent
        # accounting is checked separately with real order/event fixtures below.
    def test_budget_and_resource_measurement(self):
        self.points(1001);tracemalloc.start();start=time.perf_counter()
        d=self.page(sampling='minmax',limit=50).json();_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
        print({'equity_archive_fixture_points':1001,'audit_query_seconds':round(time.perf_counter()-start,4),'peak_traced_bytes':peak,'db_bytes':self.path.stat().st_size})
        self.assertEqual(d['observations_scanned'],1001);self.assertLessEqual(len(d['points']),50)
        self.assertEqual(d['sampling'],'minmax');self.assertEqual(d['excluded_incomplete'],0)
        self.assertEqual(self.page(sampling='minmax',limit=2).status_code,422)

    def test_archive_read_preserves_independently_audited_execution(self):
        fixtures.EquityHistoryTests.order(self);fixtures.EquityHistoryTests.bar(self)
        before=audit_database(self.path,require_domain=True)
        self.assertEqual(self.page(sampling='minmax',limit=6).status_code,200)
        self.assertEqual(self.page(limit=1).status_code,200)
        after=audit_database(self.path,require_domain=True)
        self.assertEqual(before,after);self.assertEqual(after['checks']['MISMATCH'],0);self.assertEqual(after['checks']['CORRUPT'],0)
    def test_oversized_sample_has_no_partial_curve_and_response_budget_fails_closed(self):
        from unittest.mock import patch
        self.points(11)
        with patch('market_ai.v2.equity_archive.MAX_SCAN_ROWS',10):
            d=self.page(sampling='minmax',limit=6).json()
        self.assertEqual(d['status'],'incomplete_budget');self.assertEqual(d['points'],[])
        self.assertEqual(self.page(limit=6).status_code,200)
        with patch('market_ai.v2.equity_archive.MAX_RESPONSE_BYTES',20):
            r=self.page();self.assertEqual(r.status_code,503)
            self.assertEqual(r.json()['error']['code'],'HISTORY_RESPONSE_BUDGET')
    def test_equal_and_backward_timestamps_do_not_reorder_account_sequence(self):
        h=self.app.state.v2.ledger.history
        with h.db.transaction() as c:
            for i in range(8):h.capture(c,'MANUAL',{'kind':'test_observation','index':i},self.now-(i//4))
        a=self.page(limit=3).json();b=self.page(limit=3,cursor=a['next_cursor']).json();d=self.page(limit=3,cursor=b['next_cursor']).json()
        self.assertEqual([p['sequence'] for page in (d,b,a) for p in page['points']],list(range(1,9)))
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(self.path)) as c:
            plan=c.execute('EXPLAIN QUERY PLAN SELECT sequence FROM equity_snapshots WHERE portfolio=? AND sequence<? ORDER BY sequence DESC LIMIT 201',('MANUAL',9)).fetchall()
        self.assertTrue(any('INDEX' in row[3] for row in plan),plan)
    def test_sample_preserves_utc_extremes_during_recording_clock_rollback(self):
        h=self.app.state.v2.ledger.history
        with h.db.transaction() as c:
            for i,delta in enumerate((5,1,9,4,5,5,5,5)):
                h.capture(c,'MANUAL',{'kind':'test_observation','clock_index':i},self.now+delta)
        d=self.page(sampling='minmax',limit=6).json()
        self.assertTrue({1,2,3,8}<={p['sequence'] for p in d['points']},d)
