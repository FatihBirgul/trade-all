"""SYNTHETIC_TEST_EVIDENCE API scenarios, shared by TestClient and loopback QA."""
import copy
from datetime import datetime, timezone

from forex.broker_contract import contract_observation
from forex.historical_sessions import HistoricalEvidenceStore
from forex.providers import MT5Provider
from forex.spread_policy import bind_rule
from historical_fixture import document, evaluate, trusted_store, write_candidate, window
from test_broker_readiness import metadata, policy as spread_policy
from test_exness_session_gap import rows_after_break, stamp

AS_OF = stamp(10,4)


class HistoricalApiProvider(MT5Provider):
    name = 'fixture-test-only'

    def __init__(self, folder, scenario='valid'):
        doc=document()
        if scenario == 'weekly': doc['source']['kind']='CURRENT_WEEKLY_ONLY'
        if scenario == 'operator': doc['source']['kind']='OPERATOR_DECLARED'
        if scenario == 'wrong_symbol': doc=document('EURUSD')
        if scenario == 'wrong_broker': doc['server']='Other-Broker'
        if scenario == 'conflicting': doc['conflicts']=['SYNTHETIC_TEST_EVIDENCE conflicting source']
        if scenario == 'partial':
            cutoff='2026-11-09T22:30:00Z'
            doc['coverage']=[window('2026-11-06T00:00:00Z',cutoff)]
            for key in ('quote_open','trade_open','close_only','maintenance','weekend_closed'):
                doc[key]=[w for w in doc[key] if w['end_utc']<=cutoff]
        self.store=trusted_store(folder,doc)
        if scenario == 'none': self.store=HistoricalEvidenceStore()
        if scenario == 'unreviewed': self.store=HistoricalEvidenceStore([write_candidate(folder,doc)])
        self.meta=metadata()
        self.meta.update(price_kind='bid',broker_hours=None,broker_hours_status='UNVERIFIED_REAL_SESSION',
                         source=self.name,trade_allowed=True)
        self.meta['broker_contract']=contract_observation(self.meta,'2026-11-10T04:00:00Z')
        if scenario == 'bad_contract': self.meta['broker_contract']['status']='CONFLICTING'
        approved=scenario != 'spread_unapproved'
        self.meta['spread_policy']=bind_rule(spread_policy(maximum=.2 if approved else None, approved=approved),
                                           'XAUUSD','XAUUSDc','Exness-MT5Real50','USC')
        self.rows=rows_after_break()
        for row in self.rows: row['tick_volume']=1
        if scenario == 'open_gap': self.rows.pop(210)
        self.calls=[]

    def account_preflight(self, policy, server, currency):
        assert (policy,server,currency)==('REAL_READONLY_DATA','Exness-MT5Real50','USC')
        return {'status':'PASS','currency':'USC','balance':None}

    def metadata(self,symbol): return copy.deepcopy(self.meta)
    def quote(self,symbol): return {'symbol':symbol,'provider':self.name,'bid':100,'ask':100.1,'time':AS_OF-1}
    def candles(self,symbol,timeframe,count=220): return copy.deepcopy(self.rows[-count:])
    def historical_session_policy(self,symbol,as_of): return evaluate(self.store,as_of=as_of)


ENV = {'MT5_ANALYSIS_POLICY':'REAL_READONLY_DATA','MT5_EXPECTED_REAL_SERVER':'Exness-MT5Real50',
       'MT5_EXPECTED_REAL_CURRENCY':'USC'}
