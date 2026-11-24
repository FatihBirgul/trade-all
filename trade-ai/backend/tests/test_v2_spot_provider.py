"""Public GET adapter contract using HTTP MockTransport, never real sockets."""
import httpx
from unittest import TestCase
from market_ai.v2.spot_provider import BinanceSpotProvider, FixtureSpotProvider, ProviderUnavailable


NOW = 1800000000000


def exchange_info(symbol="BTCUSDT"):
    return {"symbols": [{"symbol": symbol, "baseAsset": "BTC" if symbol == "BTCUSDT" else "ETH", "quoteAsset": "USDT", "status": "TRADING", "isSpotTradingAllowed": True,
        "filters": [{"filterType": "LOT_SIZE", "stepSize": "0.00001", "minQty": "0.00001", "maxQty": "100"},
                    {"filterType": "NOTIONAL", "minNotional": "5"},
                    {"filterType": "PRICE_FILTER", "tickSize": "0.01"}]}]}


class PublicSpotAdapterTests(TestCase):
    def test_closed_spot_identity_and_exclusive_timestamp(self):
        calls = []
        raw = [[NOW-60000, "100", "101", "99", "100", "10", NOW-1]]
        def handle(request):
            calls.append(request)
            return httpx.Response(200, json=raw)
        p = BinanceSpotProvider(transport=httpx.MockTransport(handle))
        bars = p.candles("BTCUSDT", "1m", NOW)
        self.assertEqual(bars[0].close_time_ms, NOW)
        self.assertTrue(bars[0].is_final)
        self.assertEqual(bars[0].instrument.contract_type, "spot")
        self.assertEqual(bars[0].instrument.quote_currency, "USDT")
        self.assertEqual(calls[0].method, "GET")
        self.assertEqual(calls[0].url.path, "/api/v3/klines")
        self.assertEqual(calls[0].url.params["endTime"], str(NOW-1))
        self.assertNotIn("X-MBX-APIKEY", calls[0].headers)

    def test_network_or_server_failure_uses_same_venue_mirror_only(self):
        hosts = []
        def handle(request):
            hosts.append(request.url.host)
            if len(hosts) == 1:
                return httpx.Response(503)
            return httpx.Response(200, json=[[NOW-60000, "100", "101", "99", "100", "10", NOW-1]])
        p = BinanceSpotProvider(transport=httpx.MockTransport(handle))
        self.assertEqual(p.candles("BTCUSDT", "1m", NOW)[0].instrument.venue, "binance")
        self.assertEqual(hosts, ["data-api.binance.vision", "api.binance.com"])

    def test_access_and_rate_limit_do_not_retry_or_switch_to_fixture(self):
        for status in (403, 418, 429, 451):
            calls = []
            def handle(request):
                calls.append(request)
                return httpx.Response(status)
            with self.subTest(status=status), self.assertRaises(ProviderUnavailable):
                BinanceSpotProvider(transport=httpx.MockTransport(handle)).candles("BTCUSDT", "1m", NOW)
            self.assertEqual(len(calls), 1)

    def test_exchange_rules_are_explicit_and_wrong_symbol_rejected(self):
        p = BinanceSpotProvider(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=exchange_info())))
        self.assertEqual(p.rules("BTCUSDT")["quantity_step"], "0.00001")
        bad = BinanceSpotProvider(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=exchange_info("ETHUSDT"))))
        with self.assertRaises(ProviderUnavailable):
            bad.rules("BTCUSDT")

    def test_missing_proxy_transport_dependency_is_provider_unavailable(self):
        from unittest.mock import patch
        with patch("market_ai.v2.spot_provider.httpx.Client",side_effect=ImportError("optional proxy dependency")) as calls:
            with self.assertRaises(ProviderUnavailable) as result:
                BinanceSpotProvider().candles("BTCUSDT","1m",NOW)
        self.assertEqual(str(result.exception),"proxy_transport_unavailable")
        self.assertEqual(calls.call_count,1)
