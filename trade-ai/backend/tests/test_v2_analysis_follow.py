from pathlib import Path
from contextlib import closing
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import secrets
from fastapi.testclient import TestClient
from market_ai.v2.api import create_app
from market_ai.v2.spot_provider import FixtureSpotProvider,ProviderUnavailable
from market_ai.v2.errors import V2Error
from market_ai.v2.tracking import TrackingWorker

class Switchable(FixtureSpotProvider):
    offline=True
    def rules(self,symbol):
        if self.offline:raise ProviderUnavailable('controlled offline')
        return super().rules(symbol)

class AnalysisFollowTests(TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'product.sqlite';self.now=1792584000000
        self.provider=Switchable();self.token=secrets.token_urlsafe(32)
        self.app=create_app(self.path,mode='fixture',token=self.token,provider=self.provider,clock=lambda:self.now)
        self.client=TestClient(self.app);self.addCleanup(self.client.close)
        self.client.headers['Authorization']='Bearer '+self.token
    def seed(self,account='MANUAL'):
        result=self.client.post('/api/v2/analyze',json={'timeframe':'1m','data_mode':'fixture','risk_portfolio':account,'idempotency_key':'follow-seed-'+account}).json()
        self.assertEqual(result['direction'],'WAIT')
        return result
    def start(self,account='MANUAL'):
        a=self.seed(account);r=self.client.post('/api/v2/analysis-tracking',json={'analysis_id':a['analysis_id']})
        self.assertEqual(r.status_code,200,r.text)
        return a,r.json()
    def test_wait_follow_change_dedup_stop_and_account_isolation(self):
        original,track=self.start()
        self.assertFalse(track['worker_running'])
        self.assertEqual(self.client.post('/api/v2/analysis-tracking',json={'analysis_id':original['analysis_id']}).json()['tracking_id'],track['tracking_id'])
        service=self.app.state.tracking
        service.tick();self.assertEqual(self.client.get('/api/v2/notifications').json(),[])
        self.now+=60000;self.provider.offline=False
        service.tick();notifications=self.client.get('/api/v2/notifications').json()
        self.assertEqual(len(notifications),1)
        details=notifications[0]['details'];self.assertEqual(details['portfolio_id'],'MANUAL')
        result=self.client.get('/api/v2/analyses/'+details['analysis_id']).json()
        self.assertEqual(result['risk_portfolio'],'MANUAL');self.assertIsNone(result['auto_order_id'])
        self.now+=60000;service.tick()
        self.assertEqual(len(self.client.get('/api/v2/notifications').json()),1)
        key=track['tracking_id']
        self.assertFalse(self.client.post('/api/v2/analysis-tracking/'+key,json={'enabled':False}).json()['enabled'])
        before=len(self.client.get('/api/v2/analyses').json());self.now+=60000;self.assertEqual(service.tick(),[])
        self.assertEqual(len(self.client.get('/api/v2/analyses').json()),before)
        for account in ['AUTO','MANUAL']:self.assertEqual(self.client.get('/api/v2/portfolios/'+account+'/orders').json(),[])
        self.assertEqual(self.client.get('/api/v2/analyses/'+original['analysis_id']).json(),original)
    def test_restart_atomic_outbox_rollback_and_recovery(self):
        original,track=self.start();self.provider.offline=False
        with patch.object(self.app.state.v2.scanner,'_notify',side_effect=V2Error('INJECTED','controlled failure')):
            self.app.state.tracking.tick()
        self.assertEqual(self.client.get('/api/v2/notifications').json(),[])
        app=create_app(self.path,mode='fixture',token=self.token,provider=self.provider,clock=lambda:self.now)
        self.now+=60000;app.state.tracking.tick();app.state.tracking.tick()
        self.assertEqual(len(self.client.get('/api/v2/notifications').json()),1)
        row=self.client.get('/api/v2/analysis-tracking/'+track['tracking_id']).json()
        self.assertEqual(row['notified_changes'],1)
        self.assertEqual(row['origin_analysis_id'],original['analysis_id'])
    def test_auth_missing_record_reject_extra_fields_and_worker_stop(self):
        self.assertEqual(self.client.get('/api/v2/analysis-tracking',headers={'Authorization':'Bearer wrong'}).status_code,401)
        self.assertEqual(self.client.post('/api/v2/analysis-tracking',json={'analysis_id':'a'*64}).status_code,404)
        self.assertEqual(self.client.post('/api/v2/analysis-tracking',json={'analysis_id':'a'*64,'auto_paper':True}).status_code,422)
        worker=TrackingWorker(self.app.state.tracking);worker.start();worker.stop()
        self.assertFalse(worker.thread.is_alive())
    def test_resume_cannot_bypass_active_limit_and_repeat_change_is_noop(self):
        tracks=[]
        for index in range(7):
            self.now+=60000
            symbol=['BTCUSDT','ETHUSDT','SOLUSDT'][index%3]
            tf=['1m','5m','15m'][index//3]
            response=self.client.post('/api/v2/analyze',json={'symbol':symbol,'timeframe':tf,'data_mode':'fixture','risk_portfolio':'MANUAL','idempotency_key':'limit-test-'+str(index)})
            self.assertEqual(response.status_code,200,response.text)
            a=response.json()
            response=self.client.post('/api/v2/analysis-tracking',json={'analysis_id':a['analysis_id']})
            if index<6:
                self.assertEqual(response.status_code,200,response.text);tracks.append(response.json())
            else:
                self.assertEqual(response.status_code,409)
                self.client.post('/api/v2/analysis-tracking/'+tracks[0]['tracking_id'],json={'enabled':False})
                self.assertEqual(self.client.post('/api/v2/analysis-tracking',json={'analysis_id':a['analysis_id']}).status_code,200)
        self.assertEqual(self.client.post('/api/v2/analysis-tracking/'+tracks[0]['tracking_id'],json={'enabled':True}).status_code,409)
        service=self.app.state.tracking;service.tick()
        before=service.get(tracks[1]['tracking_id']).model_dump()
        self.assertEqual(service.change(tracks[1]['tracking_id'],True).model_dump(),before)
    def test_provider_outage_backoff_and_recovery_do_not_repeat_same_condition(self):
        _,track=self.start();service=self.app.state.tracking
        service.tick();self.now+=60000;service.tick()
        checked=service.get(track['tracking_id']).last_checked_ms
        self.now+=60000;self.assertEqual(service.tick(),[])
        self.assertEqual(service.get(track['tracking_id']).last_checked_ms,checked)
        self.now+=60000;self.provider.offline=False;service.tick()
        self.assertEqual(len(self.client.get('/api/v2/notifications').json()),1)
        self.now+=60000;self.provider.offline=True;service.tick()
        self.assertEqual(service.get(track['tracking_id']).status,'waiting_data')
        self.now+=60000;self.provider.offline=False;service.tick()
        self.assertEqual(len(self.client.get('/api/v2/notifications').json()),1)
    def test_shared_scanner_lease_and_stop_in_flight_prevent_commit(self):
        _,track=self.start();service=self.app.state.tracking
        with service.db.transaction() as c:
            state=service.db.get(c,'scanner_state','state');state.update(lease_id='other',lease_until_ms=self.now+120000)
            service.db.update(c,'scanner_state','state',state)
        self.assertEqual(service.tick(),[])
        self.now+=120001
        original=self.app.state.v2.analysis.analyze
        def stop_first(request,**kwargs):
            service.change(track['tracking_id'],False)
            return original(request,**kwargs)
        before=len(self.client.get('/api/v2/analyses').json())
        with patch.object(self.app.state.v2.analysis,'analyze',side_effect=stop_first):service.tick()
        self.assertEqual(len(self.client.get('/api/v2/analyses').json()),before)
        self.assertEqual(self.client.get('/api/v2/notifications').json(),[])
    def test_backup_preserves_tracking_and_rejects_corrupt_projection(self):
        from scripts.backup_v2 import copy_database
        from sqlite3 import connect
        _,track=self.start()
        saved=Path(self.temp.name)/'backup.sqlite'
        self.assertEqual(copy_database(self.path,saved)['status'],'verified')
        app=create_app(saved,mode='fixture',token=self.token,provider=self.provider,clock=lambda:self.now)
        self.assertEqual(app.state.tracking.get(track['tracking_id']).origin_analysis_id,track['origin_analysis_id'])
        with closing(connect(saved)) as c:
            with c:
                c.execute("UPDATE analysis_tracking SET body='{}'")
        with self.assertRaises(V2Error):copy_database(saved,Path(self.temp.name)/'invalid.sqlite')
    def test_expired_future_missing_and_bad_quality_never_notify_a_direction(self):
        from market_ai.v2.tracking import condition
        from market_ai.v2.api_models import AnalysisResponse
        self.provider.offline=False
        a=AnalysisResponse.model_validate(self.client.post('/api/v2/analyze',json={'timeframe':'1m','data_mode':'fixture','idempotency_key':'freshness-baseline'}).json())
        self.assertTrue(condition(a,self.now)[1])
        for updates in ({'expires_at_ms':self.now-1}, {'price_time_ms':self.now+1}, {'price':None}, {'quality':{'ok':False}}):
            candidate=a.model_copy(update={**updates,'direction':'bullish'})
            _,fresh,direction,reason=condition(candidate,self.now)
            self.assertFalse(fresh);self.assertEqual(direction,'WAIT');self.assertEqual(reason,'stale_analysis')
    def test_opt_in_factory_worker_runs_after_restart_and_stops_on_shutdown(self):
        import os
        from threading import Event
        from market_ai.v2.api import app_from_env
        original,track=self.start()
        done=Event()
        # Keep the actual env factory, real worker and all assertions, but bind
        # its production create_app call to the fixture clock. Wall time can cross
        # a 1m expiry between analysis and condition(), legitimately yielding no alert.
        with patch.dict(os.environ,{'V2_DB_PATH':str(self.path),'V2_API_TOKEN':self.token,'V2_DATA_MODE':'fixture','V2_TRACKING_WORKER':'1'}):
            with patch('market_ai.v2.api.create_app',side_effect=lambda *args,**kw:create_app(*args,**kw,clock=lambda:self.now+60000)):
                app=app_from_env()
        service=app.state.tracking;tick=service.tick
        def observed_tick():
            try:return tick()
            finally:done.set()
        with patch.object(service,'tick',side_effect=observed_tick):
            with TestClient(app) as client:
                client.headers['Authorization']='Bearer '+self.token
                self.assertTrue(done.wait(5),'Worker did not execute its first bounded tick')
                row=client.get('/api/v2/analysis-tracking/'+track['tracking_id']).json()
                self.assertTrue(row['worker_running'])
                events=client.get('/api/v2/notifications').json()
                self.assertEqual(len(events),1)
                self.assertEqual(events[0]['details']['tracking_id'],track['tracking_id'])
                self.assertEqual(events[0]['delivery_status'],'pending')
                last=client.get('/api/v2/analyses/'+events[0]['details']['analysis_id']).json()
                self.assertEqual(last['risk_portfolio'],'MANUAL');self.assertIsNone(last['auto_order_id'])
                self.assertEqual(client.get('/api/v2/analyses/'+original['analysis_id']).json(),original)
        self.assertFalse(service.worker.thread.is_alive())
