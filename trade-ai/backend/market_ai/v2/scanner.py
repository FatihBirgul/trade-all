"""Bounded cooperative scanner. Disabled by default, durable jobs and outbox.

No catch-up analyses against historical prices, no delivery service, no real orders.
An optional local worker calls tick once a minute; API ticks use the same lease.
"""
from uuid import uuid4
import logging
import threading
from .api_models import AnalyzeRequest
from .errors import V2Error
from .market_poller import MarketPoller
from .product_db import fingerprint
from . import domain_journal as domain
from .technical_adapter import TIMEFRAME_MS


class Scanner:
    def __init__(self, runtime):
        self.r, self.db = runtime, runtime.db
        self.poller = MarketPoller(runtime)
        # Additive feature tables only after ProductDatabase ownership/mode
        # verification. No legacy DB is opened or migrated by this component.
        with self.db.transaction() as c:
            for table in ("watchlist","scanner_state","scanner_jobs","notifications"):
                c.execute(f"CREATE TABLE IF NOT EXISTS {table}(id TEXT PRIMARY KEY,body TEXT NOT NULL,body_hash TEXT NOT NULL)")
            for op in ("UPDATE","DELETE"):
                c.execute(f"CREATE TRIGGER IF NOT EXISTS notifications_{op.lower()} BEFORE {op} ON notifications BEGIN SELECT RAISE(ABORT,'immutable outbox'); END")
            c.execute("CREATE INDEX IF NOT EXISTS scanner_job_status ON scanner_jobs(json_extract(body,'$.status'))")
            domain.attach(c)
            if self.db.get(c,"scanner_state","state") is None:
                self.db.put(c,"scanner_state","state",{"paused":True,"lease_id":None,"lease_until_ms":0,
                    "last_tick_ms":None,"last_error":None,"max_analyses_per_tick":2,"interval_seconds":60})

    def state(self):
        with self.db.transaction() as c:
            return self.db.get(c,"scanner_state","state")

    def pause(self, paused):
        with self.db.transaction() as c:
            if self.db.domain_enabled:
                domain.begin(c, effective_at=self.r.clock(), source={"control":"scanner_pause"})
                domain.note(c, "control.requested", {"paused":paused})
            state=self.db.get(c,"scanner_state","state")
            state["paused"]=paused
            self.db.update(c,"scanner_state","state",state)
            return state

    def watch(self, request):
        body=request.model_dump(mode="json")
        if body.get('profile_id') is None:body.pop('profile_id',None)
        key=body["symbol"]+":"+body["timeframe"]
        with self.db.transaction() as c:
            existing=self.db.get(c,'watchlist',key)
            if 'profile_id' not in request.model_fields_set and existing and existing.get('profile_id'):
                body['profile_id']=existing['profile_id']
            if body.get('profile_id'):
                _,profile=self.r.analysis.profiles.get(c,'AUTO',body['profile_id'])
                if profile.setup_timeframe!=request.timeframe:
                    raise V2Error('PROFILE_TIMEFRAME_MISMATCH','Scanner setup timeframe must match the profile',422)
            rows=self.db.rows(c,"watchlist")
            if self.db.get(c,"watchlist",key) is None and len(rows)>=10:
                raise V2Error("WATCHLIST_LIMIT","At most ten watchlist entries are supported")
            body["watch_id"]=key
            if self.db.get(c,"watchlist",key) is None: self.db.put(c,"watchlist",key,body)
            else: self.db.update(c,"watchlist",key,body)
        return body

    def rows(self, table, limit=20, offset=0):
        if table not in ("watchlist","scanner_jobs","notifications"):
            raise ValueError("Unsupported scanner collection")
        with self.db.transaction() as c:
            return [self.db.decode(row) for row in c.execute(f"SELECT body,body_hash FROM {table} ORDER BY rowid DESC LIMIT ? OFFSET ?",(limit,offset))]

    def _notify(self,c,key,kind,details):
        if self.db.get(c,"notifications",key) is None:
            self.db.put(c,"notifications",key,{"notification_id":key,"kind":kind,"details":details,
                "created_at_ms":self.r.clock(),"data_mode":self.db.mode,"delivery_status":"pending",
                "delivery_service":"not_configured"})

    def tick(self):
        now, owner=self.r.clock(),uuid4().hex
        with self.db.transaction() as c:
            state=self.db.get(c,"scanner_state","state")
            if state["paused"]: return {"status":"paused","jobs":[]}
            if state["lease_until_ms"]>now: return {"status":"busy","jobs":[]}
            state.update(lease_id=owner,lease_until_ms=now+120000,last_tick_ms=now,last_error=None)
            self.db.update(c,"scanner_state","state",state)
        completed=[]
        try:
            # Existing exposures get first use of the public data budget. If
            # recovery fails no new analysis/order is attempted in this tick.
            def paper_event(c,event):
                self._guard(c,owner)
                if event["processed"]:
                    self._notify(c,event["event_id"],"paper_event",event)
            self.poller.poll(self.poller.active_symbols(),on_event=paper_event)
            with self.db.transaction() as c:
                watches=[w for w in self.db.rows(c,"watchlist") if w["enabled"]]
                running=[self.db.decode(row) for row in c.execute("SELECT body,body_hash FROM scanner_jobs WHERE json_extract(body,'$.status')='running'")]
                for job in running:
                    if job["status"]=="running" and job["closed_bar_ms"] < now//TIMEFRAME_MS[job["timeframe"]]*TIMEFRAME_MS[job["timeframe"]]:
                        job.update(status="skipped_stale",reason="restart_does_not_replay_historical_analysis")
                        self.db.update(c,"scanner_jobs",job["job_id"],job)
            for watch in sorted(watches,key=lambda w:w["watch_id"]):
                if len(completed)>=2: break
                tf=watch["timeframe"]
                boundary=now//TIMEFRAME_MS[tf]*TIMEFRAME_MS[tf]
                key=fingerprint({"watch":watch,"closed_bar_ms":boundary,"mode":self.db.mode,
                                 "provider":self.r.analysis.provider.name,"scanner_version":"1"})
                with self.db.transaction() as c:
                    self._guard(c,owner)
                    job=self.db.get(c,"scanner_jobs",key)
                    if job and job["status"] in ("completed","failed","skipped_stale"): continue
                    job={"job_id":key,"symbol":watch["symbol"],"timeframe":tf,"closed_bar_ms":boundary,
                         "status":"running","started_at_ms":self.r.clock(),"analysis_id":None,"reason":None}
                    if self.db.get(c,"scanner_jobs",key) is None: self.db.put(c,"scanner_jobs",key,job)
                    else: self.db.update(c,"scanner_jobs",key,job)
                try:
                    frames=[]
                    if watch.get('profile_id'):
                        with self.db.transaction() as c:
                            _,profile=self.r.analysis.profiles.get(c,'AUTO',watch['profile_id'])
                            frames=[t for t in profile.timeframes if t!=tf]
                    request=AnalyzeRequest(profile_id=watch.get('profile_id'),symbol=watch["symbol"],timeframe=tf,timeframes=frames,data_mode=self.db.mode,
                                           auto_paper=watch["auto_paper"],idempotency_key="scanner:"+key)
                    result=self.r.analysis.analyze(request,commit_guard=lambda c:self._guard(c,owner,boundary,tf,watch))
                    job.update(status="completed",analysis_id=result.analysis_id,reason=result.reason)
                except V2Error as exc:
                    job.update(status="failed",reason=exc.code)
                with self.db.transaction() as c:
                    self.db.update(c,"scanner_jobs",key,job)
                    self._notify(c,key,"analysis" if job["status"]=="completed" else "scanner_error",job)
                completed.append(job)
            return {"status":"completed","jobs":completed}
        except V2Error as exc:
            with self.db.transaction() as c:
                state=self.db.get(c,"scanner_state","state")
                if state["lease_id"]==owner:
                    state["last_error"]=exc.code
                    self.db.update(c,"scanner_state","state",state)
                self._notify(c,fingerprint({"error":exc.code,"minute":now//60000}),"scanner_error",{"code":exc.code})
            return {"status":"blocked","reason":exc.code,"jobs":completed}
        finally:
            with self.db.transaction() as c:
                state=self.db.get(c,"scanner_state","state")
                if state["lease_id"]==owner:
                    state.update(lease_id=None,lease_until_ms=0)
                    self.db.update(c,"scanner_state","state",state)

    def _guard(self,c,owner,boundary=None,tf=None,watch=None):
        state=self.db.get(c,"scanner_state","state")
        if state["paused"] or state["lease_id"]!=owner or state["lease_until_ms"]<=self.r.clock():
            if self.db.domain_enabled:domain.blocked(c, self.r.clock(), {"control":"scanner_guard"})
            raise V2Error("SCANNER_PAUSED","Scanner paused or execution lease expired")
        if watch is not None and self.db.get(c,'watchlist',watch['watch_id'])!=watch:
            if self.db.domain_enabled:domain.blocked(c,self.r.clock(),{'control':'scanner_guard'})
            raise V2Error('SCANNER_WATCH_CHANGED','Watch configuration changed during analysis')
        if boundary is not None and self.r.clock()//TIMEFRAME_MS[tf]*TIMEFRAME_MS[tf]!=boundary:
            if self.db.domain_enabled:domain.blocked(c, self.r.clock(), {"control":"scanner_guard"})
            raise V2Error("SCANNER_STALE_JOB","Closed-bar boundary changed during analysis")


class ScannerWorker:
    """One cooperative local thread; no tight loops, process installs or timers."""
    def __init__(self,scanner):
        self.scanner=scanner
        self.stop_event=threading.Event()
        self.thread=threading.Thread(target=self._run,name="v2-bounded-scanner",daemon=True)

    def _run(self):
        while not self.stop_event.is_set():
            try:
                self.scanner.tick()
            except Exception:
                logging.getLogger(__name__).exception("Scanner tick failed; no success claimed")
            if self.stop_event.wait(60): break

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.scanner.pause(True)
        self.thread.join(timeout=10)
