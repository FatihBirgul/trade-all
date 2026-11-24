"""Versioned strategy positives, strict WAITs, conflicts, and real API risk veto."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from fastapi.testclient import TestClient
from market_ai.v2.api import create_app
from market_ai.v2.spot_provider import FixtureSpotProvider
from market_ai.v2.pipeline import evaluate_strategies
from market_ai.v2.strategies import STRATEGIES, TREND, RANGE, BREAKOUT, SWEEP, resolve_setups
from market_ai.v2.decision_record import record_analysis, replay_analysis, AnalysisConfig

NOW=1800000000000
TF=3600000


from scripts.v2_scenario_fixtures import fixture


def evaluate(b, **kw):
    return evaluate_strategies(b,STRATEGIES,timeframe_ms=TF,as_of_ms=NOW,max_age_ms=TF,session="off_hours",risk_gate_ok=kw.get("risk",True))


class SetupTests(TestCase):
    def test_four_strategies_confirm_and_select_with_versioned_rules(self):
        for kind, expected in (("trend",TREND),("range",RANGE),("breakout",BREAKOUT),("sweep",SWEEP)):
            with self.subTest(kind=kind):
                r=evaluate(fixture(kind));self.assertEqual(r.route.strategy_id,expected,r.strategy_analysis)
                a=r.strategy_analysis["assessments"][expected]
                self.assertEqual(a["status"],"confirmed")
                self.assertTrue(a["version"])
                if expected!=TREND:
                    self.assertEqual(len({e["bucket"] for e in a["evidence"]}),3)
                    z={k:float(v) for k,v in a["levels"].items()}
                    self.assertLess(z["invalidation"],z["entry_low"])
                    self.assertGreaterEqual((z["target_1"]-z["entry_high"])/(z["entry_high"]-z["invalidation"]),1.5)

    def test_bearish_symmetry_at_analysis_layer_not_permission_to_short_spot(self):
        for kind, expected in (("range",RANGE),("breakout",BREAKOUT),("sweep",SWEEP)):
            with self.subTest(kind=kind):
                r=evaluate(fixture(kind,mirror=True))
                self.assertEqual(r.route.strategy_id,expected)
                a=r.strategy_analysis["assessments"][expected]
                self.assertEqual(a["direction"],"bearish")
                z={k:float(v) for k,v in a["levels"].items()}
                self.assertTrue(0<z["target_2"]<z["target_1"]<z["entry_low"]<=z["entry_high"]<z["invalidation"])

    def test_volume_missing_confirmation_warmup_and_risk_fail_closed(self):
        for kind in ("range","breakout","sweep"):
            b=fixture(kind)
            r=evaluate(b[:-1]+[replace(b[-1],volume=100)])
            # A secondary continuation can be eligible only in trend, never an
            # unconfirmed breakout/range/sweep masquerading as confirmation.
            for key in (RANGE,BREAKOUT,SWEEP):
                self.assertNotEqual(r.strategy_analysis["assessments"][key]["status"],"confirmed")
            self.assertEqual(evaluate(b,risk=False).route.reason,"risk_gate")
            self.assertEqual(evaluate(b[-100:]).route.status,"wait")
            for volume_kind, volume in (("tick",100),("unavailable",None)):
                self.assertEqual(evaluate([replace(x,volume_kind=volume_kind,volume=volume) for x in b]).route.status,"wait")

    def test_unfinished_bar_invalidates_every_strategy_and_no_future_repair(self):
        b=fixture("range")
        r=evaluate(b[:-1]+[replace(b[-1],is_final=False)])
        self.assertEqual(r.route.reason,"data_quality_gate")
        self.assertIsNone(r.strategy_analysis)
        prefix=evaluate(b)
        future=replace(b[-1],open_time_ms=b[-1].close_time_ms,close_time_ms=b[-1].close_time_ms+TF)
        self.assertEqual(evaluate(b+[future]).route.reason,"data_quality_gate")
        self.assertEqual(evaluate(b),prefix)

    def test_opposite_direction_veto_overrides_unequal_priority(self):
        r=evaluate(fixture("range")); setup=r.strategy_analysis
        setup["assessments"][SWEEP].update(status="confirmed",direction="bearish")
        route=resolve_setups(STRATEGIES,setup,regime="range",market="crypto_spot",session="off_hours",
                             capabilities=frozenset({"ohlc","real_volume"}),data_quality_ok=True,risk_gate_ok=True)
        self.assertEqual(route.reason,"opposing_strategy_conflict")
        self.assertIsNone(route.strategy_id)

    def test_new_strategy_record_replays_at_original_time(self):
        b=fixture("range")
        r=record_analysis(b,STRATEGIES,config=AnalysisConfig("fixture-1","setup-test-1","1H",NOW,TF,"off_hours",True))
        self.assertEqual(replay_analysis(r).status,"matched")
        self.assertIn("price-action",r.payload()["routing"]["strategy_analysis"]["methods"]["version"])

    def test_api_range_strategy_passes_unchanged_paper_risk_and_exposes_methods(self):
        class RangeProvider(FixtureSpotProvider):
            def candles(self,symbol,timeframe,as_of_ms): return fixture("range",timeframe,as_of_ms,symbol)
        with TemporaryDirectory(prefix="v2-setup-api-") as root:
            app=create_app(Path(root)/"isolated.sqlite",mode="fixture",token="setup-test-token-not-a-secret-32",provider=RangeProvider(),clock=lambda:NOW)
            with TestClient(app,headers={"Authorization":"Bearer setup-test-token-not-a-secret-32"}) as client:
                r=client.post("/api/v2/analyze",json={"data_mode":"fixture","idempotency_key":"new-range-setup-test"})
                self.assertEqual(r.status_code,200,r.text); a=r.json()
                self.assertEqual(a["router"]["strategy_id"],RANGE)
                self.assertEqual(a["direction"],"bullish",a)
                self.assertEqual(a["risk"]["status"],"eligible_for_paper")
                self.assertEqual(a["technical_methods"]["vwap"]["status"],"available")
                self.assertEqual(len(a["supporting_evidence"]),3)
                order=client.post("/api/v2/portfolios/MANUAL/orders",json={"analysis_id":a["analysis_id"],"idempotency_key":"range-order-test-key"})
                self.assertEqual(order.status_code,200,order.text)

    def test_api_mtf_opposition_blocks_range_setup_with_explicit_reason(self):
        class MixedProvider(FixtureSpotProvider):
            def candles(self,symbol,timeframe,as_of_ms):
                if timeframe=="1H":return fixture("range",timeframe,as_of_ms,symbol)
                # A strong closed downtrend on the higher TF is independent
                # evidence and vetoes the current range long.
                b=super().candles(symbol,timeframe,as_of_ms)
                return [replace(x,open=300-x.open,close=300-x.close,high=300-x.low,low=300-x.high) for x in b]
        with TemporaryDirectory(prefix="v2-mtf-setup-") as root:
            app=create_app(Path(root)/"isolated.sqlite",mode="fixture",token="setup-test-token-not-a-secret-32",provider=MixedProvider(),clock=lambda:NOW)
            with TestClient(app,headers={"Authorization":"Bearer setup-test-token-not-a-secret-32"}) as client:
                a=client.post("/api/v2/analyze",json={"data_mode":"fixture","timeframes":["4H"],"idempotency_key":"mtf-veto-range-test"}).json()
                self.assertEqual(a["router"]["strategy_id"],RANGE)
                self.assertEqual(a["direction"],"WAIT",a)
                self.assertEqual(a["reason"],"mtf_strategy_conflict")
                self.assertIsNone(a["levels"])

    def test_single_breakout_close_is_not_confirmed_and_bearish_spot_stays_wait(self):
        b=fixture("breakout");b[-2]=replace(b[-2],open=100,high=101,low=99,close=100)
        self.assertEqual(evaluate(b).strategy_analysis["assessments"][BREAKOUT]["status"],"wait")
        class BearProvider(FixtureSpotProvider):
            def candles(self,symbol,timeframe,as_of_ms):return fixture("range",timeframe,as_of_ms,symbol,mirror=True)
        with TemporaryDirectory(prefix="v2-bearish-setup-") as root:
            app=create_app(Path(root)/"isolated.sqlite",mode="fixture",token="setup-test-token-not-a-secret-32",provider=BearProvider(),clock=lambda:NOW)
            with TestClient(app,headers={"Authorization":"Bearer setup-test-token-not-a-secret-32"}) as client:
                a=client.post("/api/v2/analyze",json={"data_mode":"fixture","auto_paper":True,"idempotency_key":"bearish-no-spot-short"}).json()
                self.assertEqual(a["direction"],"WAIT",a)
                self.assertIsNone(a["levels"])
                self.assertEqual(client.get("/api/v2/portfolios/AUTO/orders").json(),[])

    def test_wilder_rsi_has_independent_hand_calculated_reference(self):
        b=fixture("trend")
        b=[replace(x,open=100,high=101,low=99,close=100,volume=100) for x in b]
        for i,value in ((-3,101),(-2,100),(-1,102)):
            b[i]=replace(b[i],open=value,high=value+1,low=value-1,close=value)
        momentum=evaluate(b).strategy_analysis["momentum"]
        # After a flat warm-up and +1,-1,+2, the smoothed gains/losses
        # are 561/2744 and 182/2744; RSI=100*561/(561+182).
        self.assertAlmostEqual(float(momentum["rsi14_wilder"]),100*561/743,places=12)
        self.assertAlmostEqual(float(momentum["previous_rsi14"]),100*13/27,places=12)

    def test_tick_rounding_cannot_reduce_new_strategy_gross_rr_threshold(self):
        class CoarseProvider(FixtureSpotProvider):
            def candles(self,symbol,timeframe,as_of_ms):return fixture("range",timeframe,as_of_ms,symbol)
            def rules(self,symbol):return {**super().rules(symbol),"price_tick":"1"}
        with TemporaryDirectory(prefix="v2-rounded-risk-") as root:
            app=create_app(Path(root)/"isolated.sqlite",mode="fixture",token="setup-test-token-not-a-secret-32",provider=CoarseProvider(),clock=lambda:NOW)
            with TestClient(app,headers={"Authorization":"Bearer setup-test-token-not-a-secret-32"}) as client:
                a=client.post("/api/v2/analyze",json={"data_mode":"fixture","idempotency_key":"coarse-rounded-range"}).json()
                self.assertEqual(a["direction"],"WAIT",a)
                self.assertEqual(a["reason"],"strategy_reward_risk_gate")
                self.assertIsNone(a["levels"])

    def test_missing_older_volume_cannot_crash_or_inherit_recent_real_volume(self):
        b=fixture("range");b[0]=replace(b[0],volume_kind="unavailable",volume=None)
        r=evaluate(b)
        self.assertEqual(r.route.status,"wait")
        self.assertTrue(all(a["status"]=="wait" for a in r.strategy_analysis["assessments"].values()))
        self.assertNotIn("real_volume",r.capabilities)
