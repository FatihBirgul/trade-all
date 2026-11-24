"""Deterministic USC and four-alias contract checks; no live broker claims."""
import unittest
from types import SimpleNamespace

from forex.core import DataError, size_lots
from forex.providers import MT5Provider
from forex.unified import unified_analyze
from test_forex import fixture, NOW


ALIASES = {symbol: symbol+'c' for symbol in ('XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY')}


class CentTerminal:
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    def initialize(self): return True
    def symbol_select(self, symbol, enabled): return enabled and symbol in ALIASES.values()
    def account_info(self): return SimpleNamespace(currency='USC', trade_allowed=True,
                                                    server='fixture-cent-server')
    def symbol_info(self, symbol):
        if symbol not in ALIASES.values(): return None
        base, quote = symbol[:3], symbol[3:6]
        return SimpleNamespace(currency_base=base, currency_profit=quote, trade_mode=4,
                               trade_contract_size=1 if base=='XAU' else 1000,
                               trade_tick_size=.001 if base=='XAU' else .00001,
                               trade_tick_value=.1 if base=='XAU' else 1,
                               point=.001 if base=='XAU' else .00001,
                               volume_min=.01, volume_max=10, volume_step=.01,
                               trade_stops_level=10)
    def order_calc_profit(self, typ, symbol, lots, entry, stop):
        info = self.symbol_info(symbol)
        sign = 1 if typ==self.ORDER_TYPE_BUY else -1
        return (stop-entry)*sign/info.trade_tick_size*info.trade_tick_value*lots


class CentContract(unittest.TestCase):
    def test_four_exact_aliases_and_usc_identity(self):
        provider = MT5Provider(CentTerminal(), ALIASES)
        for symbol, alias in ALIASES.items():
            with self.subTest(symbol=symbol):
                meta = provider.metadata(symbol)
                self.assertEqual(meta['broker_symbol'], alias)
                self.assertEqual(meta['account_currency'], 'USC')
                self.assertEqual(meta['tick_value_currency'], 'USC')
                self.assertEqual(meta['allowed_directions'], ['BUY', 'SELL'])

    def test_usc_buy_sell_risk_and_currency_veto(self):
        provider = MT5Provider(CentTerminal(), ALIASES)
        for symbol in ALIASES:
            meta = provider.metadata(symbol)
            entry = 2000 if symbol=='XAUUSD' else 1.2
            distance = .1 if symbol=='XAUUSD' else .001
            for side in ('BUY', 'SELL'):
                stop = entry-distance if side=='BUY' else entry+distance
                with self.subTest(symbol=symbol, side=side):
                    result = size_lots(10000, 1, entry, stop, meta,
                        lambda s,l,e,x: provider.loss_for(symbol,s,l,e,x), side, 'USC')
                    self.assertEqual(result['currency'], 'USC')
                    self.assertLessEqual(result['unrounded_risk'], 100)
                    self.assertGreaterEqual(result['lots'], meta['volume_min'])
                    self.assertLessEqual(result['lots'], meta['volume_max'])
                    with self.assertRaisesRegex(DataError, 'currency'):
                        size_lots(10000, 1, entry, stop, meta, side=side,
                                  account_currency='USD')

    def test_minimum_lot_and_response_currency(self):
        meta = MT5Provider(CentTerminal(), ALIASES).metadata('XAUUSD')
        with self.assertRaisesRegex(DataError, 'minimum lot'):
            size_lots(1, 1, 2000, 1990, meta, side='BUY', account_currency='USC')
        p = fixture()
        p.data['XAUUSD']['metadata'].update(account_currency='USC', tick_value_currency='USC',
                                             broker_symbol='XAUUSDc')
        report = unified_analyze(p, 'XAUUSD', now=NOW, balance=10000)
        self.assertEqual(report.account_currency, 'USC')
        self.assertEqual(report.broker_symbol, 'XAUUSDc')
        self.assertGreater(report.spread, 0)

    def test_broker_profit_must_agree_with_declared_tick_loss(self):
        meta = MT5Provider(CentTerminal(), ALIASES).metadata('XAUUSD')
        with self.assertRaisesRegex(DataError, 'broker profit disagrees'):
            size_lots(10000, 1, 2000, 1999, meta,
                      lambda side, lots, entry, stop: -50*lots,
                      side='BUY', account_currency='USC')

    def test_broker_cent_rounding_uses_larger_read_only_sample(self):
        meta = MT5Provider(CentTerminal(), ALIASES).metadata('XAUUSD')
        samples=[]
        def rounded_profit(side,lots,entry,stop):
            samples.append(lots)
            return round((stop-entry)*100*lots, 2)
        result=size_lots(10000,1,2000,1999.99,meta,rounded_profit,
                         side='BUY',account_currency='USC')
        self.assertEqual(samples[0],1.0)
        self.assertGreater(result['lots'],0)
        self.assertEqual(result['currency'],'USC')


if __name__ == '__main__': unittest.main()
