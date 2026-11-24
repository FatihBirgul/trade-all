"""Account-scoped immutable profile controls, isolated fixture databases."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from fastapi.testclient import TestClient
from market_ai.v2.api import create_app
TOKEN='fixture-profile-token-not-secret-32'
class ProfileProductTests(TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'profiles.sqlite'
        self.app=create_app(self.path,mode='fixture',token=TOKEN,clock=lambda:1800000000000,domain_journal=True)
        self.client=TestClient(self.app,headers={'Authorization':'Bearer '+TOKEN}); self.addCleanup(self.client.close)
        self.base='/api/v2/portfolios/MANUAL/strategy-profiles'
    def create(self,key='profile-create-1',**kw):
        r=self.client.post(self.base,json={'idempotency_key':key,**kw})
        self.assertEqual(r.status_code,200,r.text); return r.json()
    def test_create_retry_restart_isolation(self):
        self.assertEqual(self.client.get('/api/v2/strategy-capabilities').status_code,200)
        first=self.create(); self.assertEqual(first,self.create())
        self.assertEqual(self.client.get('/api/v2/portfolios/AUTO/strategy-profiles/'+first['profile_id']).status_code,404)
        app=create_app(self.path,mode='fixture',token=TOKEN,clock=lambda:1800000000001)
        with TestClient(app,headers={'Authorization':'Bearer '+TOKEN}) as c:
            self.assertEqual(c.get(self.base+'/'+first['profile_id']).json(),first)
        self.assertEqual(len(self.client.get(self.base).json()),1)
    def test_revision_conflict_and_idempotency(self):
        first=self.create(); path=self.base+'/'+first['profile_id']+'/revisions'
        args={'idempotency_key':'revision-request-1','selection':{'minimum_confirmations':3}}
        second=self.client.post(path,json=args); self.assertEqual(second.status_code,200,second.text)
        self.assertEqual(second.json(),self.client.post(path,json=args).json())
        self.assertEqual(second.json()['revision'],2)
        self.assertEqual(self.client.post(path,json={**args,'idempotency_key':'revision-request-2'}).status_code,409)
        self.assertEqual(self.client.post(self.base,json={'idempotency_key':'profile-create-1','selection':{'minimum_confirmations':4}}).status_code,409)
    def test_invalid_whitelist_and_auth(self):
        for selection in ({'risk_limit':100},{'minimum_confirmations':True},{'required_methods':['madeup']},{'strategy_ids':[]},{'bias_timeframe':'1m','setup_timeframe':'1H'}):
            self.assertEqual(self.client.post(self.base,json={'idempotency_key':'bad-profile-1','selection':selection}).status_code,422)
        with TestClient(self.app) as c:self.assertEqual(c.get(self.base).status_code,401)
    def test_concurrent_same_command_and_immutable(self):
        with ThreadPoolExecutor(max_workers=3) as pool: rows=list(pool.map(lambda _:self.create(),range(3)))
        self.assertTrue(all(row==rows[0] for row in rows))
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(self.path)) as c:
            with self.assertRaises(sqlite3.DatabaseError):c.execute('DELETE FROM strategy_profiles')
    def test_binding_cannot_revive_wait_and_account_scope(self):
        first=self.create()
        args={'idempotency_key':'analysis-profile-1','data_mode':'fixture','risk_portfolio':'MANUAL','timeframe':'1m','profile_id':first['profile_id'],'fixture_case':'stale'}
        r=self.client.post('/api/v2/analyze',json=args); self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['direction'],'WAIT'); self.assertIsNone(r.json()['levels'])
        self.assertFalse(r.json()['technical_methods']['profile_control']['trade_permission'])
        self.assertEqual(self.client.post('/api/v2/analyze',json={**args,'risk_portfolio':'AUTO','idempotency_key':'analysis-profile-2'}).status_code,404)
        self.assertEqual(self.client.post('/api/v2/analyze',json={**args,'timeframe':'1H','idempotency_key':'analysis-profile-3'}).status_code,422)

    def test_journal_and_projection_failure_roll_back_all_profile_writes(self):
        from unittest.mock import patch
        import sqlite3
        from market_ai.v2.product_db import ProductDatabase
        from market_ai.v2 import domain_journal as domain
        store=self.app.state.v2.analysis.profiles
        original=ProductDatabase.remember
        def fail(*args,**kwargs):
            original(*args,**kwargs)
            raise sqlite3.OperationalError('fixture disk failure')
        from market_ai.v2.profile_product import ProfileWrite
        with patch.object(ProductDatabase,'remember',side_effect=fail):
            with self.assertRaises(sqlite3.OperationalError):store.write('MANUAL',ProfileWrite(idempotency_key='rollback-profile'))
        self.assertEqual(self.client.get(self.base).json(),[])
        from market_ai.v2.paper_audit import audit_database
        report=audit_database(self.path,require_domain=True)
        self.assertEqual(report['checks']['CORRUPT'],0,report)
        self.assertEqual(report['checks']['MISMATCH'],0,report)
        self.create()
        report=audit_database(self.path,require_domain=True)
        self.assertEqual(report['checks']['CORRUPT'],0,report)
        self.assertEqual(report['checks']['MISMATCH'],0,report)

    def test_evaluate_saved_analysis_cannot_access_other_account(self):
        profile=self.create()
        args={'idempotency_key':'evaluate-analysis-1','data_mode':'fixture','risk_portfolio':'AUTO'}
        analysis=self.client.post('/api/v2/analyze',json=args).json()
        path=self.base+'/'+profile['profile_id']+'/evaluate'
        self.assertEqual(self.client.post(path,json={'analysis_id':analysis['analysis_id']}).status_code,404)

    def test_restricts_valid_direction_and_preserves_legacy_digest(self):
        original={'idempotency_key':'original-analysis-1','data_mode':'fixture','risk_portfolio':'MANUAL','timeframe':'1H'}
        response=self.client.post('/api/v2/analyze',json=original)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['direction'],'bullish')
        p=self.create(selection={'strategy_ids':['range_mean_reversion_v2'],'bias_timeframe':'1H','setup_timeframe':'1H','trigger_timeframe':'1H'})
        filtered=self.client.post('/api/v2/analyze',json={**original,'idempotency_key':'filtered-analysis-1','profile_id':p['profile_id']})
        self.assertEqual(filtered.status_code,200,filtered.text)
        self.assertEqual(filtered.json()['direction'],'WAIT');self.assertIsNone(filtered.json()['levels'])
        with self.app.state.v2.db.transaction() as c:
            from market_ai.v2.api_models import AnalyzeRequest
            from market_ai.v2.product_db import fingerprint
            saved=c.execute("SELECT hash FROM commands WHERE scope='analyze' AND key=?",(original['idempotency_key'],)).fetchone()[0]
            legacy=AnalyzeRequest(**original).model_dump(mode='json');legacy.pop('profile_id',None)
            self.assertEqual(saved,fingerprint(legacy))

    def test_passing_profile_does_not_change_decision_or_levels(self):
        p=self.create(selection={'bias_timeframe':'1H','setup_timeframe':'1H','trigger_timeframe':'1H'})
        args={'data_mode':'fixture','risk_portfolio':'MANUAL','timeframe':'1H','idempotency_key':'unfiltered-pass-1'}
        before=self.client.post('/api/v2/analyze',json=args).json()
        after=self.client.post('/api/v2/analyze',json={**args,'idempotency_key':'filtered-pass-1','profile_id':p['profile_id']}).json()
        self.assertTrue(after['technical_methods']['profile_control']['passes'],after)
        self.assertEqual(before['direction'],after['direction']);self.assertEqual(before['levels'],after['levels'])
        self.assertIsNone(after['auto_order_id'])

    def test_event_write_failure_rolls_back_profile_and_command(self):
        from unittest.mock import patch
        import sqlite3
        from market_ai.v2 import domain_journal
        from market_ai.v2.profile_product import ProfileWrite
        original=domain_journal.append
        def fail(c,kind,*args,**kwargs):
            if kind=='record.created':raise sqlite3.OperationalError('injected event failure')
            return original(c,kind,*args,**kwargs)
        with patch.object(domain_journal,'append',side_effect=fail):
            with self.assertRaises(sqlite3.OperationalError):
                self.app.state.v2.analysis.profiles.write('MANUAL',ProfileWrite(idempotency_key='event-fail-profile'))
        self.assertEqual(self.client.get(self.base).json(),[])
        with self.app.state.v2.db.transaction() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM commands WHERE scope='profile:MANUAL'").fetchone()[0],0)
        self.create(key='event-fail-profile')

    def test_competing_revisions_have_one_winner_and_backup_restores(self):
        p=self.create();url=self.base+'/'+p['profile_id']+'/revisions'
        with ThreadPoolExecutor(max_workers=2) as pool:
            codes=list(pool.map(lambda n:self.client.post(url,json={'idempotency_key':'revision-race-'+str(n)}).status_code,range(2)))
        self.assertEqual(sorted(codes),[200,409])
        from scripts.backup_v2 import copy_database
        target=self.path.with_name('copy.sqlite');copy_database(self.path,target)
        app=create_app(target,mode='fixture',token=TOKEN,clock=lambda:1800000000001)
        with TestClient(app,headers={'Authorization':'Bearer '+TOKEN}) as c:self.assertEqual(len(c.get(self.base).json()),2)

    def test_legacy_profiles_copy_upgrade_has_no_fabricated_events(self):
        from scripts.migrate_v2_domain import copy_upgrade
        from market_ai.v2.paper_audit import audit_database
        legacy=self.path.with_name('legacy.sqlite')
        app=create_app(legacy,mode='fixture',token=TOKEN,clock=lambda:1800000000000)
        with TestClient(app,headers={'Authorization':'Bearer '+TOKEN}) as c:
            r=c.post(self.base,json={'idempotency_key':'legacy-profile-1'});self.assertEqual(r.status_code,200,r.text)
        before=legacy.read_bytes();target=self.path.with_name('migrated.sqlite')
        copy_upgrade(legacy,target,clock=lambda:1800000000001)
        self.assertEqual(before,legacy.read_bytes())
        report=audit_database(target,require_domain=True)
        self.assertEqual(report['checks']['MISMATCH'],0,report)
        self.assertEqual(report['checks']['CORRUPT'],0,report)
        self.assertEqual(report['domain']['coverage'],'legacy_boundary')

    def test_follow_keeps_original_profile_after_restart(self):
        p=self.create(selection={'strategy_ids':['range_mean_reversion_v2'],'bias_timeframe':'1H','setup_timeframe':'1H','trigger_timeframe':'1H'})
        args={'data_mode':'fixture','risk_portfolio':'MANUAL','timeframe':'1H','idempotency_key':'follow-profile-analysis','profile_id':p['profile_id']}
        a=self.client.post('/api/v2/analyze',json=args).json()
        f=self.client.post('/api/v2/analysis-tracking',json={'analysis_id':a['analysis_id']});self.assertEqual(f.status_code,200,f.text)
        app=create_app(self.path,mode='fixture',token=TOKEN,clock=lambda:1800003600000)
        app.state.tracking.tick()
        row=app.state.tracking.get(f.json()['tracking_id'])
        with app.state.v2.db.transaction() as c:latest=app.state.v2.db.get(c,'analyses',row.last_analysis_id)
        self.assertEqual(latest['direction'],'WAIT',latest)
        self.assertEqual(latest['technical_methods']['profile_control']['profile_record_id'],p['profile_id'])

    def test_scanner_profile_is_auto_scoped_and_uses_all_roles(self):
        p=self.create()
        args={'symbol':'BTCUSDT','timeframe':'1H','profile_id':p['profile_id'],'auto_paper':False}
        self.assertEqual(self.client.post('/api/v2/watchlist',json=args).status_code,404)
        response=self.client.post('/api/v2/portfolios/AUTO/strategy-profiles',json={'idempotency_key':'scanner-profile-1','selection':{'bias_timeframe':'4H','setup_timeframe':'1H','trigger_timeframe':'15m'}})
        auto=response.json();self.assertEqual(response.status_code,200,response.text)
        watch=self.client.post('/api/v2/watchlist',json={**args,'profile_id':auto['profile_id']});self.assertEqual(watch.status_code,200,watch.text)
        self.app.state.v2.scanner.pause(False)
        jobs=self.app.state.v2.scanner.tick()['jobs'];self.assertEqual(len(jobs),1)
        with self.app.state.v2.db.transaction() as c:a=self.app.state.v2.db.get(c,'analyses',jobs[0]['analysis_id'])
        self.assertEqual(a['timeframes'],['15m','1H','4H'])
        self.assertEqual(a['technical_methods']['profile_control']['profile_record_id'],auto['profile_id'])
        self.assertIsNone(a['auto_order_id'])
        self.assertEqual(self.app.state.v2.scanner.tick()['jobs'],[])

    def test_changed_watch_during_provider_call_cannot_commit_old_analysis(self):
        from unittest.mock import patch
        from market_ai.v2.scanner_models import WatchRequest
        scanner=self.app.state.v2.scanner
        scanner.watch(WatchRequest(symbol='BTCUSDT'));scanner.pause(False)
        provider=self.app.state.v2.analysis.provider
        original=provider.candles
        changed=False
        def candles(*args,**kw):
            nonlocal changed
            if not changed:
                changed=True;scanner.watch(WatchRequest(symbol='BTCUSDT',enabled=False))
            return original(*args,**kw)
        with patch.object(provider,'candles',side_effect=candles):jobs=scanner.tick()['jobs']
        self.assertEqual(jobs[0]['reason'],'SCANNER_WATCH_CHANGED')
        self.assertIsNone(jobs[0]['analysis_id'])
        self.assertEqual(self.client.get('/api/v2/analyses').json(),[])
        self.assertEqual(self.client.get('/api/v2/portfolios/AUTO/orders').json(),[])

    def test_old_watch_wire_shape_and_toggle_keep_profile_without_opt_in(self):
        p=self.client.post('/api/v2/portfolios/AUTO/strategy-profiles',json={'idempotency_key':'legacy-watch-profile','selection':{'bias_timeframe':'1H','setup_timeframe':'1H','trigger_timeframe':'1H'}}).json()
        args={'symbol':'BTCUSDT','timeframe':'1H','profile_id':p['profile_id']}
        self.assertEqual(self.client.post('/api/v2/watchlist?include_profile=true',json=args).json()['profile_id'],p['profile_id'])
        old=self.client.get('/api/v2/watchlist').json()[0]
        self.assertNotIn('profile_id',old)
        old.pop('watch_id');old['enabled']=False
        self.assertNotIn('profile_id',self.client.post('/api/v2/watchlist',json=old).json())
        self.assertEqual(self.client.get('/api/v2/watchlist?include_profile=true').json()[0]['profile_id'],p['profile_id'])

    def test_new_profile_revision_does_not_change_existing_follow(self):
        profile=self.create()
        a=self.client.post('/api/v2/analyze',json={'idempotency_key':'frozen-follow-origin','data_mode':'fixture','risk_portfolio':'MANUAL','timeframe':'1m','profile_id':profile['profile_id']}).json()
        self.assertEqual(a['direction'],'bullish')
        follow=self.client.post('/api/v2/analysis-tracking',json={'analysis_id':a['analysis_id']}).json()
        revision=self.client.post(self.base+'/'+profile['profile_id']+'/revisions',json={'idempotency_key':'frozen-follow-revision','selection':{'strategy_ids':['range_mean_reversion_v2']}})
        self.assertEqual(revision.status_code,200,revision.text)
        app=create_app(self.path,mode='fixture',token=TOKEN,clock=lambda:1800000060000)
        app.state.tracking.tick();row=app.state.tracking.get(follow['tracking_id'])
        with app.state.v2.db.transaction() as c:latest=app.state.v2.db.get(c,'analyses',row.last_analysis_id)
        self.assertEqual(latest['technical_methods']['profile_control']['profile_record_id'],profile['profile_id'])
        self.assertEqual(latest['direction'],'bullish');self.assertIsNone(latest['auto_order_id'])
