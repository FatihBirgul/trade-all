"""Hand-calculated closed-bar geometry, availability and causal prefixes."""
from dataclasses import replace
from decimal import Decimal as D
from unittest import TestCase
from market_ai.v2.market_data_contract import Candle, Instrument
from market_ai.v2.price_action import compute_price_action

TF = 60000
IDENTITY = Instrument("BTCUSDT", "crypto_spot", "fixture", "last", "spot", "USDT")


def bars(values=None):
    values = values or [100]*30
    return [Candle(IDENTITY, i*TF, (i+1)*TF, True, x, x+1, x-1, x, 10, "real", "fixture_spot") for i,x in enumerate(values)]


def methods(series, **kw):
    return compute_price_action(series, timeframe_ms=TF, as_of_ms=len(series)*TF, max_age_ms=TF, **kw)


class PriceActionTests(TestCase):
    def test_vwap_exact_weighted_typical_price_not_mean_close(self):
        b=bars()
        b[-1]=replace(b[-1], open=101, high=104, low=100, close=102, volume=30)
        expected=(D(100)*190+D(102)*30)/220
        self.assertEqual(D(methods(b)["vwap"]["value"]), expected)
        self.assertEqual(methods(b)["vwap"]["basis"], "rolling_typical_price")

    def test_tick_missing_and_zero_volume_cannot_create_vwap(self):
        for kind, volume, reason in (("tick",10,"real_volume_required"),("unavailable",None,"real_volume_required"),("real",0,"zero_volume")):
            m=methods([replace(b,volume_kind=kind,volume=volume) for b in bars()])
            self.assertEqual(m["vwap"]["reason"], reason)
            self.assertEqual(m["structure"]["status"], "available")

    def test_all_methods_fail_closed_on_bad_ohlc_future_stale_and_nan(self):
        b=bars()
        cases=[b[:-1]+[replace(b[-1],is_final=False)], b[:-1]+[replace(b[-1],high=99)],
               b[:-1]+[replace(b[-1],close=float("nan"))], b[:-1]+[replace(b[-1],volume=float("inf"))], b[:10]+b[11:]]
        for series in cases:
            with self.subTest(series=series[-1]):
                m=methods(series)
                self.assertTrue(all(m[k]["status"]=="unavailable" for k in ("structure","vwap","fvg","liquidity_sweep")))
        for now in (29*TF,33*TF):
            self.assertEqual(compute_price_action(b,timeframe_ms=TF,as_of_ms=now,max_age_ms=TF)["structure"]["status"],"unavailable")

    def test_fvg_displacement_and_full_mitigation(self):
        b=bars(); b[-2]=replace(b[-2],open=100,high=104,low=99,close=103)
        b[-1]=replace(b[-1],open=103,high=105,low=102,close=104)
        gap=methods(b)["fvg"]["active_gaps"][-1]
        self.assertEqual((gap["direction"],D(gap["low"]),D(gap["high"])),("bullish",D(101),D(102)))
        extra=replace(b[-1],open_time_ms=30*TF,close_time_ms=31*TF,open=103,high=104,low=101,close=102)
        self.assertEqual(methods(b+[extra])["fvg"]["active_gaps"],[])
        b[-2]=replace(b[-2],open=103) # no displacement
        self.assertEqual(methods(b)["fvg"]["active_gaps"],[])

    def test_sweep_requires_reclaim_and_marks_two_sided_conflict(self):
        b=bars(); b[-1]=replace(b[-1],open=100,low=97,high=101,close=100)
        m=methods(b)
        self.assertEqual(m["liquidity_sweep"]["direction"],"bullish")
        self.assertEqual(m["liquidity_sweep"]["bucket"],m["fvg"]["bucket"])
        b[-1]=replace(b[-1],high=103)
        self.assertEqual(methods(b)["liquidity_sweep"]["direction"],"conflict")
        b[-1]=replace(b[-1],high=101,close=98)
        self.assertEqual(methods(b)["liquidity_sweep"]["direction"],"neutral")

    def test_pivot_is_not_available_before_two_right_bars_and_bos_only_once(self):
        b=bars(); b[24]=replace(b[24],high=105)
        b[25]=replace(b[25],high=104)
        b[26]=replace(b[26],high=103)
        b[27]=replace(b[27],open=100,high=107,close=106)
        short=methods(b[:27]); event=methods(b[:28])["structure"]["events"][0]
        self.assertEqual(short["structure"]["events"],[])
        self.assertEqual(event["kind"],"BOS")
        self.assertEqual(event["confirmed_at_ms"],27*TF)
        self.assertEqual(event["event_time_ms"],28*TF)
        b[28]=replace(b[28],open=106,high=108,low=105,close=107)
        self.assertEqual(methods(b[:29])["structure"]["events"],[])
        # Adding future prices cannot mutate the saved prefix event.
        self.assertEqual(methods(b[:28])["structure"]["events"][0],event)

    def test_choch_uses_confirmed_prior_lower_high_and_lower_low(self):
        b=bars([100]*35)
        for i,hi in ((5,110),(15,108),(25,106)):
            b[i]=replace(b[i],high=hi)
        for i,lo in ((10,90),(20,92),(29,94)):
            b[i]=replace(b[i],low=lo)
        # Higher lows + lower highs are neutral, not a fabricated trend.
        self.assertEqual(methods(b)["structure"]["bias"],"neutral")
        b[20]=replace(b[20],low=88);b[29]=replace(b[29],low=86)
        b[-1]=replace(b[-1],open=100,high=109,close=108)
        event=methods(b)["structure"]["events"][0]
        self.assertEqual(event["kind"],"CHoCH")
        self.assertEqual(event["direction"],"bullish")

    def test_fvg_formation_threshold_does_not_repaint_when_later_atr_expands(self):
        b=bars();b[-2]=replace(b[-2],open=100,high=104,low=99,close=103)
        b[-1]=replace(b[-1],open=103,high=105,low=102,close=104)
        saved=methods(b)["fvg"]["active_gaps"][0]
        # A later volatility spike above the bullish gap cannot retroactively
        # erase its valid formation threshold when it never mitigated the gap.
        extra=replace(b[-1],open_time_ms=30*TF,close_time_ms=31*TF,open=104,high=1000,low=103,close=104)
        self.assertIn(saved,methods(b+[extra])["fvg"]["active_gaps"])
