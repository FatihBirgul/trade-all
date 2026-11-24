import unittest
from unittest.mock import patch
from fixtures import fixture,NOW
from unified_forex.engine import AnalysisEngine
from unified_forex import strategies


class EngineIntegration(unittest.TestCase):
    def test_buy_sell_actual_private_functions_and_risk(self):
        for side in ('BUY','SELL'):
            p=fixture(side);e=AnalysisEngine()
            result=e.analyze(p,'XAUUSD',now=NOW,balance=10000)
            self.assertEqual(result.final_decision,side+'_CANDIDATE',result.decision_reasons)
            self.assertEqual(result.integration_status,'PRIVATE_INTEGRATED')
            self.assertEqual(result.candlestick_patterns['status'],'available')
            self.assertEqual(result.chart_patterns['status'],'available')
            self.assertEqual(result.confluence['source_engine'],'trade-ai-v2-confluence')
            self.assertGreater(result.lot_size,0);self.assertLessEqual(result.risk_amount,100)
            self.assertEqual(result,e.analyze(p,'XAUUSD',now=NOW,balance=10000))
            self.assertEqual(result.entry_zone['price_side'],'ask' if side=='BUY' else 'bid')

    def test_fail_closed_end_to_end(self):
        cases=[('spread','NO_TRADE'),('metadata','NO_TRADE'),('hours','NO_TRADE'),
               ('unfinished','INSUFFICIENT_DATA'),('stale','STALE_DATA'),('closed','MARKET_CLOSED')]
        for name,expected in cases:
            p=fixture();m=p.data['XAUUSD']['metadata']
            if name=='spread':m['max_spread']=.01
            elif name=='metadata':del m['contract_size']
            elif name=='hours':m['broker_hours_verified']=False
            elif name=='unfinished':p.data['XAUUSD']['candles']['M15'][-1]['is_final']=False
            elif name=='stale':p.data['XAUUSD']['quote']['time']=NOW-500
            else:m['trade_allowed']=False
            r=AnalysisEngine().analyze(p,'XAUUSD',now=NOW,balance=10000)
            self.assertEqual(r.final_decision,expected,(name,r.decision_reasons))
            self.assertIsNone(r.entry_zone);self.assertIsNone(r.lot_size)

    def test_strategy_conflict_precedes_priority_and_plan(self):
        original=strategies.assess
        def opposing(*args):
            rows=original(*args)
            rows[0].update(status='CONFIRMED',direction='BUY')
            rows[2].update(status='CONFIRMED',direction='SELL')
            return rows
        with patch.object(strategies,'assess',side_effect=opposing):
            r=AnalysisEngine().analyze(fixture(),'XAUUSD',now=NOW,balance=10000)
        self.assertEqual(r.final_decision,'WAIT')
        self.assertIsNone(r.entry_zone);self.assertIsNone(r.lot_size)

    def test_tick_volume_never_unlocks_vwap(self):
        r=AnalysisEngine().analyze(fixture(),'XAUUSD',now=NOW)
        self.assertEqual(r.market_structure['price_action']['vwap']['reason'],'real_volume_required')
        self.assertIn('real_volume',r.missing_capabilities)
        self.assertIsNone(r.lot_size)
        self.assertEqual(r.trading_eligibility,'NOT_EVALUATED')

    def test_provider_failure_and_unknown_regime(self):
        p=fixture()
        with patch.object(p,'candles',side_effect=RuntimeError('private exception')):
            r=AnalysisEngine().analyze(p,'XAUUSD',now=NOW)
        self.assertEqual(r.final_decision,'PROVIDER_UNAVAILABLE')
        self.assertNotIn('private exception',r.model_dump_json())
        p=fixture()
        for rows in p.data['XAUUSD']['candles'].values():
            for b in rows:b.update(open=2000,high=2000,low=2000,close=2000)
        p.data['XAUUSD']['quote'].update(bid=2000,ask=2000.2)
        r=AnalysisEngine().analyze(p,'XAUUSD',now=NOW)
        self.assertEqual(r.regime['label'],'UNKNOWN')
        self.assertEqual(r.final_decision,'WAIT');self.assertIsNone(r.entry_zone)

    def test_account_currency_and_minimum_lot_veto(self):
        p=fixture();p.data['XAUUSD']['metadata']['account_currency']='EUR'
        r=AnalysisEngine().analyze(p,'XAUUSD',now=NOW,balance=10000)
        self.assertEqual(r.final_decision,'NO_TRADE');self.assertIsNone(r.lot_size)
        r=AnalysisEngine().analyze(fixture(),'XAUUSD',now=NOW,balance=1)
        self.assertEqual(r.final_decision,'NO_TRADE');self.assertIsNone(r.lot_size)

    def test_real_confirmed_structure_reaches_confluence_once(self):
        p=fixture();p.data['XAUUSD']['candles']['M15'][210]['high']=2023
        r=AnalysisEngine().analyze(p,'XAUUSD',now=NOW)
        self.assertTrue(r.market_structure['price_action']['structure']['events'])
        self.assertIn('v2_structure',{e['source'] for e in r.confluence['input_observations']})
        self.assertEqual(r.confluence['deduplicated_evidence_count'],1)

    def test_live_asof_is_after_reads_without_advancing_replay(self):
        from datetime import datetime,timezone
        p=fixture();original=p.quote
        with patch('unified_forex.engine.datetime') as clock,patch.object(p,'quote') as quote:
            clock.now.return_value=datetime.fromtimestamp(NOW,timezone.utc)
            clock.fromtimestamp.side_effect=datetime.fromtimestamp
            def advancing(symbol):
                result=original(symbol);result['time']=NOW+1
                clock.now.return_value=datetime.fromtimestamp(NOW+2,timezone.utc)
                return result
            quote.side_effect=advancing
            live=AnalysisEngine().analyze(p,'XAUUSD')
            self.assertEqual(live.final_decision,'BUY_CANDIDATE',live.decision_reasons)
            self.assertEqual(quote.call_count,1)
            replay=AnalysisEngine().analyze(p,'XAUUSD',now=NOW)
            self.assertEqual(replay.final_decision,'STALE_DATA')

    def test_missing_higher_timeframe_is_not_a_healthy_wait(self):
        p=fixture();p.data['XAUUSD']['candles']['H4']=[]
        r=AnalysisEngine().analyze(p,'XAUUSD',now=NOW)
        self.assertEqual(r.final_decision,'INSUFFICIENT_DATA')
        self.assertEqual(r.data_status,'DATA_UNAVAILABLE')
        p=fixture();p.data['XAUUSD']['candles']['H4']=fixture('SELL').data['XAUUSD']['candles']['H4']
        r=AnalysisEngine().analyze(p,'XAUUSD',now=NOW)
        self.assertEqual(r.final_decision,'WAIT');self.assertEqual(r.data_status,'OK')
        self.assertIsNone(r.entry_zone)
