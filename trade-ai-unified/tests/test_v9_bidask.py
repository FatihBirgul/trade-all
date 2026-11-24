import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch
from fixtures import fixture
from unified_forex.research import HistoricalDataset,ResearchConfig,run_backtest,dataset_from_provider
from unified_forex.data_sides import CAPABILITIES


class PairedSideReplay(unittest.TestCase):
    def test_paired_json_import_binds_explicit_ask_source(self):
        import csv,io,json
        from pathlib import Path
        from tempfile import TemporaryDirectory
        import test_v8_ingestion as fixtures_v8
        from unified_forex.ingestion import import_file
        req=fixtures_v8.LocalHistoricalImport().request();req['data_type']='BID_ASK_OHLC'
        rows=list(csv.DictReader(io.StringIO((Path(__file__).parent/'data/v8_handmade.csv').read_text())))
        for row in rows:
            for key in ('open_time_ms','close_time_ms'):row[key]=int(row[key])
            for key in ('open','high','low','close'):row[key]=float(row[key]);row['ask_'+key]=row[key]+.2
            row['is_final']=True;row['ask_source']=row['source']
        with TemporaryDirectory() as root:
            p=Path(root,'paired.json');p.write_text(json.dumps(rows))
            d,report=import_file(root,'paired.json',req)
            self.assertTrue(d.ask_frames);self.assertEqual(report['spread_history'],'DECLARED_PAIRED_OHLC')
            rows[0]['ask_source']='other-broker-feed';p.write_text(json.dumps(rows))
            with self.assertRaises(ValueError):import_file(root,'paired.json',req)
    def dataset(self):
        d=dataset_from_provider(fixture(n=270,frames=('M15',)),'XAUUSD','M15',270)
        bids=list(d.frames['15m'])
        for i in range(250,len(bids)):bids[i]=replace(bids[i],open=2000,high=2000.5,low=1999.5,close=2000)
        instrument=replace(bids[0].instrument,price_kind='ask')
        asks=[replace(b,instrument=instrument,open=b.open+.2,high=b.high+.2,low=b.low+.2,close=b.close+.2) for b in bids]
        return d,bids,asks
    def test_sell_stop_triggers_on_ask_spike_not_bid_high(self):
        d,bids,asks=self.dataset()
        # Bid never reaches stop2001. Ask high crosses it on the next bar.
        asks[251]=replace(asks[251],high=2001.5)
        paired=HistoricalDataset({'15m':bids},d.metadata(),data_kind='synthetic',data_version='paired-oracle',ask_frames={'15m':asks})
        candidate=SimpleNamespace(final_decision='SELL_CANDIDATE',legacy_signal='SELL',entry_zone={'low':2000},stop_loss=2001,
            take_profit_1=1996,routing={'strategy_id':'fx_trend_momentum_v6'},regime={'regime':'trend'})
        c=ResearchConfig('15m',bids[250].open_time_ms,bids[-1].close_time_ms)
        with patch('unified_forex.research.AnalysisEngine.analyze',return_value=candidate):r=run_backtest(paired,c,fee_bps=0,spread_bps=0,slippage_bps=0)
        t=r['closed_trades'][0]
        self.assertEqual(t['exit_index'],251);self.assertAlmostEqual(float(t['net_pnl_quote']),-100*t['lots'])
        self.assertEqual(r['price_evidence']['spread_evidence'],'DECLARED_OBSERVED_SIDE_BARS')
        self.assertFalse(r['price_evidence']['historical_execution_verified'])
    def test_buy_entry_pays_actual_ask_not_declared_zero_spread(self):
        d,bids,asks=self.dataset();bids[251]=replace(bids[251],high=2004.5,close=2004)
        asks[251]=replace(asks[251],high=2004.7,close=2004.2)
        paired=HistoricalDataset({'15m':bids},d.metadata(),data_kind='synthetic',data_version='buy-paired',ask_frames={'15m':asks})
        candidate=SimpleNamespace(final_decision='BUY_CANDIDATE',legacy_signal='BUY',entry_zone={'low':2000},stop_loss=1999,
            take_profit_1=2004,routing={'strategy_id':'fx_trend_momentum_v6'},regime={'regime':'trend'})
        c=ResearchConfig('15m',bids[250].open_time_ms,bids[-1].close_time_ms)
        with patch('unified_forex.research.AnalysisEngine.analyze',return_value=candidate):r=run_backtest(paired,c,fee_bps=0,spread_bps=0,slippage_bps=0)
        t=r['closed_trades'][0]
        self.assertAlmostEqual(float(t['net_pnl_quote']),380*t['lots'])
        self.assertAlmostEqual(t['r'],380/120)
    def test_side_identity_crossing_timestamps_and_hash_bindings(self):
        d,bids,asks=self.dataset()
        for change in ({'source':'another-source'},{'open':1999},{'open_time_ms':asks[-1].open_time_ms+1}):
            altered=list(asks);altered[-1]=replace(altered[-1],**change)
            with self.assertRaises(ValueError):HistoricalDataset({'15m':bids},d.metadata(),data_kind='synthetic',data_version='bad',ask_frames={'15m':altered})
        a=HistoricalDataset({'15m':bids},d.metadata(),data_kind='synthetic',data_version='test',ask_frames={'15m':asks})
        altered=list(asks);altered[-1]=replace(altered[-1],high=altered[-1].high+.1)
        b=HistoricalDataset({'15m':bids},d.metadata(),data_kind='synthetic',data_version='test',ask_frames={'15m':altered})
        self.assertNotEqual(a.digest,b.digest)
        self.assertFalse(CAPABILITIES['MID_ONLY']['analysis'])
