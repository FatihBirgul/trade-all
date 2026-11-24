"""Additive diagnostics must not alter route, risk or historical responses."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from fastapi.testclient import TestClient
from market_ai.v2.api import create_app
from market_ai.v2.paper_audit import audit_database
NOW=1800000000000
TOKEN='diagnostic-fixture-not-a-secret-32'

class AnalysisDiagnosticTests(TestCase):
    def analyze(self,client,key='diagnostic-key-one',**kw):
        r=client.post('/api/v2/analyze',json={'data_mode':'fixture','timeframe':'1H','idempotency_key':key,**kw})
        self.assertEqual(r.status_code,200,r.text);return r.json()
    def test_product_exposes_source_bound_diagnostics_in_existing_dictionary(self):
        with TemporaryDirectory(prefix='v2-diagnostics-') as root:
            path=Path(root)/'new.sqlite';app=create_app(path,mode='fixture',token=TOKEN,clock=lambda:NOW,domain_journal=True)
            with TestClient(app,headers={'Authorization':'Bearer '+TOKEN}) as client:
                r=self.analyze(client)
                d=r['technical_methods']['research_context']
                self.assertEqual(r['version'],'v2-product-analysis-3')
                self.assertEqual(d['status'],'available');self.assertFalse(d['trade_permission'])
                self.assertEqual(d['patterns']['validation_status'],'DETECTION_IMPLEMENTED')
                self.assertEqual(d['methods']['methods']['adx14_wilder']['status'],'available')
                self.assertEqual(len(d['source_record_id']),64)
                self.assertEqual(self.analyze(client),r)
            self.assertEqual(audit_database(path,require_domain=True)['status'],'PASS')
    def test_diagnostics_do_not_change_direction_levels_or_risk(self):
        with TemporaryDirectory(prefix='v2-diagnostics-') as root:
            results=[]
            for enabled in (True,False):
                app=create_app(Path(root)/str(enabled),mode='fixture',token=TOKEN,clock=lambda:NOW)
                with TestClient(app,headers={'Authorization':'Bearer '+TOKEN}) as client:
                    if enabled:r=self.analyze(client)
                    else:
                        with patch('market_ai.v2.analysis_service.compute_diagnostics',return_value={'status':'unavailable','reason':'test_only','trade_permission':False}):r=self.analyze(client)
                    results.append(r)
            for key in ('direction','reason','levels','risk','router','regime','supporting_evidence','conflicting_evidence','scenarios'):
                self.assertEqual(results[0][key],results[1][key],key)
    def test_provider_quality_failure_has_no_successful_pattern_context(self):
        with TemporaryDirectory(prefix='v2-diagnostics-') as root:
            app=create_app(Path(root)/'new.sqlite',mode='fixture',token=TOKEN,clock=lambda:NOW)
            with TestClient(app,headers={'Authorization':'Bearer '+TOKEN}) as client:
                r=self.analyze(client,fixture_case='unfinished')
                self.assertEqual(r['direction'],'WAIT');d=r['technical_methods']['research_context']
                self.assertEqual(d['status'],'unavailable');self.assertNotIn('patterns',d)
    def test_optional_diagnostic_failure_is_visible_and_does_not_replace_prices(self):
        with TemporaryDirectory(prefix='v2-diagnostics-') as root:
            app=create_app(Path(root)/'new.sqlite',mode='fixture',token=TOKEN,clock=lambda:NOW)
            with TestClient(app,headers={'Authorization':'Bearer '+TOKEN}) as client:
                with patch('market_ai.v2.analysis_diagnostics.compute_methods',side_effect=RuntimeError('fixture-only')):
                    r=self.analyze(client)
                self.assertEqual(r['technical_methods']['research_context']['reason'],'diagnostic_engine_unavailable')
                self.assertEqual(r['price'],'129.9')
    def test_saved_response_survives_diagnostic_code_failure_and_restart(self):
        with TemporaryDirectory(prefix='v2-diagnostics-') as root:
            path=Path(root)/'new.sqlite'
            app=create_app(path,mode='fixture',token=TOKEN,clock=lambda:NOW)
            with TestClient(app,headers={'Authorization':'Bearer '+TOKEN}) as client:r=self.analyze(client)
            app=create_app(path,mode='fixture',token=TOKEN,clock=lambda:NOW+60000)
            with TestClient(app,headers={'Authorization':'Bearer '+TOKEN}) as client:
                with patch('market_ai.v2.analysis_service.compute_diagnostics',side_effect=AssertionError('historical response must not be recomputed')):
                    self.assertEqual(self.analyze(client),r)
                    detail=client.get('/api/v2/analyses/'+r['analysis_id']);self.assertEqual(detail.json(),r)

    def test_real_version2_example_remains_unchanged_on_read_and_idempotent_retry(self):
        import json
        from market_ai.v2.product_db import ProductDatabase
        from market_ai.v2.api_models import AnalyzeRequest
        legacy=json.loads((Path(__file__).resolve().parents[2]/'docs/v2_examples/analysis.json').read_text())
        self.assertEqual(legacy['version'],'v2-product-analysis-2')
        self.assertNotIn('research_context',legacy['technical_methods'])
        with TemporaryDirectory(prefix='v2-legacy-response-') as root:
            path=Path(root)/'old.sqlite';db=ProductDatabase(path,'fixture')
            request=AnalyzeRequest(data_mode='fixture',idempotency_key='legacy-retry-key')
            with db.transaction() as c:
                db.put(c,'analyses',legacy['analysis_id'],legacy,created_ms=legacy['created_at_ms'])
                db.remember(c,'analyze',request.idempotency_key,request.model_dump(mode='json'),legacy)
            app=create_app(path,mode='fixture',token=TOKEN,clock=lambda:NOW)
            before=path.read_bytes()
            with TestClient(app,headers={'Authorization':'Bearer '+TOKEN}) as client:
                with patch('market_ai.v2.analysis_service.compute_diagnostics',side_effect=AssertionError('legacy record must not be upgraded')):
                    r=client.post('/api/v2/analyze',json=request.model_dump(mode='json'))
                    self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json(),legacy)
                    self.assertEqual(client.get('/api/v2/analyses/'+legacy['analysis_id']).json(),legacy)
            self.assertEqual(path.read_bytes(),before)

    def test_optional_charts_and_session_failures_preserve_existing_diagnostics(self):
        from tests.test_v2_pattern_research import bars,TF
        from market_ai.v2.analysis_diagnostics import compute_diagnostics
        b=bars([(105,105,95,95),(107,117,107,117)])
        for name in ('detect_charts','session_research'):
            with patch('market_ai.v2.analysis_diagnostics.'+name,side_effect=RuntimeError('fixture isolated engine failure')):
                r=compute_diagnostics(b,timeframe='1m',as_of_ms=b[-1].close_time_ms,max_age_ms=TF,tick_size='0.01',source_record_id='fixture-snapshot')
            self.assertEqual(r['status'],'available');self.assertFalse(r['trade_permission']);self.assertEqual(r['patterns']['status'],'available')
            self.assertEqual(r['charts' if name=='detect_charts' else 'session']['status'],'unavailable')
