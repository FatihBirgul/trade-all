"""Offline snapshot -> routing -> technical -> bound paper risk smoke."""
from dataclasses import FrozenInstanceError, replace
import json
from unittest import TestCase

from market_ai.v2.decision_record import AnalysisConfig, record_analysis, record_paper_risk, replay_analysis
from market_ai.v2.strategy_router import StrategySpec
from tests.test_v2_paper_risk import NOW, POLICY, portfolio, setup
from tests.test_v2_technical_adapter import candles, TF


CONFIG = AnalysisConfig("fixture-bars-v1", "fixture-config-v1", "1m", NOW, TF, "london", True)
SPEC = StrategySpec("trend", frozenset({"trend"}), frozenset({"crypto_spot"}), version="fixture-1")


def series(n=30):
    # Smooth path; wide candles avoid triggering the breakout classifier.
    return [replace(c, open=100 + i * .1, close=100 + i * .1,
                    high=105 + i * .1, low=95 + i * .1,
                    open_time_ms=NOW - (n - i) * TF,
                    close_time_ms=NOW - (n - i - 1) * TF) for i, c in enumerate(candles(n))]


def analysis(**changes):
    return record_analysis(series(), [SPEC], config=replace(CONFIG, **changes))


def risk(record, candidate=None, **overrides):
    s = candidate or setup(instrument=series()[0].instrument, created_at_ms=NOW,
                            analysis_record_id=record.record_id)
    args = dict(as_of_ms=NOW, session_allowed=True, news_clear=True, emergency_paused=False)
    args.update(overrides)
    return record_paper_risk(record, s, portfolio(), POLICY, **args)


class DecisionRecordTests(TestCase):
    def test_replay_uses_original_as_of_and_matches_identical_decision(self):
        for record in (analysis(), analysis(as_of_ms=NOW - 1)):
            with self.subTest(record_id=record.record_id):
                result = replay_analysis(record)
                self.assertEqual(result.status, "matched")
                self.assertEqual(result.original_record_id, result.replayed_record_id)

    def test_replay_refuses_corruption_foreign_version_and_invalid_number_tags(self):
        from hashlib import sha256
        from market_ai.v2.decision_record import ImmutableDecisionRecord
        record = analysis()
        body = record.payload()
        body["engine_versions"]["technical"] = "future-version"
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":"))
        foreign = ImmutableDecisionRecord(sha256(encoded.encode()).hexdigest(), encoded)
        self.assertEqual(replay_analysis(foreign).reason, "unsupported_kind_or_engine_version")
        self.assertEqual(replay_analysis(replace(record, record_id="corrupt")).status, "unavailable")
        bars = series()
        bars[-1] = replace(bars[-1], close=float("nan"))
        invalid = record_analysis(bars, [SPEC], config=CONFIG)
        self.assertEqual(replay_analysis(invalid).reason, "invalid_number_diagnostics_not_replayable")

    def test_record_contains_inputs_versions_and_deterministic_gates(self):
        record = analysis()
        self.assertTrue(record.verify())
        payload = record.payload()
        self.assertEqual(payload["status"], "analysis_ready")
        self.assertEqual(len(payload["candles"]), 30)
        self.assertEqual(payload["strategies"][0]["version"], "fixture-1")
        self.assertEqual(payload["config"]["data_version"], "fixture-bars-v1")
        self.assertEqual(payload["parameters"]["technical"]["ema_warmup"]["200"], 250)
        self.assertEqual(payload["routing"]["route"]["strategy_id"], "trend")
        self.assertIn("ema200", payload["technical"]["unavailable_indicators"])
        json.dumps(payload, allow_nan=False)

    def test_hash_repeatable_and_record_is_immutable(self):
        record = analysis()
        self.assertEqual(record, analysis())
        record.payload()["config"]["data_version"] = "tampered"
        self.assertTrue(record.verify())
        with self.assertRaises(FrozenInstanceError):
            record.body_json = "{}"
        self.assertFalse(replace(record, body_json=record.body_json + " ").verify())

    def test_parameter_data_and_strategy_versions_change_identity(self):
        record = analysis()
        self.assertNotEqual(record.record_id, analysis(configuration_version="v2").record_id)
        self.assertNotEqual(record.record_id, analysis(data_version="v2").record_id)
        revised = record_analysis(series(), [replace(SPEC, version="fixture-2")], config=CONFIG)
        self.assertNotEqual(record.record_id, revised.record_id)
        bars = series()
        bars[0] = replace(bars[0], close=bars[0].close + .01)
        self.assertNotEqual(record.record_id, record_analysis(bars, [SPEC], config=CONFIG).record_id)

    def test_registry_input_order_does_not_change_record(self):
        other = replace(SPEC, strategy_id="lower-priority", priority=-1)
        first = record_analysis(series(), [SPEC, other], config=CONFIG)
        second = record_analysis(series(), [other, SPEC], config=CONFIG)
        self.assertEqual(first, second)

    def test_future_bar_cannot_leak_into_replay_decision(self):
        record = analysis(as_of_ms=NOW - 1)
        self.assertEqual(record.payload()["status"], "wait")
        self.assertEqual(record.payload()["reason"], "data_quality_gate")
        self.assertIsNone(record.payload()["technical"])
        self.assertTrue(record.verify())

    def test_invalid_number_is_tagged_without_invalid_json(self):
        bars = series()
        bars[-1] = replace(bars[-1], close=float("nan"))
        record = record_analysis(bars, [SPEC], config=CONFIG)
        self.assertEqual(record.payload()["status"], "wait")
        self.assertEqual(record.payload()["candles"][-1]["close"], {"invalid": "nonfinite_number"})
        self.assertNotIn("NaN", record.body_json)
        self.assertTrue(record.verify())

    def test_regime_warmup_does_not_bypass_technical_warmup(self):
        record = record_analysis(series(20), [SPEC], config=CONFIG)
        self.assertEqual(record.payload()["routing"]["route"]["status"], "selected")
        self.assertEqual(record.payload()["status"], "wait")
        self.assertEqual(record.payload()["reason"], "technical_data_quality_gate")
        self.assertEqual(risk(record).payload()["decision"]["reason"], "analysis_not_ready")

    def test_full_analysis_to_paper_risk_is_bound_and_repeatable(self):
        record = analysis()
        result = risk(record)
        self.assertEqual(result.payload()["decision"]["status"], "eligible_for_paper")
        self.assertEqual(result.payload()["analysis_record_id"], record.record_id)
        self.assertEqual(result, risk(record))
        self.assertTrue(result.verify())

    def test_wrong_instrument_timestamp_or_record_reference_is_rejected(self):
        record = analysis()
        candidate = setup(instrument=series()[0].instrument, created_at_ms=NOW, analysis_record_id=record.record_id)
        for changes in ({"instrument": replace(candidate.instrument, symbol="ETHUSDT")},
                        {"created_at_ms": NOW - 1}, {"analysis_record_id": "other"}):
            with self.subTest(changes=changes):
                self.assertEqual(risk(record, replace(candidate, **changes)).payload()["decision"]["reason"],
                                 "analysis_setup_mismatch")

    def test_corruption_and_risk_veto_are_recorded(self):
        record = analysis()
        corrupted = replace(record, record_id="0" * 64)
        self.assertEqual(risk(corrupted).payload()["decision"]["reason"], "invalid_analysis_record")
        self.assertEqual(risk(record, news_clear=False).payload()["decision"]["reason"], "session_or_news_gate")

    def test_strategies_require_immutable_constraints_and_explicit_versions(self):
        for changes in ({"regimes": {"trend"}}, {"version": ""}, {"enabled": "yes"},
                        {"priority": True}, {"markets": frozenset({"unknown"})}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(SPEC, **changes)

    def test_missing_data_and_config_versions_are_configuration_errors(self):
        for changes in ({"data_version": ""}, {"configuration_version": ""}, {"timeframe": "bad"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(CONFIG, **changes)
