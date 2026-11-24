"""Acceptance: ASGI -> existing V2 engines -> isolated SQLite -> paper ledger.

TestClient is in-process, providers are explicit fixtures/test doubles; the
outer runner blocks real sockets and non-temporary SQLite connections.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from decimal import Decimal as D
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import sqlite3
import json
import os
import subprocess
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient
from market_ai.v2.api import create_app, create_runtime, install_v2
from market_ai.v2.api_models import AnalysisResponse
from market_ai.v2.spot_provider import FixtureSpotProvider, ProviderUnavailable


TOKEN = "fixture-test-token-not-a-secret-32"
NOW = 1800000000000


class ProductAPITests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="v2-product-test-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)/"isolated.sqlite"
        self.now = NOW
        self.counter = 0
        self.app = create_app(self.path, mode="fixture", token=TOKEN, clock=lambda: self.now)
        self.client = TestClient(self.app, headers={"Authorization": "Bearer "+TOKEN})
        self.addCleanup(self.client.close)

    def analyze(self, **overrides):
        self.counter += 1
        args = {"data_mode": "fixture", "timeframe": "1H", "timeframes": ["15m", "4H"],
                "idempotency_key": "analysis-request-"+str(self.counter)}
        args.update(overrides)
        r = self.client.post("/api/v2/analyze", json=args)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def order(self, analysis, account="MANUAL", quantity=None, key="order-request-first"):
        args = {"analysis_id": analysis["analysis_id"], "idempotency_key": key}
        if quantity is not None:
            args["quantity"] = quantity
        r = self.client.post(f"/api/v2/portfolios/{account}/orders", json=args)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def event(self, **changes):
        start = self.now
        self.now += 60000
        event = {"symbol": "BTCUSDT", "open_time_ms": start, "close_time_ms": self.now,
                 "open": "129.9", "high": "130.2", "low": "129.5", "close": "130", "volume": "10000"}
        event.update(changes)
        r = self.client.post("/api/v2/paper/events", json=event)
        self.assertEqual(r.status_code, 200, r.text)
        return event, r.json()

    def account(self, name="MANUAL"):
        r = self.client.get("/api/v2/portfolios/"+name)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def positions(self, account="MANUAL", all=False):
        return self.client.get(f"/api/v2/portfolios/{account}/positions", params={"open_only": not all}).json()

    def close(self, p, quantity=None, key="close-request-first"):
        r = self.client.post(f"/api/v2/portfolios/{p['portfolio_id']}/positions/{p['position_id']}/close", json={
            "quantity": quantity or p["quantity"], "idempotency_key": key})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_exact_acceptance_flow_restart_and_cash_reconciliation(self):
        a = self.analyze()
        self.assertTrue(a["quality"]["ok"])
        self.assertEqual(a["router"]["status"], "selected")
        self.assertEqual(a["data_mode"], "fixture")
        self.assertEqual(a["direction"], "bullish")
        self.assertEqual(self.client.get("/api/v2/analyses/"+a["analysis_id"]).json(), a)
        order = self.order(a)
        again = self.order(a)
        self.assertEqual(order, again)
        self.assertEqual(len(self.client.get("/api/v2/portfolios/MANUAL/orders").json()), 1)
        e, receipt = self.event()
        before = self.account()
        self.assertEqual(self.client.post("/api/v2/paper/events", json=e).json(), receipt)
        self.assertEqual(self.account(), before)
        p = self.positions()[0]
        self.assertEqual(p["status"], "open")
        command = self.close(p)
        self.assertEqual(command["status"], "pending")
        # No past-price exit at request time.
        self.assertEqual(self.account(), before)
        self.client.close()
        restarted = create_app(self.path, mode="fixture", token=TOKEN, clock=lambda: self.now)
        self.client = TestClient(restarted, headers={"Authorization": "Bearer "+TOKEN})
        self.addCleanup(self.client.close)
        self.assertEqual(self.positions()[0]["pending_closes"][0]["status"], "pending")
        self.event(open="130.5", high="130.8", low="130.3", close="130.6")
        self.assertEqual(self.positions(), [])
        account = self.account()
        tx = self.client.get("/api/v2/portfolios/MANUAL/transactions").json()
        self.assertEqual(len(tx), 2)
        cash_delta = sum(D(t["cash_delta_quote"]) for t in tx)
        pnl = sum(D(t["realized_pnl_quote"]) for t in tx)
        self.assertEqual(D(account["cash_quote"]), D("10000")+cash_delta)
        self.assertEqual(D(account["cash_quote"]), D("10000")+pnl)
        self.assertEqual(D(self.account("AUTO")["cash_quote"]), D("10000"))
        perf = self.client.get("/api/v2/performance").json()
        self.assertEqual(perf["data_mode"], "fixture")
        self.assertEqual(perf["portfolios"][1]["closed_positions"], 1)
        self.assertEqual(D(perf["portfolios"][1]["realized_pnl_quote"]), pnl)

    def test_openapi_has_required_paths_security_and_no_real_order_gateway(self):
        schema = self.client.get("/openapi.json").json()
        for path in ("health", "markets", "analyze", "analyses", "analyses/{analysis_id}", "portfolios",
                     "portfolios/{portfolio_id}", "portfolios/{portfolio_id}/positions",
                     "portfolios/{portfolio_id}/transactions", "performance"):
            self.assertIn("/api/v2/"+path, schema["paths"])
        self.assertIn("V2Bearer", schema["components"]["securitySchemes"])
        self.assertFalse(self.client.get("/api/v2/health").json()["real_execution"])
        json.dumps(schema, allow_nan=False)

    def test_auth_invalid_requests_and_unavailable_markets(self):
        self.assertEqual(self.client.get("/api/v2/portfolios", headers={"Authorization": "Bearer invalid"}).status_code, 401)
        self.assertEqual(self.client.post("/api/v2/analyze", json={"idempotency_key": "short"}).status_code, 422)
        self.assertEqual(self.client.get("/api/v2/analyses?limit=1000").status_code, 422)
        self.assertEqual(self.client.get("/api/v2/analyses/missing").status_code, 404)
        markets = self.client.get("/api/v2/markets").json()["items"]
        self.assertEqual([m["availability"] for m in markets if m["market"] != "crypto_spot"], ["unavailable", "unavailable"])
        r = self.client.post("/api/v2/analyze", json={"idempotency_key": "market-unavailable", "data_mode": "fixture", "market": "gold_spot"})
        self.assertEqual(r.status_code, 503)

    def test_analysis_idempotency_conflict_and_same_snapshot_different_key(self):
        first = self.analyze(idempotency_key="same-analysis-key")
        second = self.analyze(idempotency_key="same-analysis-key")
        self.assertEqual(first, second)
        third = self.analyze(idempotency_key="another-analysis-key")
        self.assertEqual(first, third)
        self.assertEqual(len(self.client.get("/api/v2/analyses").json()), 1)
        r = self.client.post("/api/v2/analyze", json={"data_mode": "fixture", "fixture_case": "range", "idempotency_key": "same-analysis-key"})
        self.assertEqual(r.status_code, 409)

    def test_auto_opens_only_after_all_gates_and_wait_never_opens(self):
        a = self.analyze(auto_paper=True)
        self.assertIsNotNone(a["auto_order_id"])
        for case in ("range", "stale", "unfinished", "mixed", "gap"):
            wait = self.analyze(fixture_case=case, auto_paper=True)
            self.assertEqual(wait["direction"], "WAIT")
            self.assertIsNone(wait["levels"])
            self.assertIsNone(wait["auto_order_id"])
            self.assertNotIn("None", json.dumps(wait["scenarios"]))
        self.assertEqual(len(self.client.get("/api/v2/portfolios/AUTO/orders").json()), 1)

    def test_mtf_identity_alignment_and_no_current_evidence_double_count(self):
        a = self.analyze()
        evidence = a["supporting_evidence"]+a["conflicting_evidence"]
        self.assertEqual(len(evidence), len({e["bucket"] for e in evidence}))
        self.assertNotIn("mtf_current", [e["source"] for e in evidence])
        self.assertTrue(all(q["last_close_ms"] <= NOW for q in a["quality"]["timeframes"].values()))
        original = self.app.state.v2.analysis.provider.candles
        def misaligned(symbol, tf, as_of):
            bars = original(symbol, tf, as_of)
            if tf == "4H":
                bars = [replace(b, open_time_ms=b.open_time_ms+1, close_time_ms=b.close_time_ms+1) for b in bars]
            return bars
        with patch.object(self.app.state.v2.analysis.provider, "candles", side_effect=misaligned):
            a = self.analyze(idempotency_key="alignment-check-key")
        self.assertEqual(a["direction"], "WAIT")
        self.assertFalse(a["quality"]["ok"])

    def test_partial_fills_partial_closes_and_pending_reservations(self):
        a = self.analyze()
        o = self.order(a, quantity="10")
        self.event(volume="200")  # model 1% participation -> 2 units
        p = self.positions()[0]
        self.assertEqual(D(p["quantity"]), D("2"))
        self.assertEqual(self.client.get("/api/v2/portfolios/MANUAL/orders").json()[0]["status"], "partially_filled")
        self.event(volume="300")
        p = self.positions()[0]
        self.assertEqual(D(p["quantity"]), D("5"))
        before = self.account()
        self.close(p, quantity="1", key="partial-close-key")
        self.assertLess(D(self.account()["reserved_cash_quote"]), D(before["reserved_cash_quote"]))
        self.event(open="130", high="130.5", low="129.9", close="130.2", volume="10000")
        p = self.positions()[0]
        self.assertEqual(D(p["quantity"]), D("4"))
        self.assertGreater(D(self.account()["cash_quote"]), D(before["cash_quote"]))

    def test_cancel_releases_cash_and_account_isolation(self):
        a = self.analyze()
        o = self.order(a)
        self.assertGreater(D(self.account()["reserved_cash_quote"]), 0)
        self.assertEqual(D(self.account("AUTO")["reserved_cash_quote"]), 0)
        r = self.client.post(f"/api/v2/portfolios/MANUAL/orders/{o['order_id']}/cancel", json={"idempotency_key": "cancel-request-key"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(D(self.account()["reserved_cash_quote"]), 0)
        wrong = self.client.post(f"/api/v2/portfolios/AUTO/orders/{o['order_id']}/cancel", json={"idempotency_key": "other-cancel-key"})
        self.assertEqual(wrong.status_code, 404)

    def test_simultaneous_stop_target_is_ambiguous_not_win(self):
        a = self.analyze()
        self.order(a)
        self.event()
        self.event(low="128", high="134", open="130", close="131")
        p = self.positions()[0]
        self.assertEqual(p["status"], "ambiguous")
        self.assertTrue(self.account()["paused"])
        perf = self.client.get("/api/v2/performance").json()["portfolios"][1]
        self.assertEqual(perf["wins"], 0)
        self.assertEqual(perf["ambiguous_positions"], 1)
        self.assertEqual(len(self.client.get("/api/v2/portfolios/MANUAL/transactions").json()), 1)

    def test_take_profit_partial_then_full_and_costs_are_applied(self):
        a = self.analyze()
        self.order(a, quantity="10")
        self.event()
        self.event(open="130", high="132", low="129.8", close="131.8")
        self.assertEqual(D(self.positions()[0]["quantity"]), D("5"))
        self.event(open="132", high="134", low="131.8", close="133.8")
        self.assertEqual(self.positions(), [])
        tx = self.client.get("/api/v2/portfolios/MANUAL/transactions").json()
        self.assertEqual({t["kind"] for t in tx}, {"entry", "take_profit_1", "take_profit_2"})
        self.assertTrue(all(D(t["fee_quote"]) > 0 for t in tx))
        self.assertGreater(D(self.account()["cash_quote"]), D("10000"))

    def test_stop_gap_never_gets_a_favorable_stop_price(self):
        a = self.analyze()
        self.order(a, quantity="1")
        self.event()
        self.event(open="127", high="128", low="126", close="127")
        tx = self.client.get("/api/v2/portfolios/MANUAL/transactions").json()
        stop = next(t for t in tx if t["kind"] == "stop_loss")
        self.assertLess(D(stop["price"]), D("127"))
        self.assertEqual(self.positions(), [])

    def test_future_unfinished_conflicting_and_gap_events_are_rejected(self):
        a = self.analyze()
        self.order(a)
        e, _ = self.event()
        bad = {**e, "close": "130.1"}
        self.assertEqual(self.client.post("/api/v2/paper/events", json=bad).status_code, 409)
        future = {**e, "open_time_ms": self.now, "close_time_ms": self.now+60000}
        self.assertEqual(self.client.post("/api/v2/paper/events", json=future).status_code, 422)
        self.assertEqual(self.client.post("/api/v2/paper/events", json={**e, "is_final": False}).status_code, 422)
        self.now += 180000
        gap = {**e, "open_time_ms": self.now-60000, "close_time_ms": self.now}
        self.assertEqual(self.client.post("/api/v2/paper/events", json=gap).status_code, 409)

    def test_quantity_risk_stale_and_pause_veto(self):
        a = self.analyze()
        for quantity in ("100000", "0.00000001", "NaN", "Infinity", "-1"):
            r = self.client.post("/api/v2/portfolios/MANUAL/orders", json={"analysis_id": a["analysis_id"],
                "idempotency_key": "bad-quantity-key", "quantity": quantity})
            self.assertIn(r.status_code, (409, 422))
        self.client.post("/api/v2/portfolios/MANUAL/pause", json={"paused": True})
        r = self.client.post("/api/v2/portfolios/MANUAL/orders", json={"analysis_id": a["analysis_id"], "idempotency_key": "paused-order-key"})
        self.assertEqual(r.status_code, 409)
        self.now += 4*3600000
        r = self.client.post("/api/v2/portfolios/AUTO/orders", json={"analysis_id": a["analysis_id"], "idempotency_key": "stale-order-key"})
        self.assertEqual(r.status_code, 409)

    def test_concurrent_same_order_key_only_reserves_once(self):
        a = self.analyze()
        body = {"analysis_id": a["analysis_id"], "idempotency_key": "concurrent-order-key", "quantity": "1"}
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.client.post, "/api/v2/portfolios/MANUAL/orders", json=body) for _ in range(2)]
            responses = [f.result() for f in futures]
        self.assertEqual([r.status_code for r in responses], [200, 200])
        self.assertEqual(responses[0].json(), responses[1].json())
        self.assertEqual(len(self.client.get("/api/v2/portfolios/MANUAL/orders").json()), 1)

    def test_mount_does_not_change_v1_routes_or_validation(self):
        old = FastAPI()
        @old.get("/api/v1-sentinel")
        def sentinel(number: int):
            return {"number": number}
        install_v2(old, self.app.state.v2)
        with TestClient(old, headers={"Authorization": "Bearer "+TOKEN}) as client:
            self.assertEqual(client.get("/api/v1-sentinel?number=3").json(), {"number": 3})
            self.assertIn("detail", client.get("/api/v1-sentinel?number=bad").json())
            self.assertEqual(client.get("/api/v2/health").status_code, 200)

    def test_database_mode_is_persistent_and_foreign_db_is_not_migrated(self):
        with self.assertRaises(ValueError):
            create_app(self.path, mode="live", token=TOKEN)
        foreign = Path(self.directory.name)/"foreign.sqlite"
        foreign.write_bytes(b"preserve-this-user-fixture")
        with self.assertRaises(sqlite3.DatabaseError):
            create_app(foreign, mode="fixture", token=TOKEN)
        self.assertEqual(foreign.read_bytes(), b"preserve-this-user-fixture")

    def test_failed_journal_rolls_back_cash_position_fill_and_event_receipt(self):
        a = self.analyze()
        self.order(a, quantity="1")
        before = self.account()
        event = {"symbol": "BTCUSDT", "open_time_ms": self.now, "close_time_ms": self.now+60000,
                 "open": "129.9", "high": "130.2", "low": "129.5", "close": "130", "volume": "10000"}
        self.now += 60000
        with patch.object(self.app.state.v2.ledger, "_journal", side_effect=sqlite3.OperationalError("intentional fixture failure")):
            with self.assertLogs("market_ai.v2.api", level="ERROR"):
                r = self.client.post("/api/v2/paper/events", json=event)
        self.assertEqual(r.status_code, 503)
        self.assertEqual(r.json()["error"]["code"], "STORAGE_UNAVAILABLE")
        self.assertEqual(self.account(), before)
        self.assertEqual(self.positions(), [])
        self.assertEqual(self.client.get("/api/v2/portfolios/MANUAL/transactions").json(), [])
        r = self.client.post("/api/v2/paper/events", json=event)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(D(self.positions()[0]["quantity"]), D("1"))

    def test_live_provider_failure_is_saved_wait_not_fixture_fallback(self):
        class Down:
            name, venue, mode = "binance_public_spot", "binance", "live"
            def rules(self, symbol):
                raise ProviderUnavailable("fixture-injected outage")
        app = create_app(Path(self.directory.name)/"live-isolated.sqlite", mode="live", token=TOKEN, provider=Down(), clock=lambda: self.now)
        with TestClient(app, headers={"Authorization": "Bearer "+TOKEN}) as client:
            r = client.post("/api/v2/analyze", json={"idempotency_key": "unavailable-live-key"})
            self.assertEqual(r.status_code, 200)
            a = r.json()
            self.assertEqual(a["data_mode"], "live")
            self.assertEqual(a["provider"], "binance_public_spot")
            self.assertEqual(a["direction"], "WAIT")
            self.assertIsNone(a["price"])
            self.assertIsNone(a["levels"])
            self.assertIn("provider_unavailable", a["quality"]["issues"])
            self.assertEqual(client.get("/api/v2/analyses/"+a["analysis_id"]).json(), a)
            self.assertEqual(client.post("/api/v2/paper/events", json={"symbol":"BTCUSDT", "open_time_ms":NOW, "close_time_ms":NOW+60000,
                "open":"1", "high":"2", "low":"1", "close":"1", "volume":"1"}).status_code, 403)

    def test_entry_bar_exit_order_is_ambiguous_and_no_second_fill_when_paused(self):
        a = self.analyze()
        self.order(a, quantity="10")
        self.event(high="134", low="129", volume="100")
        self.assertEqual(self.positions()[0]["status"], "ambiguous")
        self.assertEqual(D(self.positions()[0]["quantity"]), D("1"))
        self.event()
        self.assertEqual(D(self.positions()[0]["quantity"]), D("1"))

    def test_initial_missing_event_cannot_create_a_historical_advantage(self):
        a = self.analyze()
        self.order(a, quantity="1")
        self.now += 180000
        event = {"symbol": "BTCUSDT", "open_time_ms": self.now-60000, "close_time_ms": self.now,
                 "open": "129.9", "high": "130.2", "low": "129.5", "close": "130", "volume": "10000"}
        self.assertEqual(self.client.post("/api/v2/paper/events", json=event).status_code, 409)
        self.assertEqual(self.positions(), [])

    def test_auto_account_pause_does_not_block_manual_risk_analysis(self):
        self.client.post("/api/v2/portfolios/AUTO/pause", json={"paused": True})
        auto = self.analyze()
        manual = self.analyze(risk_portfolio="MANUAL")
        self.assertEqual(auto["direction"], "WAIT")
        self.assertEqual(manual["direction"], "bullish")
        self.order(manual, quantity="1")

    def test_repeated_auto_signal_with_new_request_key_is_not_a_second_order(self):
        self.analyze(auto_paper=True)
        self.analyze(auto_paper=True)
        orders = self.client.get("/api/v2/portfolios/AUTO/orders").json()
        self.assertEqual(len(orders), 1)

    def test_committed_openapi_and_fixture_contract_match_runtime_schema(self):
        docs = Path(__file__).resolve().parents[2]/"docs"
        expected=json.loads((docs/"V2_OPENAPI.json").read_text(encoding="utf-8"))
        actual=self.app.openapi()
        differences=[]
        def diff(left,right,path="$"):
            if type(left) is not type(right):
                differences.append((path,left,right))
            elif isinstance(left,dict):
                for key in sorted(set(left)|set(right)):
                    if key not in left or key not in right:
                        differences.append((path+"/"+key,left.get(key),right.get(key)))
                    else: diff(left[key],right[key],path+"/"+key)
            elif isinstance(left,list):
                if len(left)!=len(right): differences.append((path,left,right))
                else:
                    for i,(a,b) in enumerate(zip(left,right)): diff(a,b,path+"/"+str(i))
            elif left!=right: differences.append((path,left,right))
        diff(expected,actual)
        self.assertFalse(differences,json.dumps(differences[:12],ensure_ascii=True))
        for name in ("analysis", "wait", "provider_unavailable", "range_setup", "breakout_setup", "sweep_setup"):
            value=json.loads((docs/"v2_examples"/(name+".json")).read_text(encoding="utf-8"))
            AnalysisResponse.model_validate(value)
        from market_ai.v2.api_models import ChartResponse
        ChartResponse.model_validate(json.loads((docs/"v2_examples/candles.json").read_text(encoding="utf-8")))
        from market_ai.v2.scanner_models import WatchRequest,WatchResponse,ScannerState,ScannerJob,TickResponse,NotificationResponse
        for name,model,many in (("watch_request",WatchRequest,False),("watchlist",WatchResponse,True),
                                ("scanner",ScannerState,False),("scanner_jobs",ScannerJob,True),
                                ("scanner_tick",TickResponse,False),("notifications",NotificationResponse,True)):
            value=json.loads((docs/"v2_examples"/(name+".json")).read_text(encoding="utf-8"))
            for item in value if many else [value]: model.model_validate(item)

    def test_openapi_and_errors_never_need_exchange_or_ai_secrets(self):
        r=self.client.post("/api/v2/analyze",json={"idempotency_key":"reject-private-key","exchange_api_key":"fixture-must-not-echo"})
        self.assertEqual(r.status_code,422)
        self.assertNotIn("fixture-must-not-echo",r.text)
        self.assertEqual(self.client.get("/api/v2/missing-route").json()["error"]["code"],"NOT_FOUND")
        r=self.client.post("/api/v2/analyze",json={"symbol":"XAUUSD","market":"gold_spot","data_mode":"fixture","idempotency_key":"gold-unavailable-key"})
        self.assertEqual(r.status_code,503)

    def test_process_crash_before_commit_does_not_change_paper_cash(self):
        before=self.account()
        code = "import sqlite3,sys,os; from pathlib import Path; p=Path(sys.argv[1]).resolve(); assert p.is_relative_to(Path(sys.argv[2]).resolve()); c=sqlite3.connect(p); c.execute('BEGIN IMMEDIATE'); c.execute(\"UPDATE accounts SET body='{}' WHERE id='MANUAL'\"); os._exit(7)"
        result=subprocess.run([sys.executable,"-c",code,str(self.path),self.directory.name],timeout=10,
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
        self.assertEqual(result.returncode,7)
        self.assertEqual(self.account(),before)

    def test_cross_timeframe_provider_source_cannot_be_silently_mixed(self):
        original=self.app.state.v2.analysis.provider.candles
        def mixed_source(symbol,tf,as_of):
            bars=original(symbol,tf,as_of)
            return [replace(b,source="other-feed") for b in bars] if tf=="4H" else bars
        with patch.object(self.app.state.v2.analysis.provider,"candles",side_effect=mixed_source):
            a=self.analyze()
        self.assertEqual(a["direction"],"WAIT")
        self.assertIn("4H:provider_source_mismatch",a["quality"]["issues"])
        self.assertEqual(self.client.get(f"/api/v2/analyses/{a['analysis_id']}/candles?timeframe=4H").status_code,409)

    def test_corrupted_projection_is_not_silently_reseeded_or_repaired(self):
        with closing(sqlite3.connect(self.path)) as c, c:
            c.execute("UPDATE accounts SET body='{}' WHERE id='MANUAL'")
        r=self.client.get("/api/v2/portfolios/MANUAL")
        self.assertEqual(r.status_code,503)
        self.assertEqual(r.json()["error"]["code"],"STORAGE_CORRUPT")
        self.assertEqual(self.client.get("/api/v2/health").status_code,503)

    def test_gap_open_below_stop_has_known_order_even_if_later_target_touched(self):
        self.order(self.analyze(),quantity="1")
        self.event()
        self.event(open="127",low="126",high="134",close="130")
        self.assertEqual(self.positions(),[])
        tx=self.client.get("/api/v2/portfolios/MANUAL/transactions").json()
        stop=next(t for t in tx if t["kind"]=="stop_loss")
        self.assertLess(D(stop["price"]),D("127"))

    def test_partial_stop_continues_as_pending_exit_instead_of_resurrecting(self):
        self.order(self.analyze(),quantity="10")
        self.event()
        self.event(open="128.5",low="128",high="129",close="128.8",volume="200")
        self.assertEqual(D(self.positions()[0]["quantity"]),D("8"))
        self.assertTrue(self.account()["paused"])
        resume=self.client.post("/api/v2/portfolios/MANUAL/pause",json={"paused":False})
        self.assertEqual(resume.status_code,409)
        self.assertEqual(resume.json()["error"]["code"],"UNRESOLVED_PAPER_EXIT")
        self.event(open="129.2",low="129",high="130.2",close="130",volume="10000")
        self.assertEqual(self.positions(),[])

    def test_multiple_queued_closes_share_liquidity_without_overclosing(self):
        self.order(self.analyze(),quantity="10")
        self.event()
        p=self.positions()[0]
        self.close(p,quantity="6",key="first-queued-close")
        self.close(p,quantity="4",key="second-queued-close")
        bad=self.client.post(f"/api/v2/portfolios/MANUAL/positions/{p['position_id']}/close",json={"quantity":"1","idempotency_key":"overlapping-close-key"})
        self.assertEqual(bad.status_code,422)
        self.event(volume="300")
        self.assertEqual(D(self.positions()[0]["quantity"]),D("7"))
        self.event()
        self.assertEqual(self.positions(),[])
        tx=self.client.get("/api/v2/portfolios/MANUAL/transactions").json()
        self.assertEqual(sum(D(t["quantity"]) for t in tx if t["kind"].startswith("manual_close:")),D("10"))

    def test_expired_partial_entry_releases_unfilled_cash_but_keeps_position(self):
        a=self.analyze(timeframe="1m",timeframes=[])
        self.order(a,quantity="10")
        self.event(volume="200")
        for _ in range(3): self.event(volume="0")
        self.assertEqual(D(self.positions()[0]["quantity"]),D("2"))
        self.assertEqual(D(self.account()["reserved_cash_quote"]),D("0"))
        self.assertEqual(self.client.get("/api/v2/portfolios/MANUAL/orders").json()[0]["status"],"expired_remainder")

    def test_engine_failure_has_explicit_wait_reason_and_no_auto_order(self):
        with patch("market_ai.engines.technical.compute",side_effect=RuntimeError("injected engine outage")):
            result=self.analyze(auto_paper=True)
        self.assertEqual(result["direction"],"WAIT")
        self.assertEqual(result["reason"],"technical_engine_unavailable")
        self.assertIsNone(result["levels"])
        self.assertTrue(any("technical_unavailable:engine_error" in e for e in result["quality"]["issues"]))
        self.assertEqual(self.client.get("/api/v2/portfolios/AUTO/orders").json(),[])

    def test_unexpected_error_keeps_json_contract_without_exception_payload(self):
        with TestClient(self.app,headers={"Authorization":"Bearer "+TOKEN},raise_server_exceptions=False) as client:
            with patch.object(self.app.state.v2.ledger,"account",side_effect=RuntimeError("internal-detail-must-not-echo")):
                r=client.get("/api/v2/portfolios/MANUAL")
        self.assertEqual(r.status_code,500)
        self.assertEqual(r.json()["error"]["code"],"V2_INTERNAL_ERROR")
        self.assertNotIn("internal-detail-must-not-echo",r.text)

    def test_chart_reads_exact_saved_closed_snapshot_without_provider_io(self):
        a=self.analyze()
        self.now+=7200000
        with patch.object(self.app.state.v2.analysis.provider,"candles",side_effect=AssertionError("history must not fetch")):
            r=self.client.get(f"/api/v2/analyses/{a['analysis_id']}/candles",params={"timeframe":"1H","limit":3})
        self.assertEqual(r.status_code,200,r.text)
        chart=r.json()
        self.assertTrue(chart["snapshot_only"])
        self.assertEqual(chart["as_of_ms"],a["created_at_ms"])
        self.assertEqual(chart["data_mode"],"fixture")
        self.assertEqual(len(chart["candles"]),3)
        self.assertEqual(D(chart["candles"][-1]["close"]),D(a["price"]))
        self.assertEqual(chart["candles"][-1]["close_time_ms"],a["price_time_ms"])
        self.assertTrue(all(b["is_final"] and b["close_time_ms"]<=a["created_at_ms"] for b in chart["candles"]))
        self.assertEqual(self.client.get(f"/api/v2/analyses/{a['analysis_id']}/candles?timeframe=1D").status_code,404)

    def test_invalid_chart_source_never_substitutes_prices(self):
        a=self.analyze(fixture_case="stale")
        r=self.client.get(f"/api/v2/analyses/{a['analysis_id']}/candles")
        self.assertEqual(r.status_code,409)
        self.assertEqual(r.json()["error"]["code"],"CANDLE_SNAPSHOT_UNAVAILABLE")

    def test_chart_checks_immutable_source_integrity(self):
        a=self.analyze()
        path=f"/api/v2/analyses/{a['analysis_id']}/candles"
        source=self.client.get(path).json()["source_record_id"]
        with closing(sqlite3.connect(self.path)) as c,c:
            c.execute("DROP TRIGGER immutable_records_update")
            c.execute("UPDATE decision_records SET body_json='{}' WHERE record_id=?",(source,))
        r=self.client.get(path)
        self.assertEqual(r.status_code,503)
        self.assertEqual(r.json()["error"]["code"],"STORAGE_CORRUPT")

    def test_partial_tp1_then_manual_reduction_cannot_overclose_or_block_replay(self):
        self.order(self.analyze(), quantity="10")
        self.event()
        self.event(open="130", high="132", low="129.8", close="131.8", volume="200")
        p = self.positions()[0]
        self.assertEqual(D(p["quantity"]), D("8"))
        self.close(p, quantity="6", key="reduce-after-partial-tp1")
        self.event(open="130", high="130.5", low="129.8", close="130", volume="600")
        self.assertEqual(D(self.positions()[0]["quantity"]), D("2"))
        event, receipt = self.event(open="130", high="132", low="129.8", close="131.8")
        self.assertEqual(self.positions(), [])
        self.assertEqual(self.client.post("/api/v2/paper/events", json=event).json(), receipt)
        tx = self.client.get("/api/v2/portfolios/MANUAL/transactions").json()
        self.assertEqual(sum(D(t["quantity"]) for t in tx if t["kind"] != "entry"), D("10"))
        self.assertEqual(D(self.account()["cash_quote"]), D("10000") + sum(D(t["realized_pnl_quote"]) for t in tx))
        self.assertEqual(self.account("AUTO")["cash_quote"], "10000")

    def test_position_pnl_is_independent_of_callers_decimal_context(self):
        from decimal import localcontext, ROUND_UP
        self.order(self.analyze(), quantity="10.123456")
        self.event()
        expected = self.positions()[0]["unrealized_pnl_quote"]
        self.assertEqual(expected, self.account()["unrealized_pnl_quote"])
        with localcontext() as ctx:
            ctx.prec = 6
            ctx.rounding = ROUND_UP
            self.assertEqual(self.positions()[0]["unrealized_pnl_quote"], expected)
            self.assertEqual(self.account()["unrealized_pnl_quote"], expected)

    def test_money_text_uses_fixed_rounding_and_unsigned_zero(self):
        from decimal import localcontext, ROUND_UP
        from market_ai.v2.paper_ledger import text
        with localcontext() as ctx:
            ctx.rounding = ROUND_UP
            self.assertEqual(text(D("1.000000005")), "1.00000000")
        self.assertEqual(text(D("-0")), "0.00000000")
        self.assertEqual(text(D("-0.000000001")), "0.00000000")

    def test_performance_fees_are_independent_of_callers_decimal_context(self):
        from decimal import localcontext, ROUND_UP
        self.order(self.analyze(), quantity="10.123456")
        self.event()
        self.close(self.positions()[0])
        self.event(open="130.5", high="130.8", low="130.3", close="130.6")
        expected = self.client.get("/api/v2/performance").json()
        with localcontext() as ctx:
            ctx.prec = 6
            ctx.rounding = ROUND_UP
            self.assertEqual(self.client.get("/api/v2/performance").json(), expected)

    def test_invalid_numeric_inputs_never_create_orders_closes_or_events(self):
        a = self.analyze()
        self.order(a, quantity="1")
        self.event()
        p = self.positions()[0]
        before = self.account()
        invalid = ("-0", "0", "-1", "NaN", "sNaN", "Infinity", "-Infinity", "garbage", "0.000000001")
        for value in invalid:
            with self.subTest(value=value):
                order = self.client.post("/api/v2/portfolios/MANUAL/orders", json={
                    "analysis_id": a["analysis_id"], "quantity": value, "idempotency_key": "invalid-order-numeric"})
                close = self.client.post(f"/api/v2/portfolios/MANUAL/positions/{p['position_id']}/close", json={
                    "quantity": value, "idempotency_key": "invalid-close-numeric"})
                self.assertEqual(order.status_code, 422, order.text)
                self.assertEqual(close.status_code, 422, close.text)
        event = {"symbol": "BTCUSDT", "open_time_ms": self.now, "close_time_ms": self.now+60000,
                 "open": "130", "high": "131", "low": "129.8", "close": "130", "volume": "100"}
        self.now += 60000
        for field in ("open", "high", "low", "close", "volume"):
            for value in ("NaN", "sNaN", "Infinity", "-Infinity", "garbage", "-1"):
                with self.subTest(field=field, value=value):
                    r = self.client.post("/api/v2/paper/events", json={**event, field: value})
                    self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(self.account(), before)
        self.assertEqual(self.positions()[0], p)
        self.assertEqual(len(self.client.get("/api/v2/portfolios/MANUAL/orders").json()), 1)
        self.assertEqual(len(self.client.get("/api/v2/portfolios/MANUAL/transactions").json()), 1)
        self.assertEqual(self.client.post("/api/v2/paper/events", json=event).status_code, 200)

    def test_concurrent_event_and_restart_keep_account_liquidity_and_journal_isolated(self):
        a = self.analyze()
        self.order(a, account="AUTO", quantity="10", key="explicit-auto-test-order")
        self.order(a, quantity="10")
        start = self.now
        self.now += 60000
        event = {"symbol": "BTCUSDT", "open_time_ms": start, "close_time_ms": self.now,
                 "open": "129.9", "high": "130.2", "low": "129.5", "close": "130", "volume": "200"}
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: self.client.post("/api/v2/paper/events", json=event), range(2)))
        self.assertEqual([r.status_code for r in responses], [200, 200])
        self.assertEqual(responses[0].json(), responses[1].json())
        for name in ("AUTO", "MANUAL"):
            self.assertEqual(D(self.positions(name)[0]["quantity"]), D("2"))
            tx = self.client.get(f"/api/v2/portfolios/{name}/transactions").json()
            self.assertEqual(len(tx), 1)
            self.assertEqual(D(self.account(name)["cash_quote"]), D("10000")+D(tx[0]["cash_delta_quote"]))
        self.client.close()
        restarted = create_app(self.path, mode="fixture", token=TOKEN, clock=lambda: self.now)
        self.client = TestClient(restarted, headers={"Authorization": "Bearer "+TOKEN})
        self.addCleanup(self.client.close)
        self.assertEqual(self.client.post("/api/v2/paper/events", json=event).json(), responses[0].json())
        for name in ("AUTO", "MANUAL"):
            self.assertEqual(len(self.client.get(f"/api/v2/portfolios/{name}/transactions").json()), 1)

    def test_second_account_journal_failure_rolls_back_both_accounts_and_retries_once(self):
        a = self.analyze()
        self.order(a, account="AUTO", quantity="1", key="explicit-auto-rollback")
        self.order(a, quantity="1")
        before = [self.account(name) for name in ("AUTO", "MANUAL")]
        start = self.now
        self.now += 60000
        event = {"symbol": "BTCUSDT", "open_time_ms": start, "close_time_ms": self.now,
                 "open": "129.9", "high": "130.2", "low": "129.5", "close": "130", "volume": "10000"}
        ledger = self.app.state.v2.ledger
        original = ledger._journal
        calls = []
        def fail_second(*args, **kwargs):
            calls.append(True)
            if len(calls) == 2:
                raise sqlite3.OperationalError("injected second account journal failure")
            return original(*args, **kwargs)
        with patch.object(ledger, "_journal", side_effect=fail_second), self.assertLogs("market_ai.v2.api", level="ERROR"):
            self.assertEqual(self.client.post("/api/v2/paper/events", json=event).status_code, 503)
        self.assertEqual(len(calls), 2)
        self.assertEqual([self.account(name) for name in ("AUTO", "MANUAL")], before)
        for name in ("AUTO", "MANUAL"):
            self.assertEqual(self.positions(name), [])
            self.assertEqual(self.client.get(f"/api/v2/portfolios/{name}/transactions").json(), [])
        self.assertEqual(self.client.post("/api/v2/paper/events", json=event).status_code, 200)
        for name in ("AUTO", "MANUAL"):
            self.assertEqual(len(self.client.get(f"/api/v2/portfolios/{name}/transactions").json()), 1)
