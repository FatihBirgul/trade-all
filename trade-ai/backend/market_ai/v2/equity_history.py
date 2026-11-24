"""Forward-only immutable observations, captured on the ledger connection.

No historical interpolation/backfill. Each mark keeps its own source/time;
stale/incomplete observations are retained but excluded from drawdown and charts.
"""
from typing import Literal
from .api_models import Model
from .product_db import fingerprint
from .errors import V2Error
from . import domain_journal as domain

class EquityPoint(Model):
    schema_version: Literal[1] = 1
    snapshot_id: str
    portfolio_id: Literal['AUTO','MANUAL']
    data_mode: Literal['fixture','live']
    proof_coverage: Literal['domain_journal','checksum_only'] = 'checksum_only'
    quote_currency: Literal['USDT'] = 'USDT'
    sequence: int
    recorded_at_ms: int
    effective_at_ms: int
    source: dict
    transaction_watermark: int
    cash_quote: str
    reserved_cash_quote: str
    available_cash_quote: str
    equity_quote: str | None
    realized_pnl_quote: str
    unrealized_pnl_quote: str | None
    fees_quote: str
    open_positions: int
    closed_positions: int
    ambiguous_positions: int
    pending_orders: int
    marks: list[dict]
    reservations: list[dict]
    strategy_results: list[dict]
    quality_status: Literal['complete','stale','incomplete']
    chart_eligible: bool
    peak_equity_quote: str | None
    maximum_drawdown_quote: str
    maximum_drawdown_pct: str
    drawdown_scope: Literal['observed_complete_snapshots_since_coverage'] = 'observed_complete_snapshots_since_coverage'
    spread_slippage_breakdown: Literal['not_separately_recorded'] = 'not_separately_recorded'

class EquityHistoryResponse(Model):
    portfolio_id: Literal['AUTO','MANUAL']
    data_mode: Literal['fixture','live']
    coverage: Literal['forward_only'] = 'forward_only'
    coverage_started_at_ms: int
    audit_coverage: Literal['domain_journal','checksum_only']
    points: list[EquityPoint]
    has_more: bool
    period: Literal['day','week','month']
    period_totals: list[dict]
    period_status: Literal['complete','incomplete_budget_or_timestamp']
    note: str

class EquityHistory:
    def __init__(self,ledger):
        self.ledger,self.db=ledger,ledger.db
        with self.db.transaction() as c:
            c.execute('CREATE TABLE IF NOT EXISTS equity_snapshots(id TEXT PRIMARY KEY,portfolio TEXT NOT NULL,sequence INTEGER NOT NULL,recorded_ms INTEGER NOT NULL,body TEXT NOT NULL,body_hash TEXT NOT NULL,UNIQUE(portfolio,sequence))')
            c.execute('CREATE INDEX IF NOT EXISTS equity_account_time ON equity_snapshots(portfolio,recorded_ms,sequence)')
            for op in ('UPDATE','DELETE'):
                c.execute(f"CREATE TRIGGER IF NOT EXISTS equity_snapshots_{op.lower()} BEFORE {op} ON equity_snapshots BEGIN SELECT RAISE(ABORT,'immutable equity observation'); END")
            c.execute("CREATE INDEX IF NOT EXISTS transaction_account_time_ms ON transactions(portfolio,json_extract(body,'$.time_ms'))")
            domain.attach(c)
            if self.db.get(c,'equity_snapshots','coverage') is None:
                self.db.put(c,'equity_snapshots','coverage',{'kind':'coverage','schema_version':1,'data_mode':self.db.mode,'started_at_ms':self.db.clock(),'backfilled':False},portfolio='GLOBAL',sequence=0,recorded_ms=self.db.clock())
            meta=self.db.get(c,'equity_snapshots','coverage')
            if meta.get('schema_version')!=1 or meta.get('data_mode')!=self.db.mode:
                raise V2Error('STORAGE_CORRUPT','Unsupported equity history schema',503)

    def _value(self,c,account,now):return self.ledger.account(c,account,now)

    def capture(self,c,account,source,now,*,effective_at=None):
        from .paper_ledger import decimal_context
        return decimal_context(self._capture)(c,account,source,now,effective_at=effective_at)

    def _capture(self,c,account,source,now,*,effective_at=None):
        from .paper_ledger import dec,text,ZERO
        key=fingerprint({'portfolio':account,'source':source,'equity_version':1})
        if self.db.get(c,'equity_snapshots',key) is not None:return
        a=self._value(c,account,now)
        previous=c.execute('SELECT body,body_hash FROM equity_snapshots WHERE portfolio=? ORDER BY sequence DESC LIMIT 1',(account,)).fetchone()
        previous=self.db.decode(previous) if previous else None
        positions=self.db.rows(c,'positions',account);orders=self.db.rows(c,'orders',account)
        marks=[];status='complete'
        for p in positions:
            if dec(p['quantity'])<=0:continue
            event=c.execute('SELECT id,body,body_hash FROM events WHERE symbol=? AND close_ms=?',(p['symbol'],p['mark_time_ms'])).fetchone()
            receipt=self.db.decode((event[1],event[2])) if event else None
            valid=bool(receipt and dec(receipt['market_event']['close'])==dec(p['mark_price']) and 0<=p['mark_time_ms']<=now)
            if not valid:status='incomplete'
            elif now-p['mark_time_ms']>60000 and status=='complete':status='stale'
            marks.append({k:p[k] for k in ('position_id','order_id','symbol','quantity','cost_basis_quote','mark_price','mark_time_ms','status')})
            marks[-1]['event_id']=event[0] if valid else None
        reservations=[{k:o[k] for k in ('order_id','status','remaining_quantity','reservation_per_unit')} for o in orders if o['status'] in ('pending','partially_filled')]
        transactions=self.db.rows(c,'transactions',account);strategies={}
        for t in transactions:
            order=self.db.get(c,'orders',t['order_id']);analysis=self.db.get(c,'analyses',order['analysis_id'])
            strategy=analysis.get('router',{}).get('strategy_id') if analysis else None
            name=strategy or 'unknown'
            totals=strategies.setdefault(name,[ZERO,ZERO,0]);totals[0]+=dec(t['realized_pnl_quote']);totals[1]+=dec(t['fee_quote']);totals[2]+=1
        peak=dec(previous['peak_equity_quote']) if previous and previous['peak_equity_quote'] is not None else None
        maximum=dec(previous['maximum_drawdown_quote']) if previous else ZERO
        maximum_pct=dec(previous['maximum_drawdown_pct']) if previous else ZERO
        eligible=status=='complete'
        if eligible:
            equity=dec(a['equity_quote']);peak=max(peak,equity) if peak is not None else equity
            maximum=max(maximum,peak-equity)
            maximum_pct=max(maximum_pct,(peak-equity)/peak*100 if peak>0 else ZERO)
        point=EquityPoint(snapshot_id=key,portfolio_id=account,data_mode=self.db.mode,proof_coverage='domain_journal' if self.db.domain_enabled else 'checksum_only',
            sequence=previous['sequence']+1 if previous else 1,recorded_at_ms=now,effective_at_ms=effective_at if effective_at is not None else now,
            source=source,transaction_watermark=c.execute('SELECT COALESCE(MAX(rowid),0) FROM transactions').fetchone()[0],
            **{k:text(dec(a[k])) for k in ('cash_quote','reserved_cash_quote','available_cash_quote','realized_pnl_quote')},
            equity_quote=a['equity_quote'] if status!='incomplete' else None,unrealized_pnl_quote=a['unrealized_pnl_quote'] if status!='incomplete' else None,
            fees_quote=text(sum((dec(t['fee_quote']) for t in transactions),ZERO)),open_positions=a['open_positions'],
            closed_positions=sum(p['status']=='closed' for p in positions),ambiguous_positions=sum(bool(p.get('ambiguity_seen')) for p in positions),
            pending_orders=a['pending_orders'],marks=sorted(marks,key=lambda m:m['position_id']),reservations=sorted(reservations,key=lambda o:o['order_id']),
            strategy_results=[{'strategy_id':name,'realized_pnl_quote':text(v[0]),'fees_quote':text(v[1]),'transaction_count':v[2]} for name,v in sorted(strategies.items())],
            quality_status=status,chart_eligible=eligible,peak_equity_quote=text(peak) if peak is not None else None,
            maximum_drawdown_quote=text(maximum),maximum_drawdown_pct=text(maximum_pct)).model_dump(mode='json')
        self.db.put(c,'equity_snapshots',key,point,portfolio=account,sequence=point['sequence'],recorded_ms=now)

    def read(self,account,*,limit=100,offset=0,from_ms=0,to_ms=9223372036854775807,period='day'):
        from .paper_ledger import decimal_context
        return decimal_context(self._read)(account,limit=limit,offset=offset,from_ms=from_ms,to_ms=to_ms,period=period)

    def _read(self,account,*,limit,offset,from_ms,to_ms,period):
        from .paper_ledger import dec,text,ZERO
        from datetime import datetime,timezone,timedelta
        if from_ms>to_ms:raise V2Error('INVALID_HISTORY_RANGE','from_ms must not exceed to_ms',422)
        with self.db.transaction() as c:
            meta=self.db.get(c,'equity_snapshots','coverage')
            rows=c.execute('SELECT body,body_hash FROM equity_snapshots WHERE portfolio=? AND recorded_ms BETWEEN ? AND ? ORDER BY sequence DESC LIMIT ? OFFSET ?',(account,from_ms,to_ms,limit+1,offset)).fetchall()
            periods={};period_status='complete'
            txrows=c.execute("SELECT body,body_hash FROM transactions WHERE portfolio=? AND json_extract(body,'$.time_ms') BETWEEN ? AND ? ORDER BY rowid DESC LIMIT 10001",(account,from_ms,to_ms))
            count=0
            for row in txrows:
                count+=1
                if count>10000:period_status='incomplete_budget_or_timestamp';break
                t=self.db.decode(row)
                if t['portfolio_id']!=account:raise V2Error('STORAGE_CORRUPT','Transaction account mismatch',503)
                try:
                    stamp=datetime(1970,1,1,tzinfo=timezone.utc)+timedelta(milliseconds=t['time_ms'])
                    iso=stamp.isocalendar()
                    key=stamp.strftime('%Y-%m-%d') if period=='day' else stamp.strftime('%Y-%m') if period=='month' else f'{iso.year:04d}-W{iso.week:02d}'
                except (OverflowError,TypeError,ValueError):period_status='incomplete_budget_or_timestamp';break
                totals=periods.setdefault(key,[ZERO,ZERO,0]);totals[0]+=dec(t['realized_pnl_quote']);totals[1]+=dec(t['fee_quote']);totals[2]+=1
                if len(periods)>200:period_status='incomplete_budget_or_timestamp';break
            summaries=[{'period':k,'realized_pnl_quote':text(v[0]),'fees_quote':text(v[1]),'transaction_count':v[2]} for k,v in sorted(periods.items())] if period_status=='complete' else []
            return EquityHistoryResponse(period=period,period_totals=summaries,period_status=period_status,portfolio_id=account,data_mode=self.db.mode,coverage_started_at_ms=meta['started_at_ms'],audit_coverage='domain_journal' if self.db.domain_enabled else 'checksum_only',
                points=[self.db.decode(r) for r in reversed(rows[:limit])],has_more=len(rows)>limit,
                note='Forward observations only; no historical backfill/interpolation. Drawdown covers observed complete snapshots since capture began, not continuous prices or backtest. Stale/incomplete marks are excluded from charts. Fees are included in PnL; spread/slippage are embedded in execution prices, not separately recorded.')
