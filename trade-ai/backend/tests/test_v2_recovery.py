"""Bounded historical recovery, restart, no fabricated marks, atomic outbox."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from dataclasses import replace
from fastapi.testclient import TestClient
from market_ai.v2.api import create_app
from market_ai.v2.spot_provider import FixtureSpotProvider, BinanceSpotProvider, ProviderUnavailable
from market_ai.v2.market_data_contract import Candle, Instrument
import httpx

NOW=1800000000000
TOKEN="recovery-test-token-not-a-secret-32"
TF=60000


class HistoryProvider(FixtureSpotProvider):
    def __init__(self): self.windows=[]
    def candle_window(self,symbol,start,end):
        self.windows.append((start,end))
        identity=Instrument(symbol,"crypto_spot",self.venue,"last","spot","USDT")
        return [Candle(identity,t,t+TF,True,130,130.1,129.8,130,10000,"real",self.source_name) for t in range(start,end,TF)]
    def candles(self,symbol,tf,now):
        if tf!="1m": return super().candles(symbol,tf,now)
        end=now//TF*TF
        return self.candle_window(symbol,end-300*TF,end)


class RecoveryTests(TestCase):
    def setUp(self):
        self.directory=TemporaryDirectory(prefix="v2-recovery-");self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name)/"isolated.sqlite";self.now=NOW;self.restart()
        a=self.client.post("/api/v2/analyze",json={"data_mode":"fixture","idempotency_key":"recovery-analysis-key"}).json()
        r=self.client.post("/api/v2/portfolios/MANUAL/orders",json={"analysis_id":a["analysis_id"],"quantity":"1","idempotency_key":"recovery-order-key"})
        self.assertEqual(r.status_code,200,r.text)
        self.now+=TF
        e={"symbol":"BTCUSDT","open_time_ms":NOW,"close_time_ms":self.now,"open":"129.9","high":"130.2","low":"129.5","close":"130","volume":"10000"}
        self.assertEqual(self.client.post("/api/v2/paper/events",json=e).status_code,200)
        self.provider=HistoryProvider();self.app.state.v2.analysis.provider=self.provider
        self.now+=720*TF

    def restart(self):
        self.app=create_app(self.path,mode="fixture",token=TOKEN,clock=lambda:self.now)
        self.client=TestClient(self.app,headers={"Authorization":"Bearer "+TOKEN});self.addCleanup(self.client.close)

    def poll(self): return self.client.post("/api/v2/paper/poll",json={"symbols":["BTCUSDT"]})
    def positions(self): return self.client.get("/api/v2/portfolios/MANUAL/positions").json()
    def transactions(self): return self.client.get("/api/v2/portfolios/MANUAL/transactions").json()

    def test_twelve_hour_recovery_in_bounded_pages_restart_and_no_duplicate_fill(self):
        first=self.poll();self.assertEqual(first.status_code,409,first.text)
        self.assertEqual(first.json()["error"]["code"],"PAPER_RECOVERY_IN_PROGRESS")
        self.assertEqual(self.positions()[0]["mark_time_ms"],NOW+301*TF)
        self.client.close();self.restart();self.app.state.v2.analysis.provider=self.provider
        self.assertEqual(self.poll().status_code,409)
        final=self.poll();self.assertEqual(final.status_code,200,final.text)
        self.assertEqual(self.positions()[0]["mark_time_ms"],self.now)
        tx=self.transactions();self.assertEqual(len(tx),1)
        self.assertEqual(self.poll().status_code,200)
        self.assertEqual(self.transactions(),tx)
        self.assertTrue(all(end-start<=300*TF for start,end in self.provider.windows))

    def test_missing_history_is_visible_and_leaves_cash_and_marks_untouched(self):
        before=self.positions(),self.transactions()
        self.app.state.v2.analysis.provider=FixtureSpotProvider()
        result=self.poll();self.assertEqual(result.status_code,503,result.text)
        self.assertEqual(result.json()["error"]["code"],"PAPER_HISTORY_UNAVAILABLE")
        self.assertEqual((self.positions(),self.transactions()),before)

    def test_partial_gap_wrong_source_and_unfinished_history_are_rejected_atomically(self):
        original=self.provider.candle_window
        def corrupt(kind):
            def window(symbol,start,end):
                b=original(symbol,start,end)
                # Leave latest source page intact; corrupt only required history.
                if start==self.now-300*TF:return b
                if kind=="boundary":return b[1:]
                if kind=="gap":return b[:50]+b[51:]
                return b[:-1]+[replace(b[-1],**({"source":"other"} if kind=="source" else {"is_final":False}))]
            return window
        before=self.positions(),self.transactions()
        for kind in ("boundary","gap","source","unfinished"):
            with self.subTest(kind=kind),patch.object(self.provider,"candle_window",side_effect=corrupt(kind)):
                result=self.poll();self.assertEqual(result.status_code,503,result.text)
                self.assertEqual((self.positions(),self.transactions()),before)

    def test_outage_and_stale_latest_do_not_use_history_to_hide_failure(self):
        before=self.positions()
        with patch.object(self.provider,"candles",side_effect=ProviderUnavailable("offline")):
            self.assertEqual(self.poll().json()["error"]["code"],"PROVIDER_UNAVAILABLE")
        old=self.provider.candles("BTCUSDT","1m",self.now-10*TF)
        with patch.object(self.provider,"candles",return_value=old),patch.object(self.provider,"candle_window",side_effect=AssertionError("stale source cannot recover")):
            self.assertEqual(self.poll().json()["error"]["code"],"MARKET_DATA_INVALID")
        self.assertEqual(self.positions(),before)

    def test_scanner_blocks_new_jobs_until_recovered_and_error_notifications_deduplicate(self):
        scanner=self.app.state.v2.scanner
        scanner.pause(False)
        self.client.post("/api/v2/watchlist",json={"symbol":"ETHUSDT","timeframe":"1H"})
        first=scanner.tick();self.assertEqual(first["status"],"blocked")
        self.assertEqual(first["reason"],"PAPER_RECOVERY_IN_PROGRESS")
        self.assertEqual(scanner.rows("scanner_jobs"),[])
        self.assertEqual(scanner.tick()["status"],"blocked")
        with scanner.db.transaction() as c:
            notes=scanner.db.rows(c,"notifications")
        self.assertEqual(sum(n["kind"]=="scanner_error" for n in notes),1)
        result=scanner.tick();self.assertEqual(result["status"],"completed",result)
        self.assertEqual(len(result["jobs"]),1)

    def test_history_event_and_notifications_rollback_together(self):
        scanner=self.app.state.v2.scanner;scanner.pause(False)
        before=self.positions(),self.transactions()
        with patch.object(scanner,"_notify",side_effect=RuntimeError("outbox failure")):
            with self.assertRaises(RuntimeError):scanner.tick()
        self.assertEqual((self.positions(),self.transactions()),before)
        self.assertEqual(scanner.rows("notifications"),[])
        self.assertEqual(scanner.tick()["status"],"blocked")

    def test_provider_exact_public_historical_window_and_rate_limit_no_mirror_bypass(self):
        calls=[]
        def handle(request):
            calls.append(request)
            return httpx.Response(200,json=[[NOW,"100","101","99","100","10",NOW+TF-1]])
        provider=BinanceSpotProvider(transport=httpx.MockTransport(handle))
        bars=provider.candle_window("BTCUSDT",NOW,NOW+TF)
        self.assertEqual(bars[0].close_time_ms,NOW+TF)
        self.assertEqual(calls[0].url.params["startTime"],str(NOW))
        self.assertEqual(calls[0].url.params["endTime"],str(NOW+TF-1))
        for start,end in ((NOW+1,NOW+TF),(NOW,NOW+301*TF),(NOW,NOW)):
            with self.assertRaises(ValueError):provider.candle_window("BTCUSDT",start,end)
        count=[]
        def blocked(request):count.append(request);return httpx.Response(429)
        with self.assertRaises(ProviderUnavailable):
            BinanceSpotProvider(transport=httpx.MockTransport(blocked)).candle_window("BTCUSDT",NOW,NOW+TF)
        self.assertEqual(len(count),1)
