import unittest
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import patch
from types import SimpleNamespace
from fixtures import META, fixture, NOW
from forex.core import size_lots, reward_risk_after_costs, DataError
from forex.sessions import broker_status
from unified_forex.research import dataset_from_provider, ResearchConfig, run_backtest


class FinancialRecovery(unittest.TestCase):
    def test_asymmetric_tick_value_loss_and_profit_independent_oracle(self):
        m={**META,'tick_value_loss':2,'tick_value_profit':.5}
        # One-dollar stop=100 ticks:200 loss, two-dollar target=100 reward.
        for side,stop,target in [('BUY',1999,2002),('SELL',2001,1998)]:
            r=reward_risk_after_costs(dict(direction=side,entry=2000,stop_loss=stop,take_profit_1=target),m,5,.1)
            self.assertAlmostEqual(r['net_reward_risk'],95/225)
            self.assertAlmostEqual(r['gross_reward_risk'],.5)
            self.assertAlmostEqual(r['gross_price_reward_risk'],2)
            size=size_lots(10000,1,2000,stop,m,side=side,commission_per_lot=5,slippage_price=.1)
            self.assertEqual(size['lots'],.44)
            self.assertAlmostEqual(size['unrounded_risk'],99)

    def test_holiday_override_blocks_previous_overnight_session(self):
        hours={'timezone':'UTC','weekly':{'0':[['22:00','02:00']]},'date_overrides':{'2026-11-03':None}}
        now=datetime(2026,11,3,1,tzinfo=timezone.utc)
        self.assertEqual(broker_status(now,'XAUUSD',True,hours)['status'],'CLOSED')
        hours['date_overrides']['2026-11-03']=[['07:00','12:00']]
        self.assertEqual(broker_status(now,'XAUUSD',True,hours)['status'],'CLOSED')

    def test_next_open_cannot_relocate_frozen_stop_or_target(self):
        d=dataset_from_provider(fixture(n=270,frames=('M15',)),'XAUUSD','M15',270)
        bars=d.frames['15m'];entry=bars[250].open
        # Unfavorable open above TP: must reject, never move the target to create2R.
        fake=SimpleNamespace(final_decision='BUY_CANDIDATE',legacy_signal='BUY',
             entry_zone={'low':entry-5},stop_loss=entry-6,take_profit_1=entry-3,
             routing={'strategy_id':'fx_trend_momentum_v6'},regime={'regime':'trend'})
        c=ResearchConfig('15m',bars[250].open_time_ms,bars[-1].close_time_ms)
        with patch('unified_forex.research.AnalysisEngine.analyze',return_value=fake):
            result=run_backtest(d,c,fee_bps='0',spread_bps='0',slippage_bps='0')
        self.assertEqual(result['closed_trades'],[])
        self.assertEqual(result['open_positions'],0)

    def test_broker_stop_sign_and_currency_fail_closed(self):
        with self.assertRaises(DataError):size_lots(10000,1,2000,1999,META,calc_profit=lambda *a:10)
        with self.assertRaises(DataError):size_lots(10000,1,2000,1999,{**META,'account_currency':'EUR'})
