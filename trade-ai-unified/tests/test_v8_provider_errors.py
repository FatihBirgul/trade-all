import unittest
from unittest.mock import Mock,MagicMock,patch
from datetime import datetime,timezone
from fastapi.testclient import TestClient
from fixtures import fixture
from unified_forex.official_calendar import fetch_official,parse_schedule
from unified_forex.pilot import export,_safe
from unified_forex.provenance import DatasetDeclaration
from unified_forex.api import app
from forex.core import DataError


class ProviderFailureBoundaries(unittest.TestCase):
    def test_fixed_source_success_oversize_bad_encoding_and_invalid_date(self):
        payload=b'<h4>2027 FOMC Meetings</h4><div class="fomc-meeting__month">January</div><div class="fomc-meeting__date">26-27</div>'
        for raw,expected in [(payload,'OFFICIAL_SCHEDULE_PARSED'),(b'x'*512001,'DATA_UNAVAILABLE'),(b'\xff','DATA_UNAVAILABLE')]:
            response=MagicMock();response.iter_bytes.return_value=iter([raw])
            client=MagicMock();client.stream.return_value.__enter__.return_value=response
            with patch('httpx.Client') as factory:
                factory.return_value.__enter__.return_value=client
                self.assertEqual(fetch_official('fed_calendar',usage_reviewed=True)['data_status'],expected)
                client.stream.assert_called_once_with('GET','https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm')
        now=datetime.now(timezone.utc)
        bad=parse_schedule('<dt>31/02/2027</dt><dd>monetary policy meeting</dd>','ecb',retrieved_at=now)
        self.assertEqual(bad['events'],[]);self.assertTrue(bad['issues'])
    def test_pilot_missing_margin_and_sensitive_scalars_remain_redacted(self):
        p=fixture();p.health=Mock(return_value={'connected':True});p.margin_for=Mock(side_effect=DataError('private account=123'))
        r=export(p,('XAUUSD',));self.assertEqual(r['symbols']['XAUUSD']['margin_status'],'UNAVAILABLE')
        self.assertNotIn('private account',str(r))
        self.assertIsNone(_safe(float('nan')));self.assertEqual(_safe('C:\\user\\terminal'),'REDACTED')
        self.assertEqual(_safe(['BUY','SELL']),['BUY','SELL'])
    def test_api_unavailable_provider_and_invalid_provenance_errors(self):
        app.state.provider=None
        try:
            with patch('unified_forex.api.ContractMT5Provider',side_effect=DataError('binding unavailable')):
                r=TestClient(app).get('/api/v6/health')
                self.assertEqual(r.status_code,503);self.assertEqual(r.json()['detail']['status'],'PROVIDER_UNAVAILABLE')
        finally:app.state.provider=None
        for change in ({'timezone':'Broken/Zone'},{'source_url':'https://user:password@example.org/data'},{'source_url':'file:///etc/passwd'}):
            with self.assertRaises(ValueError):DatasetDeclaration.model_validate({'retrieved_at':'2026-01-01T00:00:00Z',**change})
