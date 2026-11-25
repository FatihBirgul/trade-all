"""V10: analysis is no longer limited to the four legacy symbols."""
import unittest
from copy import deepcopy
from fixtures import fixture, NOW
from forex.providers import FixtureProvider
from forex.core import SYMBOLS, DataError, is_supported_symbol, analyze
from forex.contracts import capture
from unified_forex.engine import AnalysisEngine


def renamed(symbol, direction='BUY'):
    """The XAUUSD fixture under another broker symbol, declared as spot Forex."""
    item = deepcopy(fixture(direction, frames=('M15', 'H1', 'H4')).data['XAUUSD'])
    item['metadata'].update(symbol=symbol, broker_symbol=symbol + '.test', market_type='forex_spot',
                            contract_type='spot', profit_currency=symbol[-3:])
    return FixtureProvider({symbol: item})


class BrokerSymbols(unittest.TestCase):
    def test_predicate(self):
        for symbol in SYMBOLS + ('AUDNZD', 'BTCUSD', 'XAGUSD', 'US30', 'USDCNH'):
            self.assertTrue(is_supported_symbol(symbol), symbol)
        for symbol in ('eur/usd', 'EUR/USD', 'eurusd', 'EURUSDc', 'EU', 'A' * 13, '', None, 5, 'EUR USD', 'EURUSD\n'):
            self.assertFalse(is_supported_symbol(symbol), repr(symbol))

    def test_legacy_symbols_tuple_is_unchanged(self):
        self.assertEqual(SYMBOLS, ('XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY'))

    def test_engine_analyzes_non_legacy_symbol(self):
        for side in ('BUY', 'SELL'):
            result = AnalysisEngine().analyze(renamed('AUDNZD', side), 'AUDNZD', 'M15', now=NOW,
                                              confirmations=('H1', 'H4'), balance=10000)
            self.assertNotEqual(result.final_decision, 'PROVIDER_UNAVAILABLE', result.decision_reasons)
            self.assertNotIn('unsupported symbol', ' '.join(result.decision_reasons))
            self.assertEqual(result.final_decision, side + '_CANDIDATE', result.decision_reasons)
            self.assertEqual(result.symbol, 'AUDNZD')

    def test_capture_and_legacy_analyze_accept_broker_symbol(self):
        snapshot = capture(renamed('BTCUSD'), 'BTCUSD', 'M15', NOW)
        self.assertEqual(snapshot.payload()['symbol'], 'BTCUSD')
        self.assertEqual(analyze(renamed('BTCUSD'), 'BTCUSD', now=NOW)['data_status'], 'OK')

    def test_rejects_malformed_symbol(self):
        provider = renamed('AUDNZD')
        for symbol in ('eur/usd', 'audnzd', 'AUDNZD;DROP'):
            with self.assertRaises(DataError):
                capture(provider, symbol, 'M15', NOW)
            with self.assertRaises(DataError):
                analyze(provider, symbol, now=NOW)
            result = AnalysisEngine().analyze(provider, symbol, now=NOW)
            self.assertNotIn(result.final_decision, ('BUY_CANDIDATE', 'SELL_CANDIDATE'))
            self.assertEqual(result.trading_eligibility, 'BLOCKED')


if __name__ == '__main__':
    unittest.main()
