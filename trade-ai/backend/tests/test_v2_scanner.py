"""Scanner durability and safety, always under the V2 offline/temp-DB guard."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from threading import Event
from fastapi.testclient import TestClient
from market_ai.v2.api import create_app
from market_ai.v2.spot_provider import ProviderUnavailable
from market_ai.v2.scanner import ScannerWorker

TOKEN="fixture-scanner-token-not-a-secret"
NOW=1800000000000


class ScannerTests(TestCase):
    def setUp(self):
        self.directory=TemporaryDirectory(prefix="v2-scanner-test-")
        self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name)/"scanner.sqlite"
        self.now=NOW
        self.restart()

    def restart(self):
        self.app=create_app(self.path,mode="fixture",token=TOKEN,clock=lambda:self.now)
        self.client=TestClient(self.app,headers={"Authorization":"Bearer "+TOKEN})
        self.addCleanup(self.client.close)
        self.scanner=self.app.state.v2.scanner

    def watch(self,symbol="BTCUSDT",tf="1H",auto=False,enabled=True):
        r=self.client.post("/api/v2/watchlist",json={"symbol":symbol,"timeframe":tf,"auto_paper":auto,"enabled":enabled})
        self.assertEqual(r.status_code,200,r.text)
        return r.json()

    def tick(self):
        r=self.client.post("/api/v2/scanner/tick")
        self.assertEqual(r.status_code,200,r.text)
        return r.json()

    def test_disabled_by_default_and_empty_tick_makes_no_network_calls(self):
        with patch.object(self.app.state.v2.analysis.provider,"candles",side_effect=AssertionError("no I/O")):
            self.assertEqual(self.tick()["status"],"paused")
            self.scanner.pause(False)
            self.assertEqual(self.tick()["jobs"],[])

    def test_closed_bar_dedup_restart_and_pending_notification(self):
        self.watch()
        self.scanner.pause(False)
        first=self.tick()["jobs"]
        self.assertEqual(len(first),1)
        self.assertEqual(first[0]["status"],"completed")
        self.assertEqual(self.tick()["jobs"],[])
        self.restart()
        self.assertEqual(self.tick()["jobs"],[])
        notes=self.client.get("/api/v2/notifications").json()
        self.assertEqual(len(notes),1)
        self.assertEqual(notes[0]["delivery_status"],"pending")
        self.assertEqual(notes[0]["data_mode"],"fixture")
        self.now+=3600000
        self.assertEqual(len(self.tick()["jobs"]),1)

    def test_two_analysis_budget_and_soft_disabled_watch(self):
        for symbol in ("BTCUSDT","ETHUSDT","SOLUSDT"): self.watch(symbol)
        self.scanner.pause(False)
        self.assertEqual(len(self.tick()["jobs"]),2)
        self.assertEqual(len(self.tick()["jobs"]),1)
        self.watch(enabled=False)
        self.now+=3600000
        self.assertEqual(len(self.tick()["jobs"]),2)

    def test_lease_blocks_parallel_tick_and_recovers_after_expiry(self):
        self.watch()
        self.scanner.pause(False)
        with self.scanner.db.transaction() as c:
            s=self.scanner.db.get(c,"scanner_state","state")
            s.update(lease_id="crashed-process",lease_until_ms=self.now+120000)
            self.scanner.db.update(c,"scanner_state","state",s)
        self.assertEqual(self.tick()["status"],"busy")
        self.now+=120001
        self.assertEqual(len(self.tick()["jobs"]),1)
        self.assertIsNone(self.scanner.state()["lease_id"])

    def test_pause_during_provider_call_prevents_analysis_and_auto_commit(self):
        self.watch(auto=True)
        self.scanner.pause(False)
        provider=self.app.state.v2.analysis.provider
        original=provider.candles
        def pause_before_return(*args):
            self.scanner.pause(True)
            return original(*args)
        with patch.object(provider,"candles",side_effect=pause_before_return):
            jobs=self.tick()["jobs"]
        self.assertEqual(jobs[0]["reason"],"SCANNER_PAUSED")
        self.assertEqual(self.client.get("/api/v2/analyses").json(),[])
        self.assertEqual(self.client.get("/api/v2/portfolios/AUTO/orders").json(),[])

    def test_boundary_change_during_fetch_does_not_trade_stale_job(self):
        self.watch(auto=True)
        self.scanner.pause(False)
        provider=self.app.state.v2.analysis.provider
        original=provider.candles
        def advance(*args):
            result=original(*args)
            self.now+=3600000
            return result
        with patch.object(provider,"candles",side_effect=advance): result=self.tick()
        self.assertIn(result["jobs"][0]["reason"],("SCANNER_PAUSED","SCANNER_STALE_JOB"))
        self.assertEqual(self.client.get("/api/v2/portfolios/AUTO/orders").json(),[])

    def test_outbox_failure_restart_reuses_committed_analysis(self):
        self.watch(auto=True)
        self.scanner.pause(False)
        with patch.object(self.scanner,"_notify",side_effect=RuntimeError("injected post-analysis failure")):
            with self.assertRaises(RuntimeError): self.scanner.tick()
        first=self.client.get("/api/v2/portfolios/AUTO/orders").json()
        self.assertEqual(len(first),1)
        self.restart()
        self.tick()
        self.assertEqual(self.client.get("/api/v2/portfolios/AUTO/orders").json(),first)
        self.assertEqual(len(self.client.get("/api/v2/analyses").json()),1)
        self.assertEqual(len(self.client.get("/api/v2/notifications").json()),1)

    def test_poll_failure_blocks_new_jobs_and_preserves_exposure(self):
        self.watch(auto=True)
        self.scanner.pause(False)
        self.tick()
        orders=self.client.get("/api/v2/portfolios/AUTO/orders").json()
        self.now+=60000
        with patch.object(self.app.state.v2.analysis.provider,"candles",side_effect=ProviderUnavailable("outage")):
            result=self.tick()
        self.assertEqual(result["status"],"blocked")
        self.assertEqual(result["reason"],"PROVIDER_UNAVAILABLE")
        self.assertEqual(self.client.get("/api/v2/portfolios/AUTO/orders").json(),orders)
        self.assertEqual(self.scanner.state()["last_error"],"PROVIDER_UNAVAILABLE")

    def test_poll_rejects_wrong_quote_price_kind_or_source(self):
        self.watch(auto=True)
        self.scanner.pause(False)
        self.tick()
        self.now+=60000
        provider=self.app.state.v2.analysis.provider
        original=provider.candles
        for field,value in (("quote_currency","EUR"),("price_kind","mid"),("source","other-provider"),("volume_kind","tick")):
            def wrong(*args):
                bars=original(*args)
                return [replace(b,**{field:value}) if field in ("source","volume_kind") else replace(b,instrument=replace(b.instrument,**{field:value})) for b in bars]
            with self.subTest(field=field),patch.object(provider,"candles",side_effect=wrong):
                r=self.client.post("/api/v2/paper/poll",json={"symbols":["BTCUSDT"]})
                self.assertEqual(r.status_code,503,r.text)
                self.assertEqual(r.json()["error"]["code"],"MARKET_DATA_INVALID")

    def test_watch_schema_and_auth(self):
        self.assertEqual(self.client.post("/api/v2/watchlist",json={"symbol":"XAUUSD"}).status_code,422)
        self.assertEqual(self.client.post("/api/v2/watchlist",json={"symbol":"BTCUSDT","auto_paper":"yes"}).status_code,422)
        self.assertEqual(self.client.get("/api/v2/scanner",headers={"Authorization":"Bearer wrong"}).status_code,401)

    def test_watch_limit_and_pause_persist(self):
        pairs=[(s,t) for s in ("BTCUSDT","ETHUSDT","SOLUSDT") for t in ("5m","15m","1H","4H","1D")]
        for symbol,tf in pairs[:10]: self.watch(symbol,tf)
        symbol,tf=pairs[10]
        r=self.client.post("/api/v2/watchlist",json={"symbol":symbol,"timeframe":tf})
        self.assertEqual(r.status_code,409)
        self.assertEqual(r.json()["error"]["code"],"WATCHLIST_LIMIT")
        self.scanner.pause(False)
        self.scanner.pause(True)
        self.restart()
        self.assertTrue(self.scanner.state()["paused"])
        self.assertEqual(len(self.client.get("/api/v2/watchlist").json()),10)

    def test_abandoned_old_job_is_not_replayed_as_new_analysis(self):
        self.watch()
        with self.scanner.db.transaction() as c:
            self.scanner.db.put(c,"scanner_jobs","abandoned",{"job_id":"abandoned","symbol":"BTCUSDT",
                "timeframe":"1H","closed_bar_ms":self.now-3600000,"status":"running"})
        self.scanner.pause(False)
        self.tick()
        jobs=self.client.get("/api/v2/scanner/jobs").json()
        self.assertEqual(next(j for j in jobs if j["job_id"]=="abandoned")["status"],"skipped_stale")
        self.assertEqual(len(self.client.get("/api/v2/analyses").json()),1)

    def test_worker_stops_promptly_and_persists_safe_pause(self):
        ticked=Event()
        original=self.scanner.tick
        def tick():
            result=original()
            ticked.set()
            return result
        with patch.object(self.scanner,"tick",side_effect=tick) as calls:
            worker=ScannerWorker(self.scanner)
            worker.start()
            try:
                self.assertTrue(ticked.wait(3))
            finally:
                worker.stop()
            self.assertFalse(worker.thread.is_alive())
            self.assertEqual(calls.call_count,1)
            self.assertTrue(self.scanner.state()["paused"])

    def test_paper_event_and_outbox_rollback_together(self):
        self.watch(auto=True)
        self.scanner.pause(False)
        self.tick()
        self.now+=60000
        original=self.scanner._notify
        def fail_paper(c,key,kind,details):
            if kind=="paper_event": raise RuntimeError("injected outbox failure")
            return original(c,key,kind,details)
        with patch.object(self.scanner,"_notify",side_effect=fail_paper):
            with self.assertRaises(RuntimeError): self.scanner.tick()
        self.assertEqual(self.client.get("/api/v2/portfolios/AUTO/transactions").json(),[])
        self.assertEqual(self.client.get("/api/v2/portfolios/AUTO/positions").json(),[])
        self.restart()
        self.tick()
        self.assertTrue(self.client.get("/api/v2/portfolios/AUTO/transactions").json())
        notes=self.client.get("/api/v2/notifications").json()
        self.assertEqual(sum(n["kind"]=="paper_event" for n in notes),1)
