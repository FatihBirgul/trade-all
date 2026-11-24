import unittest
from fixtures import fixture,NOW,META
from unified_forex.engine import AnalysisEngine
from forex.core import reward_risk_after_costs


class NetRewardOracle(unittest.TestCase):
    def test_independent_buy_sell_cost_ratio(self):
        # 100oz: $100 stop + $10 adverse stop + $5 commission = $115 loss/lot.
        # $200 target - $5 commission = $195 reward/lot: exact ratio39/23.
        for direction,stop,target in (('BUY',1999,2002),('SELL',2001,1998)):
            result=reward_risk_after_costs({'direction':direction,'entry':2000,'stop_loss':stop,'take_profit_1':target},META,5,.1)
            self.assertAlmostEqual(result['net_reward_risk'],39/23,places=9)
            self.assertAlmostEqual(result['gross_reward_risk'],2)

    def test_costs_veto_even_without_sizing_or_balance(self):
        for balance in (None,10000):
            result=AnalysisEngine().analyze(fixture(),'XAUUSD',now=NOW,balance=balance,commission_per_lot=1000)
            self.assertEqual(result.final_decision,'NO_TRADE')
            self.assertIn('cost-adjusted',result.decision_reasons[0])
            self.assertIsNone(result.entry_zone);self.assertIsNone(result.lot_size)
