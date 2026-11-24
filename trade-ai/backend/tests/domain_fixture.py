"""Journal-enabled ASGI scenarios, no sockets or existing database paths."""
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import json
import sqlite3
import httpx

from fastapi.testclient import TestClient
from market_ai.v2.api import create_app
from market_ai.v2 import domain_journal as domain

NOW=1800000000000
TOKEN='domain-fixture-token-not-a-secret-32'


class DomainFixture:
    def setUp(self):
        self.tmp=TemporaryDirectory(prefix='v2-domain-api-');self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'fixture.sqlite';self.now=NOW
        self.restart()

    def restart(self):
        if hasattr(self,'client'):self.client.close()
        self.app=create_app(self.path,mode='fixture',token=TOKEN,clock=lambda:self.now,domain_journal=True)
        self.client=TestClient(self.app,headers={'Authorization':'Bearer '+TOKEN});self.addCleanup(self.client.close)

    def post(self,path,body):
        r=self.client.post('/api/v2/'+path,json=body)
        self.assertEqual(r.status_code,200,r.text);return r.json()

    def order(self, account='MANUAL', key='domain-order-key', quantity='10'):
        a=self.post('analyze',{'data_mode':'fixture','idempotency_key':'analysis-'+key})
        args={'analysis_id':a['analysis_id'],'quantity':quantity,'idempotency_key':key}
        return self.post('portfolios/'+account+'/orders',args),args

    def event(self, **changes):
        start=self.now;self.now+=60000
        body={'symbol':'BTCUSDT','open_time_ms':start,'close_time_ms':self.now,'open':'129.9','high':'130.2',
              'low':'129.5','close':'130','volume':'10000'};body.update(changes)
        return self.post('paper/events',body),body

    def rows(self):
        with closing(sqlite3.connect(self.path)) as c:
            return [json.loads(r[0]) for r in c.execute('SELECT body FROM domain_events ORDER BY sequence')]

    def assert_chain(self):
        with closing(sqlite3.connect(self.path)) as c:domain.validate_chain(c)
