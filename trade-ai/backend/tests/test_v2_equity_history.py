"""Forward-only equity history, isolated accounts/fixtures; no invented marks."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from decimal import Decimal as D, localcontext
from fastapi.testclient import TestClient
from market_ai.v2.api import create_app
from market_ai.v2.paper_audit import audit_database
TOKEN='fixture-equity-history-token-32'
class EquityHistoryTests(TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'isolated.sqlite';self.now=1800000000000
        self.app=create_app(self.path,mode='fixture',token=TOKEN,clock=lambda:self.now,domain_journal=True)
        self.c=TestClient(self.app,headers={'Authorization':'Bearer '+TOKEN});self.addCleanup(self.c.close)
        self.url='/api/v2/portfolios/MANUAL/equity-history'
    def order(self):
        a=self.c.post('/api/v2/analyze',json={'idempotency_key':'equity-analysis-1','data_mode':'fixture','risk_portfolio':'MANUAL'}).json()
        r=self.c.post('/api/v2/portfolios/MANUAL/orders',json={'idempotency_key':'equity-order-1','analysis_id':a['analysis_id'],'quantity':'1'})
        self.assertEqual(r.status_code,200,r.text);return r.json()
    def bar(self):
        start=self.now;self.now+=60000
        body={'symbol':'BTCUSDT','open_time_ms':start,'close_time_ms':self.now,'open':'129.9','high':'130.2','low':'129.5','close':'130','volume':'10000'}
        r=self.c.post('/api/v2/paper/events',json=body);self.assertEqual(r.status_code,200,r.text)
        return body
    def history(self):
        r=self.c.get(self.url);self.assertEqual(r.status_code,200,r.text);return r.json()
    def test_empty_history_is_forward_only_and_read_does_not_write(self):
        data=self.history();self.assertEqual(data['points'],[]);self.assertEqual(data['coverage'],'forward_only')
        self.assertEqual(data,self.history())
    def test_actual_mark_cash_basis_and_restart_idempotency(self):
        self.order();bar=self.bar();data=self.history();self.assertEqual(len(data['points']),2)
        p=data['points'][-1];basis=D('129.92598')+D('129.92598')*D('.0005')
        basis=basis.quantize(D('.00000001'))
        self.assertEqual(D(p['cash_quote']),D(10000)-basis)
        self.assertEqual(D(p['equity_quote']),D(10000)-basis+D(130))
        self.assertEqual(D(p['unrealized_pnl_quote']),D(130)-basis)
        self.assertEqual(p['quality_status'],'complete');self.assertEqual(p['marks'][0]['mark_time_ms'],self.now)
        self.assertEqual(self.c.get('/api/v2/portfolios/AUTO/equity-history').json()['points'],[])
        self.assertEqual(self.c.post('/api/v2/paper/events',json=bar).status_code,200)
        self.assertEqual(data,self.history())
        app=create_app(self.path,mode='fixture',token=TOKEN,clock=lambda:self.now)
        with TestClient(app,headers={'Authorization':'Bearer '+TOKEN}) as c:self.assertEqual(data,c.get(self.url).json())
        report=audit_database(self.path,require_domain=True)
        self.assertEqual(report['checks']['MISMATCH'],0,report);self.assertEqual(report['checks']['CORRUPT'],0,report)
    def test_snapshot_insert_failure_rolls_back_order_and_receipt(self):
        import sqlite3
        original=self.app.state.v2.ledger.history.capture
        with patch.object(self.app.state.v2.ledger.history,'capture',side_effect=sqlite3.OperationalError('fixture snapshot disk failure')):
            a=self.c.post('/api/v2/analyze',json={'idempotency_key':'equity-failed-analysis','data_mode':'fixture','risk_portfolio':'MANUAL'}).json()
            r=self.c.post('/api/v2/portfolios/MANUAL/orders',json={'idempotency_key':'failed-order-1','analysis_id':a['analysis_id']})
            self.assertEqual(r.status_code,503,r.text)
        self.assertEqual(self.c.get('/api/v2/portfolios/MANUAL/orders').json(),[])
        self.assertEqual(self.history()['points'],[])
        self.order()
        start=self.now;self.now+=60000
        event={'symbol':'BTCUSDT','open_time_ms':start,'close_time_ms':self.now,'open':'129.9','high':'130.2','low':'129.5','close':'130','volume':'10000'}
        with patch.object(self.app.state.v2.ledger.history,'capture',side_effect=sqlite3.OperationalError('fixture post-fill snapshot failure')):
            self.assertEqual(self.c.post('/api/v2/paper/events',json=event).status_code,503)
        self.assertEqual(self.c.get('/api/v2/portfolios/MANUAL/transactions').json(),[])
        self.assertEqual(self.c.get('/api/v2/portfolios/MANUAL/positions').json(),[])
        self.assertEqual(D(self.c.get('/api/v2/portfolios/MANUAL').json()['cash_quote']),D(10000))
        self.assertEqual(len(self.history()['points']),1)
        self.assertEqual(self.c.post('/api/v2/paper/events',json=event).status_code,200)
        self.assertEqual(len(self.c.get('/api/v2/portfolios/MANUAL/transactions').json()),1)
        self.assertEqual(len(self.history()['points']),2)
    def test_independent_audit_detects_wrong_snapshot_with_valid_hash_chain(self):
        h=self.app.state.v2.ledger.history;original=h._value
        def wrong(*a):
            result=original(*a);result['equity_quote']='99999.00000000';return result
        with patch.object(h,'_value',side_effect=wrong):self.order()
        report=audit_database(self.path,require_domain=True)
        self.assertGreater(report['checks']['MISMATCH'],0,report)
    def test_cancel_and_decimal_context_preserve_cash_reservation(self):
        order=self.order()
        self.assertGreater(D(self.history()['points'][-1]['reserved_cash_quote']),0)
        r=self.c.post('/api/v2/portfolios/MANUAL/orders/'+order['order_id']+'/cancel',json={'idempotency_key':'cancel-equity-1'})
        self.assertEqual(r.status_code,200,r.text)
        with localcontext() as ctx:
            ctx.prec=3
            p=self.history()['points'][-1]
        self.assertEqual(p['reserved_cash_quote'],'0.00000000');self.assertEqual(p['cash_quote'],'10000.00000000')
    def test_stale_marks_are_retained_but_never_charted(self):
        order=self.order();self.bar();self.now+=120000
        r=self.c.post('/api/v2/portfolios/MANUAL/positions/'+order['order_id']+'/close',json={'idempotency_key':'stale-close-1','quantity':'0.1'})
        self.assertEqual(r.status_code,200,r.text)
        p=self.history()['points'][-1]
        self.assertEqual(p['quality_status'],'stale');self.assertFalse(p['chart_eligible'])
        self.assertEqual(p['marks'][0]['mark_time_ms'],self.now-120000)
        report=audit_database(self.path,require_domain=True);self.assertEqual(report['checks']['MISMATCH'],0,report)
    def test_full_exit_fees_drawdown_and_closed_quantity(self):
        order=self.order();self.bar()
        r=self.c.post('/api/v2/portfolios/MANUAL/positions/'+order['order_id']+'/close',json={'idempotency_key':'close-equity-1','quantity':'1'})
        self.assertEqual(r.status_code,200,r.text);self.bar()
        points=self.history()['points'];p=points[-1]
        self.assertEqual(p['closed_positions'],1);self.assertEqual(p['open_positions'],0)
        self.assertEqual(p['marks'],[]);self.assertEqual(D(p['fees_quote']),D('.12990000'))
        self.assertEqual(D(p['realized_pnl_quote']),D('-.18186000'))
        self.assertEqual(D(p['equity_quote']),D('9999.81814000'));self.assertEqual(D(p['unrealized_pnl_quote']),0)
        self.assertEqual(D(p['maximum_drawdown_quote']),D('.19091701'))
        self.assertEqual(self.c.get(self.url,params={'from_ms':self.now+1}).json()['points'],[])
        report=audit_database(self.path,require_domain=True);self.assertEqual(report['checks']['MISMATCH'],0,report)
    def test_order_retry_does_not_duplicate_snapshot_and_history_is_immutable(self):
        self.order();before=self.history();self.order();self.assertEqual(before,self.history())
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(self.path)) as c:
            with self.assertRaises(sqlite3.DatabaseError):c.execute("DELETE FROM equity_snapshots")
        self.assertEqual(self.c.get(self.url,params={'from_ms':2,'to_ms':1}).status_code,422)
    def test_legacy_copy_upgrade_keeps_real_boundary_and_snapshots(self):
        from scripts.migrate_v2_domain import copy_upgrade
        legacy=self.path.with_name('legacy.sqlite')
        app=create_app(legacy,mode='fixture',token=TOKEN,clock=lambda:self.now)
        with TestClient(app,headers={'Authorization':'Bearer '+TOKEN}) as c:self.assertEqual(c.get(self.url).json()['points'],[])
        original=legacy.read_bytes();destination=self.path.with_name('upgrade.sqlite')
        copy_upgrade(legacy,destination,clock=lambda:self.now+1)
        self.assertEqual(legacy.read_bytes(),original)
        app=create_app(destination,mode='fixture',token=TOKEN,clock=lambda:self.now+1)
        with TestClient(app,headers={'Authorization':'Bearer '+TOKEN}) as c:self.assertEqual(c.get(self.url).json()['points'],[])
        r=audit_database(destination,require_domain=True);self.assertEqual(r['checks']['CORRUPT'],0,r)
    def test_legacy_existing_observation_then_new_domain_snapshot_has_no_false_mismatch(self):
        from scripts.migrate_v2_domain import copy_upgrade
        legacy=self.path.with_name('old-observations.sqlite')
        app=create_app(legacy,mode='fixture',token=TOKEN,clock=lambda:self.now)
        with TestClient(app,headers={'Authorization':'Bearer '+TOKEN}) as c:
            a=c.post('/api/v2/analyze',json={'idempotency_key':'old-history-analysis','data_mode':'fixture','risk_portfolio':'MANUAL'}).json()
            order=c.post('/api/v2/portfolios/MANUAL/orders',json={'idempotency_key':'old-history-order','analysis_id':a['analysis_id']}).json()
        target=self.path.with_name('new-domain.sqlite');copy_upgrade(legacy,target,clock=lambda:self.now+1)
        app=create_app(target,mode='fixture',token=TOKEN,clock=lambda:self.now+1)
        with TestClient(app,headers={'Authorization':'Bearer '+TOKEN}) as c:
            r=c.post('/api/v2/portfolios/MANUAL/orders/'+order['order_id']+'/cancel',json={'idempotency_key':'new-domain-cancel'});self.assertEqual(r.status_code,200,r.text)
        report=audit_database(target,require_domain=True)
        self.assertEqual(report['checks']['MISMATCH'],0,report)
        self.assertEqual(report['checks']['CORRUPT'],0,report)
    def test_calendar_periods_use_transaction_utc_not_observation_interpolation(self):
        from datetime import datetime,timezone
        self.now=int(datetime(2027,1,31,23,58,tzinfo=timezone.utc).timestamp())*1000
        order=self.order();self.bar()
        self.c.post('/api/v2/portfolios/MANUAL/positions/'+order['order_id']+'/close',json={'idempotency_key':'calendar-close-1','quantity':'1'})
        self.bar()
        days=self.c.get(self.url,params={'period':'day'}).json()
        self.assertEqual([p['period'] for p in days['period_totals']],['2027-01-31','2027-02-01'])
        self.assertEqual(sum(D(p['fees_quote']) for p in days['period_totals']),D('.12990000'))
        months=self.c.get(self.url,params={'period':'month'}).json()
        self.assertEqual([p['period'] for p in months['period_totals']],['2027-01','2027-02'])
        weeks=self.c.get(self.url,params={'period':'week'}).json()
        self.assertEqual([p['period'] for p in weeks['period_totals']],['2027-W04','2027-W05'])
