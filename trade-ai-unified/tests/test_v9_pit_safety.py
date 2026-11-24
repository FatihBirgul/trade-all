import unittest
from copy import deepcopy
from dataclasses import replace
from fixtures import fixture
from unified_forex.research import HistoricalDataset,dataset_from_provider,run_oos
from market_ai.v2.walk_forward import WalkForwardConfig,Candidate
from unified_forex.strategies import TREND


class PointInTimeIdentity(unittest.TestCase):
    def test_epoch_cannot_switch_broker_source_or_account_currency_even_while_flat(self):
        d=dataset_from_provider(fixture(n=270,frames=('M15',)),'XAUUSD','M15',270);b=d.frames['15m']
        for changes in ({'broker_server':'other-broker'},{'source':'different-feed'},{'account_currency':'EUR','tick_value_currency':'EUR'}):
            epoch={'effective_from_ms':b[0].open_time_ms,'effective_to_ms':b[-1].close_time_ms+1,'source':'declared','rules':{**d.metadata(),**changes}}
            with self.assertRaises(ValueError):HistoricalDataset(dict(d.frames),d.metadata(),data_kind='synthetic',data_version='bad',rule_epochs=[epoch])
    def test_held_out_ask_revision_changes_experiment_not_prior_selection(self):
        d=dataset_from_provider(fixture(n=420,frames=('M15',)),'XAUUSD','M15',420);bars=d.frames['15m']
        asks=[replace(b,instrument=replace(b.instrument,price_kind='ask'),open=b.open+.1,high=b.high+.1,low=b.low+.1,close=b.close+.1) for b in bars]
        a=HistoricalDataset(dict(d.frames),d.metadata(),data_kind='synthetic',data_version='paired-oos',ask_frames={'15m':asks})
        config=WalkForwardConfig(train_bars=330,test_bars=40,warmup_bars=250,max_folds=1,simulate_orders=True,timeframe='15m',
            candidates=(Candidate('trend',(TREND,),10),),fee_bps='0',spread_bps='0',slippage_bps='0')
        first=run_oos(a,config);start=first['folds'][0]['indices']['test_start']
        for i in range(start,len(asks)):asks[i]=replace(asks[i],high=asks[i].high+.02)
        b=HistoricalDataset(dict(d.frames),d.metadata(),data_kind='synthetic',data_version='paired-oos',ask_frames={'15m':asks})
        second=run_oos(b,config)
        self.assertNotEqual(first['experiment_id'],second['experiment_id'])
        self.assertEqual(first['folds'][0]['frozen_parameters_hash'],second['folds'][0]['frozen_parameters_hash'])
