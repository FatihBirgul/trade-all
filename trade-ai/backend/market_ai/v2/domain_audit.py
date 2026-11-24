"""Independent domain verification. Never imports writer, ledger or API code.

Folds state deltas in a private scratch database, verifies persisted sources and
checks recorded execution decisions against independent Decimal constraints.
It does not re-evaluate strategy selection or every historical risk veto.
"""
from decimal import Decimal, ROUND_FLOOR
from hashlib import sha256
import json

ZERO = '0'*64
MUTABLE = {'accounts','orders','positions','scanner_state','watchlist','scanner_jobs',
           'analysis_tracking','analysis_tracking_state','notification_delivery_state'}
FACTS = {'transactions','events','commands','analyses','notifications','strategy_profiles','equity_snapshots','notification_delivery_attempts','notification_controls'}
KINDS = {'coverage.started','schema.table_registered','state.baseline','state.changed','record.created',
         'command.requested','command.accepted','command.replayed','command.rejected','operation.rejected',
         'control.requested','market.received','market.replayed','order.bar_started','risk.evaluated',
         'entry.decision','exit.decision','protective.evaluated','protective.blocked','request.validation_rejected'}
FIELDS = {
    'notification':{'portfolio_id','preferences_digest'},
    'profile': {'portfolio_id','profile_digest','parent_id'},'order':{'analysis_id','quantity'}, 'cancel':{'order_id'}, 'close':{'quantity','idempotency_key'},
          'analyze':{'symbol','market','timeframe','timeframes','data_mode','risk_portfolio',
                     'fixture_case','auto_paper','idempotency_key','profile_id'}}


def _hash(x):
    return sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


class DomainFailure(Exception):
    def __init__(self,status,code):self.status,self.code=status,code


class Replay:
    def __init__(self,audit):
        self.a,self.c,self.s=audit,audit.c,audit.s
        self.status='PASS';self.seq=0;self.meta=None;self.equity_stats={}
        self.s.executescript('''
            CREATE TABLE d_state(t TEXT,k TEXT,b TEXT,PRIMARY KEY(t,k));
            CREATE TABLE d_fact(t TEXT,k TEXT,PRIMARY KEY(t,k));
            CREATE TABLE d_command(k TEXT,digest TEXT,phase TEXT,PRIMARY KEY(k,digest));
            CREATE TABLE d_capacity(event TEXT,account TEXT,value TEXT,PRIMARY KEY(event,account));
            CREATE TABLE d_evaluation(event TEXT,owner TEXT,b TEXT,PRIMARY KEY(event,owner));
            CREATE TABLE d_decision(event TEXT,owner TEXT,kind TEXT,b TEXT,PRIMARY KEY(event,owner,kind));
            CREATE TABLE domain_proof(kind TEXT,k TEXT,value TEXT,PRIMARY KEY(kind,k));
            CREATE TABLE d_registered(t TEXT PRIMARY KEY);
            CREATE TABLE d_ack(k TEXT,digest TEXT,PRIMARY KEY(k,digest));
            CREATE TABLE d_request(k TEXT,digest TEXT,b TEXT,PRIMARY KEY(k,digest));
            CREATE TABLE d_control(k TEXT PRIMARY KEY,b TEXT);
            CREATE TABLE d_cash(event TEXT,account TEXT,seq INTEGER,delta TEXT,PRIMARY KEY(event,account,seq));
            CREATE TABLE d_position(event TEXT,owner TEXT,seq INTEGER,qty TEXT,basis TEXT,PRIMARY KEY(event,owner,seq));
            CREATE TABLE d_bar(event TEXT,owner TEXT,b TEXT,started INTEGER,entry_seen INTEGER,blocked INTEGER,PRIMARY KEY(event,owner));
            CREATE TABLE d_pending(k TEXT,digest TEXT,PRIMARY KEY(k,digest));
            CREATE INDEX d_active ON d_state(t,json_extract(b,'$.status'));



        ''')

    def check(self,condition,code,status='MISMATCH'):
        self.a.check(condition,code,'domain_events',self.seq,status=status)
        if not condition:
            priority=('PASS','INCOMPLETE','MISMATCH','CORRUPT','ERROR')
            if priority.index(status)>priority.index(self.status):self.status=status
        return bool(condition)

    def state(self,table,key):
        row=self.s.execute('SELECT b FROM d_state WHERE t=? AND k=?',(table,key)).fetchone()
        return json.loads(row[0]) if row else None

    def states(self,table):
        return (json.loads(r[0]) for r in self.s.execute('SELECT b FROM d_state WHERE t=?',(table,)))

    def number(self,x):
        from .paper_audit import _decimal
        return _decimal(x)

    def quantum(self,x):return x.quantize(Decimal('.00000001'))

    def floor(self,x,step):return (x/step).to_integral_value(rounding=ROUND_FLOOR)*step

    def proof(self,kind,key,value='verified'):
        self.s.execute('INSERT OR REPLACE INTO domain_proof VALUES(?,?,?)',(kind,key,value))

    def source(self,event):
        key=(event['source'] or {}).get('event_id')
        receipt=self.a.get('events',key) if key else None
        if receipt is None:raise DomainFailure('INCOMPLETE','domain_market_source')
        self.check(event['effective_at_ms']==receipt['close_time_ms'],'domain_effective_time')
        return key,receipt['market_event']

    def command(self,event):
        cmd=event['command']
        if not isinstance(cmd,dict):raise DomainFailure('CORRUPT','domain_command_structure')
        self.check(cmd['command_id']==_hash({'scope':cmd['scope'],'key':cmd['key']}),'domain_command_identity')
        return cmd

    def request(self,event):
        cmd=self.command(event);body=event['payload']['preimage'];kind=cmd['scope'].split(':',1)[0]
        if kind not in FIELDS or not isinstance(body,dict) or not set(body).issubset(FIELDS[kind]):
            raise DomainFailure('CORRUPT','domain_preimage_allowlist')
        self.check(_hash(body)==cmd['request_digest'],'domain_request_digest')
        self.s.execute('INSERT OR REPLACE INTO d_request VALUES(?,?,?)',(cmd['command_id'],cmd['request_digest'],json.dumps(body)))
        self.s.execute('INSERT OR REPLACE INTO d_command VALUES(?,?,?)',
                       (cmd['command_id'],cmd['request_digest'],event['event_type']))
        if event['event_type']=='command.requested':
            self.s.execute('INSERT OR IGNORE INTO d_pending VALUES(?,?)',(cmd['command_id'],cmd['request_digest']))
        else:self.s.execute('DELETE FROM d_pending WHERE k=? AND digest=?',(cmd['command_id'],cmd['request_digest']))
        if event['event_type']=='command.accepted':
            self.check(self.s.execute('SELECT 1 FROM d_ack WHERE k=? AND digest=?',(cmd['command_id'],cmd['request_digest'])).fetchone() is None,'domain_duplicate_ack')
            self.s.execute('INSERT OR IGNORE INTO d_ack VALUES(?,?)',(cmd['command_id'],cmd['request_digest']))
            row=self.c.execute('SELECT hash,body_hash FROM commands WHERE scope=? AND key=?',(cmd['scope'],cmd['key'])).fetchone()
            self.check(row==(cmd['request_digest'],event['payload']['response_hash']),'domain_command_ack')

    def ref(self,p):
        table=p['table']
        if table not in FACTS:raise DomainFailure('CORRUPT','domain_fact_table')
        if table=='commands':
            row=self.c.execute('SELECT body,body_hash FROM commands WHERE scope=? AND key=?',(p['scope'],p['key'])).fetchone()
            key=_hash({'scope':p['scope'],'key':p['key']})
        else:
            key=p['id'];row=self.c.execute(f'SELECT body,body_hash FROM {table} WHERE id=?',(key,)).fetchone()
        if row is None:raise DomainFailure('INCOMPLETE','domain_fact_source')
        body=json.loads(row[0])
        self.check(_hash(body)==row[1]==p['body_hash'],'domain_fact_hash')
        self.check(self.s.execute('SELECT 1 FROM d_fact WHERE t=? AND k=?',(table,key)).fetchone() is None,
                   'domain_duplicate_fact')
        self.s.execute('INSERT OR IGNORE INTO d_fact VALUES(?,?)',(table,key))
        if table=='notification_delivery_attempts':
            if type(body.get('schema_version')) is not int or body['schema_version']!=1:raise DomainFailure('INCOMPLETE','delivery_schema_version')
            if body.get('outcome') not in ('started','accepted','retryable','permanent','expired','preference_blocked','lease_expired','invalid_source'):raise DomainFailure('CORRUPT','delivery_outcome')
            self.check(type(body['attempt']) is int and 0<=body['attempt']<=5,'delivery_attempt_bound','CORRUPT')
            self.check(key==_hash({'notification':body['notification_id'],'attempt':body['attempt'],'outcome':body['outcome']}),'delivery_attempt_identity')
            row=self.c.execute('SELECT body,body_hash FROM notifications WHERE id=?',(body['notification_id'],)).fetchone()
            if row is None:raise DomainFailure('INCOMPLETE','delivery_outbox_source')
            notice=json.loads(row[0])
            self.check(_hash(notice)==row[1]==body['outbox_hash'] and body['data_mode']==notice['data_mode']==self.a.mode,'delivery_outbox_binding')
            self.check(body['idempotency_key']=='notification:'+body['notification_id'],'delivery_provider_key')
            self.check(isinstance(body['receipt_ref'],str) and len(body['receipt_ref'])<=128 and (body['outcome']!='accepted' or bool(body['receipt_ref'])),'delivery_receipt')
        if table=='notification_controls':
            required={'schema_version','owner_ref','portfolio_id','revision','enabled','categories','generation','revoked','lease_expires_at_ms','created_at_ms','parent_id','id','data_mode','recipient_id'}
            self.check(set(body)==required and body['schema_version']==1,'notification_control_schema','CORRUPT')
            self.check(self.c.execute('SELECT owner,portfolio,revision FROM notification_controls WHERE id=?',(key,)).fetchone()==(body['owner_ref'],body['portfolio_id'],body['revision']),'notification_control_columns')
            self.check(key==body['id']==_hash({'owner':body['owner_ref'],'account':body['portfolio_id'],'revision':body['revision']}),'notification_control_identity')
            self.check(body['data_mode']==self.a.mode and set(body['categories'])=={'analysis','source','risk','system'} and all(type(v) is bool for v in body['categories'].values()),'notification_control_categories','CORRUPT')
            expected=_hash({'owner':body['owner_ref'],'account':body['portfolio_id'],'generation':body['generation']}) if body['generation'] else None
            self.check(body['recipient_id']==expected,'notification_recipient_identity')
            if body['parent_id']:
                p=self.c.execute('SELECT body FROM notification_controls WHERE id=?',(body['parent_id'],)).fetchone()
                self.check(p is not None,'notification_control_parent')
                if p:
                    parent=json.loads(p[0]);self.check((parent['owner_ref'],parent['portfolio_id'],parent['revision']+1)==(body['owner_ref'],body['portfolio_id'],body['revision']),'notification_control_lineage')
            else:self.check(body['revision']==1,'notification_control_genesis')
        if table=='equity_snapshots':self.equity_point(key,body)
        if table=='strategy_profiles':
            columns=self.c.execute('SELECT portfolio,group_id,revision FROM strategy_profiles WHERE id=?',(key,)).fetchone()
            self.check(columns==(body['portfolio_id'],body['group_id'],body['revision']),'domain_profile_columns')
            parent=None
            if body['parent_id'] is not None:
                parent_row=self.c.execute('SELECT body FROM strategy_profiles WHERE id=?',(body['parent_id'],)).fetchone()
                if parent_row is None:raise DomainFailure('INCOMPLETE','domain_profile_parent')
                parent=json.loads(parent_row[0])
                self.check(parent['portfolio_id']==body['portfolio_id'] and parent['group_id']==body['group_id'] and parent['revision']+1==body['revision'],'domain_profile_lineage')
            else:self.check(body['revision']==1 and body['group_id']==key,'domain_profile_genesis')
            config={**body['selection'],'schema_version':1,'revision':body['revision'],'parent_id':parent['content_id'] if parent else None,'strategy_versions':body['strategy_versions']}
            for field in ('strategy_ids','required_methods','allowed_regimes'):config[field]=sorted(config[field])
            self.check(_hash(config)==body['content_id'],'domain_profile_content')
        return table,key,body

    def equity_point(self,key,b):
        if b.get('kind')=='coverage':
            self.check(b.get('schema_version')==1 and b.get('backfilled') is False,'equity_coverage_boundary')
            return
        if b.get('schema_version')!=1:raise DomainFailure('INCOMPLETE','equity_version')
        account=b['portfolio_id'];number=self.number;zero=Decimal(0)
        columns=self.c.execute('SELECT portfolio,sequence,recorded_ms FROM equity_snapshots WHERE id=?',(key,)).fetchone()
        self.check(columns==(account,b['sequence'],b['recorded_at_ms']),'equity_columns')
        self.check(_hash({'portfolio':account,'source':b['source'],'equity_version':1})==key==b['snapshot_id'],'equity_identity')
        src=b['source']
        if src['kind']=='event':
            receipt=self.a.get('events',src['event_id'])
            self.check(receipt is not None and receipt['close_time_ms']==b['effective_at_ms'],'equity_source')
        else:
            row=self.c.execute('SELECT body FROM commands WHERE scope=? AND key=?',(src['scope'],src['key'])).fetchone()
            self.check(row is not None and src['scope'].split(':')[1]==account,'equity_command_source')
        state=self.state('accounts',account)
        positions=[p for p in self.states('positions') if p['portfolio_id']==account]
        active=[p for p in positions if number(p['quantity'])>0]
        pending=[o for o in self.states('orders') if o['portfolio_id']==account and o['status'] in ('pending','partially_filled')]
        reserved=sum((number(o['remaining_quantity'])*number(o['reservation_per_unit']) for o in pending),zero)
        cash=number(state['cash_quote']);marked=sum((number(p['quantity'])*number(p['mark_price']) for p in active),zero)
        basis=sum((number(p['cost_basis_quote']) for p in active),zero)
        self.check(number(b['cash_quote'])==cash and number(b['reserved_cash_quote'])==self.quantum(reserved) and number(b['available_cash_quote'])==self.quantum(cash-reserved),'equity_cash_reserves')
        expected_marks={p['position_id']:p for p in active}
        self.check({p['position_id'] for p in b['marks']}==set(expected_marks),'equity_holdings')
        quality='complete'
        for m in b['marks']:
            p=expected_marks.get(m['position_id'])
            self.check(p is not None and all(m[k]==p[k] for k in ('order_id','symbol','quantity','cost_basis_quote','mark_price','mark_time_ms','status')),'equity_position_state')
            receipt=self.a.get('events',m['event_id']) if m['event_id'] else None
            valid=bool(receipt and receipt['market_event']['symbol']==m['symbol'] and receipt['close_time_ms']==m['mark_time_ms'] and number(receipt['market_event']['close'])==number(m['mark_price']) and 0<=m['mark_time_ms']<=b['recorded_at_ms'])
            if not valid:quality='incomplete'
            elif b['recorded_at_ms']-m['mark_time_ms']>60000 and quality=='complete':quality='stale'
        self.check(b['quality_status']==quality and b['chart_eligible']==(quality=='complete'),'equity_mark_quality')
        if quality!='incomplete':
            self.check(number(b['equity_quote'])==self.quantum(cash+marked) and number(b['unrealized_pnl_quote'])==self.quantum(marked-basis),'equity_valuation')
        else:self.check(b['equity_quote'] is None and b['unrealized_pnl_quote'] is None,'equity_missing_marks')
        seen=self.s.execute("SELECT COALESCE(MAX(r.n),0) FROM records r JOIN d_fact f ON f.t=r.t AND f.k=r.k WHERE r.t='transactions'").fetchone()[0]
        self.check(b['transaction_watermark']==max(seen,self.meta['legacy_cutoffs'].get('transactions',0)),'equity_journal_prefix')
        self.check(b['open_positions']==len(active) and b['closed_positions']==sum(p['status']=='closed' for p in positions) and b['ambiguous_positions']==sum(bool(p.get('ambiguity_seen')) for p in positions) and b['pending_orders']==len(pending),'equity_position_counts')
        self.check(b['reservations']==sorted([{k:o[k] for k in ('order_id','status','remaining_quantity','reservation_per_unit')} for o in pending],key=lambda o:o['order_id']),'equity_reservation_state')
        tx=[v for _,_,v in self.a.rows('transactions','AND account=? AND n<=?',(account,b['transaction_watermark']))]
        self.check(number(b['realized_pnl_quote'])==self.quantum(sum((number(t['realized_pnl_quote']) for t in tx),zero)) and number(b['fees_quote'])==self.quantum(sum((number(t['fee_quote']) for t in tx),zero)),'equity_journal_totals')
        groups={}
        for t in tx:
            order=self.a.get('orders',t['order_id']);analysis=self.a.get('analyses',order['analysis_id']) if order else None
            name=analysis.get('router',{}).get('strategy_id') if analysis else None
            values=groups.setdefault(name or 'unknown',[zero,zero,0]);values[0]+=number(t['realized_pnl_quote']);values[1]+=number(t['fee_quote']);values[2]+=1
        def fmt(v):return format(self.quantum(v).copy_abs() if v==0 else self.quantum(v),'f')
        self.check(b['strategy_results']==[{'strategy_id':k,'realized_pnl_quote':fmt(v[0]),'fees_quote':fmt(v[1]),'transaction_count':v[2]} for k,v in sorted(groups.items())],'equity_strategy_totals')
        if account not in self.equity_stats:
            cutoff=self.meta['legacy_cutoffs'].get('equity_snapshots',0)
            old=self.c.execute('SELECT body,body_hash FROM equity_snapshots WHERE portfolio=? AND rowid<=? ORDER BY sequence DESC LIMIT 1',(account,cutoff)).fetchone()
            if old:
                prior=json.loads(old[0]);self.check(_hash(prior)==old[1],'equity_legacy_hash','CORRUPT')
                self.equity_stats[account]=(number(prior['peak_equity_quote']) if prior['peak_equity_quote'] is not None else None,number(prior['maximum_drawdown_quote']),number(prior['maximum_drawdown_pct']),prior['sequence'])
                self.check(False,'equity_drawdown_legacy_prefix','INCOMPLETE')
        peak,dd,pct,seq=self.equity_stats.get(account,(None,zero,zero,0))
        self.check(b['sequence']==seq+1,'equity_sequence')
        if quality=='complete':
            value=self.quantum(cash+marked);peak=max(peak,value) if peak is not None else value
            dd=max(dd,peak-value);pct=max(pct,(peak-value)/peak*100 if peak>0 else zero)
        self.check((number(b['peak_equity_quote']) if b['peak_equity_quote'] is not None else None)==(self.quantum(peak) if peak is not None else None) and number(b['maximum_drawdown_quote'])==self.quantum(dd) and number(b['maximum_drawdown_pct'])==self.quantum(pct),'equity_drawdown')
        self.equity_stats[account]=(self.quantum(peak) if peak is not None else None,self.quantum(dd),self.quantum(pct),b['sequence'])

    def capacity(self,event,account):
        row=self.s.execute('SELECT value FROM d_capacity WHERE event=? AND account=?',(event,account)).fetchone()
        if row is None:raise DomainFailure('INCOMPLETE','domain_capacity_source')
        return self.number(row[0])

    def state_change(self,event):
        p=event['payload'];table,key=p['table'],p['id']
        if table not in MUTABLE:raise DomainFailure('CORRUPT','domain_state_table')
        old=self.state(table,key)
        self.check((_hash(old) if old is not None else None)==p['before_hash'],'domain_before_hash')
        self.check(all(old is not None and k in old and old[k]==v for k,v in p['before'].items()),'domain_before_fields')
        new=dict(old or {})
        for k in p['before']:
            if k not in p['after']:new.pop(k,None)
        new.update(p['after'])
        self.check(_hash(new)==p['after_hash'],'domain_after_hash')
        account=new.get('portfolio_id')
        if account is not None:self.check(account==event['portfolio_id'] and account in ('AUTO','MANUAL'),'domain_account')
        cmd=event['command']
        changed=set(p['before'])|set(p['after'])
        source_id=(event['source'] or {}).get('event_id')
        if source_id:self.source(event)
        if old is not None and table=='orders':
            self.check(changed.issubset({'status','remaining_quantity'}),'domain_order_immutable_fields')
        if old is not None and table=='accounts':
            self.check(changed.issubset({'cash_quote','paused'}),'domain_account_immutable_fields')
            delta=self.number(new['cash_quote'])-self.number(old['cash_quote'])
            if delta:
                self.check(source_id is not None,'domain_cash_source')
                self.s.execute('INSERT INTO d_cash VALUES(?,?,?,?)',(source_id,key,self.seq,str(delta)))
        if table=='positions':
            if cmd and cmd['scope'].startswith('close:'):
                self.check(changed.issubset({'pending_closes'}),'domain_close_mutation')
            else:self.check(source_id is not None,'domain_position_source')
            if old is not None:
                self.check(not changed.intersection({'portfolio_id','order_id','position_id','symbol','data_mode','invalidation','target_1','target_2'}),'domain_position_immutable_fields')
            quantity=self.number(new['quantity'])-self.number(old['quantity'] if old else '0')
            basis=self.number(new['cost_basis_quote'])-self.number(old['cost_basis_quote'] if old else '0')
            if quantity or basis:self.s.execute('INSERT INTO d_position VALUES(?,?,?,?,?)',(source_id,key,self.seq,str(quantity),str(basis)))
        if cmd and table in ('accounts','orders','positions'):
            phase=self.s.execute('SELECT phase FROM d_command WHERE k=? AND digest=?',(cmd['command_id'],cmd['request_digest'])).fetchone()
            self.check(phase is None or phase[0]!='command.replayed','domain_replayed_mutation')
        if table=='orders':
            if old is None:
                account_state=self.state('accounts',account)
                self.check(account_state is not None and not account_state['paused'],'domain_entry_while_paused')
                self.check(cmd is not None and cmd['scope']=='order:'+account,'domain_order_command')
            elif old['status']!=new['status']:
                status=new['status'];valid=False
                if status=='cancelled':
                    req=self.s.execute('SELECT b FROM d_request WHERE k=? AND digest=?',(cmd['command_id'],cmd['request_digest'])).fetchone() if cmd else None
                    valid=bool(cmd and cmd['scope']=='cancel:'+account and req and json.loads(req[0]).get('order_id')==key and old['status'] in ('pending','partially_filled'))
                elif status in ('expired','expired_remainder'):
                    _,bar=self.source(event);valid=bar['close_time_ms']>old['expires_at_ms']
                elif status=='cancelled_gap':
                    _,bar=self.source(event);valid=self.number(bar['open'])<=self.number(old['levels']['invalidation'])
                elif status=='cancelled_remainder':
                    valid=bool(cmd and cmd['scope']=='close:'+account+':'+key)
                    if (event['source'] or {}).get('event_id'):
                        source_id=(event['source'] or {})['event_id']
                        evaluation=self.s.execute('SELECT b FROM d_evaluation WHERE event=? AND owner=?',(source_id,key)).fetchone()
                        valid=bool(evaluation and (json.loads(evaluation[0])['stop'] or json.loads(evaluation[0])['target']))
                        if not valid:
                            position=self.state('positions',key)
                            decisions=self.s.execute('SELECT kind,b FROM d_decision WHERE event=? AND owner=?',(source_id,key))
                            valid=bool(position and any(kind.startswith('manual_close:') and self.number(json.loads(raw)['quantity'])==self.number(position['quantity']) for kind,raw in decisions))
                if status in ('cancelled','cancelled_gap','cancelled_remainder','expired','expired_remainder'):
                    if self.check(valid and self.number(new['remaining_quantity'])==0,'domain_cancellation'):
                        self.proof('cancel',key)
                if old['status'] not in ('pending','partially_filled'):
                    self.check(new['status'] not in ('pending','partially_filled'),'domain_terminal_reactivated')
        if table=='accounts' and old and old['paused']!=new['paused']:
            source=event['source'] or {}
            if source.get('event_id'):
                self.check(new['paused'] is True,'domain_automatic_resume')
            else:
                request=self.s.execute('SELECT b FROM d_control WHERE k=?',(_hash(source),)).fetchone()
                self.check(source.get('control')=='account_pause' and source.get('portfolio_id')==key and request is not None and json.loads(request[0]).get('paused')==new['paused'],'domain_pause_source')
                if not new['paused']:
                    self.check(not any(p['portfolio_id']==key and self.number(p['quantity'])>0 and
                        (p['status']=='ambiguous' or p.get('stop_triggered')) for p in self.states('positions')),
                        'domain_unsafe_resume')
        if table=='analysis_tracking' and (old is None or old['enabled']!=new['enabled']):
            source=event['source'] or {}
            self.check(source.get('control')==('follow_start' if old is None else 'follow_change'),'domain_follow_source')
        if table=='scanner_state' and old and old['paused']!=new['paused']:
            self.check((event['source'] or {}).get('control')=='scanner_pause','domain_scanner_source')
        self.s.execute('INSERT OR REPLACE INTO d_state VALUES(?,?,?)',(table,key,json.dumps(new)))

    def live_orders(self):
        seen=set()
        for (raw,) in self.s.execute("SELECT b FROM d_state WHERE t='orders' AND json_extract(b,'$.status') IN ('pending','partially_filled')"):
            order=json.loads(raw);seen.add(order['order_id']);yield order
        for (raw,) in self.s.execute("SELECT b FROM d_state WHERE t='positions' AND json_extract(b,'$.status') IN ('open','ambiguous','exit_pending')"):
            position=json.loads(raw)
            if position['order_id'] not in seen:
                order=self.state('orders',position['order_id'])
                if order is not None:yield order

    def market(self,event):
        key,bar=self.source(event)
        self.check(event['payload']['symbol']==bar['symbol'],'domain_market_instrument')
        if self.s.execute("SELECT 1 FROM d_fact WHERE t='events' AND k=?",(key,)).fetchone():return
        row=self.c.execute('SELECT rowid FROM events WHERE id=?',(key,)).fetchone()
        if row and row[0]<=self.meta['legacy_cutoffs'].get('events',0):return
        fractions={account:[] for account in ('AUTO','MANUAL')}
        for order in self.live_orders():
            if order['symbol']!=bar['symbol']:continue
            account=order['portfolio_id'];fractions[account].append(self.number(order['participation_fraction']))
            if bar['open_time_ms']>=order['created_at_ms']:
                self.s.execute('INSERT OR IGNORE INTO d_bar VALUES(?,?,?,0,0,0)',(key,order['order_id'],'{}'))
        for account,values in fractions.items():
            if values:self.s.execute('INSERT OR IGNORE INTO d_capacity VALUES(?,?,?)',(key,account,str(self.number(bar['volume'])*min(values))))

    def bar_started(self,event):
        key,_=self.source(event);owner=event['payload']['order_id']
        row=self.s.execute('SELECT started FROM d_bar WHERE event=? AND owner=?',(key,owner)).fetchone()
        self.check(row is not None and row[0]==0,'domain_order_bar_coverage')
        order=self.state('orders',owner);position=self.state('positions',owner)
        if order is None:raise DomainFailure('INCOMPLETE','domain_order_source')
        body={'order':order,'quantity':(position or {}).get('quantity','0'),'status':(position or {}).get('status'),
              'paused':self.state('accounts',order['portfolio_id'])['paused']}
        self.s.execute('UPDATE d_bar SET b=?,started=1 WHERE event=? AND owner=?',(json.dumps(body),key,owner))

    def evaluate(self,event):
        p=event['payload'];key,bar=self.source(event);oid=p['order_id']
        order=self.state('orders',oid);position=self.state('positions',oid)
        if order is None or position is None:raise DomainFailure('INCOMPLETE','domain_decision_position')
        self.check(event['portfolio_id']==order['portfolio_id']==position['portfolio_id'],'domain_decision_account')
        self.check(all(position.get(k)==v for k,v in p['before'].items()),'domain_decision_before')
        self.check(bool(position.get('stop_triggered'))==p['prior_stop'],'domain_prior_stop')
        self.check(p.get('tp1_remaining')==position.get('tp1_remaining'),'domain_tp1_prior')
        stop=p['prior_stop'] or self.number(bar['low'])<=self.number(position['invalidation'])
        target=self.number(bar['high'])>=self.number(position['target_2'] if position['tp1_done'] else position['target_1'])
        if stop and (p['prior_stop'] or self.number(bar['open'])<=self.number(position['invalidation'])):target=False
        self.check(stop==p['stop'] and target==p['target'],'domain_protective_condition')
        self.check(self.number(p['available'])==self.capacity(key,order['portfolio_id']),'domain_decision_capacity')
        p=dict(p,seen_tp1=None)
        self.s.execute('INSERT OR REPLACE INTO d_evaluation VALUES(?,?,?)',(key,oid,json.dumps(p)))

    def decision(self,event):
        p=event['payload'];key,bar=self.source(event);oid=p['order_id'];order=self.state('orders',oid)
        if order is None:raise DomainFailure('INCOMPLETE','domain_decision_order')
        account=order['portfolio_id'];step=self.number(order['quantity_step']);cap=self.capacity(key,account)
        self.check(event['portfolio_id']==account,'domain_decision_account')
        self.check(p['available'] is not None and self.number(p['available'])==cap,'domain_decision_capacity')
        qty=self.number(p['quantity']);expected=Decimal(0);kind='entry'
        if event['event_type']=='entry.decision':self.s.execute('UPDATE d_bar SET entry_seen=1 WHERE event=? AND owner=?',(key,oid))
        if event['event_type']=='entry.decision':
            remaining=self.number(order['remaining_quantity'])
            self.check(order['status'] in ('pending','partially_filled') and
                       not self.state('accounts',account)['paused'],'domain_entry_gate')
            z=order['levels']
            self.check(self.number(bar['open'])>self.number(z['invalidation']) and
                       self.number(bar['low'])<=self.number(z['entry_high']) and self.number(bar['high'])>=self.number(z['entry_low']) and
                       bar['close_time_ms']<=order['expires_at_ms'],'domain_entry_bar')
            expected=self.floor(min(remaining,cap),step)
            price=self.quantum(self.number(z['entry_high'])*(1+self.number(order['adverse_rate'])))
        else:
            kind=p['kind'];position=self.state('positions',oid)
            self.check(position is not None,'domain_exit_position')
            current=self.number(position['quantity']);before=p['before']
            self.check(self.number(before['quantity'])==current,'domain_exit_quantity_before')
            if kind.startswith('manual_close:'):
                cid=kind.split(':',1)[1]
                request=next((x for x in position.get('pending_closes',[]) if x['close_request_id']==cid),None)
                if request is None:raise DomainFailure('INCOMPLETE','domain_manual_source')
                self.check(bar['open_time_ms']>=request['created_at_ms'],'domain_manual_time')
                # Prior fills in this bar can precede the final pending-close patch.
                used=Decimal(0)
                for _,_,tx in self.a.rows('transactions','AND owner=? AND event=?',(oid,key)):
                    if tx['kind']==kind and self.s.execute('SELECT 1 FROM d_fact WHERE t=? AND k=?',('transactions',tx['transaction_id'])).fetchone():
                        used+=self.number(tx['quantity'])
                expected=self.floor(min(current,self.number(request['remaining_quantity'])-used,cap),step)
                base=self.number(bar['open'])
            else:
                row=self.s.execute('SELECT b FROM d_evaluation WHERE event=? AND owner=?',(key,oid)).fetchone()
                if row is None:raise DomainFailure('INCOMPLETE','domain_protective_evidence')
                e=json.loads(row[0]);self.check(not (e['stop'] and e['target']),'domain_ambiguous_exit')
                if kind=='stop_loss':
                    self.check(e['stop'] and not e['target'],'domain_stop_condition')
                    base=self.number(bar['open']) if e['prior_stop'] else min(self.number(bar['open']),self.number(position['invalidation']))
                    expected=self.floor(min(current,cap),step)
                elif kind=='take_profit_1':
                    self.check(e['target'] and not e['stop'] and not e['before']['tp1_done'],'domain_tp1_condition')
                    desired=self.number(e['tp1_remaining']) if e['tp1_remaining'] is not None else self.floor(self.number(e['before']['quantity'])/2,step)
                    if desired<=0:desired=current
                    desired=min(desired,current)
                    expected=self.floor(min(desired,cap),step);base=self.number(position['target_1'])
                    e['seen_tp1']={'desired':str(desired),'filled':str(qty)}
                    self.s.execute('UPDATE d_evaluation SET b=? WHERE event=? AND owner=?',(json.dumps(e),key,oid))
                elif kind=='take_profit_2':
                    done=e['before']['tp1_done'] or (e['seen_tp1'] and self.number(e['seen_tp1']['desired'])==self.number(e['seen_tp1']['filled']))
                    self.check(bool(done) and not e['stop'] and self.number(bar['high'])>=self.number(position['target_2']),'domain_tp2_condition')
                    expected=self.floor(min(current,cap),step);base=self.number(position['target_2'])
                else:raise DomainFailure('INCOMPLETE','domain_exit_kind')
            self.check(self.number(p['base_price'])==base,'domain_exit_base')
            price=self.quantum(base*(1-self.number(order['adverse_rate'])))
        self.check(qty==expected and qty>=0,'domain_decision_quantity')
        self.s.execute('INSERT OR REPLACE INTO d_decision VALUES(?,?,?,?)',(key,oid,kind,json.dumps({'quantity':str(expected),'price':str(price)})))

    def financial(self,event,key,t):
        source,bar=self.source(event);owner=t['order_id'];kind=t['kind'];account=t['portfolio_id']
        self.check(source==t['event_id'] and event['portfolio_id']==account,'domain_financial_source')
        row=self.s.execute('SELECT b FROM d_decision WHERE event=? AND owner=? AND kind=?',(source,owner,kind)).fetchone()
        if row is None:raise DomainFailure('INCOMPLETE','domain_financial_decision')
        d=json.loads(row[0]);valid=self.check(self.number(t['quantity'])==self.number(d['quantity']) and
                                          self.number(t['price'])==self.number(d['price']),'domain_financial_decision_match')
        if valid and kind=='stop_loss':self.proof('stop',key,d['price'])
        self.s.execute('DELETE FROM d_decision WHERE event=? AND owner=? AND kind=?',(source,owner,kind))
        cash=self.s.execute('SELECT seq,delta FROM d_cash WHERE event=? AND account=? ORDER BY seq LIMIT 1',(source,account)).fetchone()
        self.check(cash is not None and self.number(cash[1])==self.number(t['cash_delta_quote']),'domain_cash_match')
        if cash:self.s.execute('DELETE FROM d_cash WHERE event=? AND account=? AND seq=?',(source,account,cash[0]))
        change=self.s.execute('SELECT seq,qty,basis FROM d_position WHERE event=? AND owner=? ORDER BY seq LIMIT 1',(source,owner)).fetchone()
        expected_q=self.number(t['quantity'])*(1 if kind=='entry' else -1)
        expected_basis=-self.number(t['cash_delta_quote']) if kind=='entry' else self.number(t['realized_pnl_quote'])-self.number(t['cash_delta_quote'])
        self.check(change is not None and self.number(change[1])==expected_q and self.number(change[2])==expected_basis,'domain_position_financial_match')
        if change:self.s.execute('DELETE FROM d_position WHERE event=? AND owner=? AND seq=?',(source,owner,change[0]))
        cap=self.capacity(source,account)-self.number(t['quantity'])
        self.check(cap>=0,'domain_liquidity')
        self.s.execute('UPDATE d_capacity SET value=? WHERE event=? AND account=?',(str(cap),source,account))

    def finalize_market(self,event):
        key,bar=self.source(event)
        self.check(self.s.execute('SELECT 1 FROM d_cash WHERE event=?',(key,)).fetchone() is None,'domain_cash_unjournaled')
        self.check(self.s.execute('SELECT 1 FROM d_position WHERE event=?',(key,)).fetchone() is None,'domain_position_unjournaled')
        for owner,raw,started,entry_seen,blocked in self.s.execute('SELECT owner,b,started,entry_seen,blocked FROM d_bar WHERE event=?',(key,)):
            if not self.check(started==1,'domain_order_bar_coverage'):continue
            initial=json.loads(raw);order=initial['order'];q=self.number(initial['quantity'])
            manual=sum((self.number(t['quantity']) for _,_,t in self.a.rows('transactions','AND owner=? AND event=?',(owner,key)) if t['kind'].startswith('manual_close:')),Decimal(0))
            evaluation=self.s.execute('SELECT b FROM d_evaluation WHERE event=? AND owner=?',(key,owner)).fetchone()
            if q>manual:
                if initial['status']=='ambiguous':self.check(blocked==1,'domain_order_evaluation_missing','INCOMPLETE')
                else:self.check(evaluation is not None,'domain_order_evaluation_missing','INCOMPLETE')
            refill=(q==0 or (q>manual and evaluation is not None and not json.loads(evaluation[0])['stop'] and not json.loads(evaluation[0])['target'] and order['status']=='partially_filled'))
            z=order['levels']
            touched=self.number(bar['low'])<=self.number(z['entry_high']) and self.number(bar['high'])>=self.number(z['entry_low'])
            if refill and order['status'] in ('pending','partially_filled') and not initial['paused'] and bar['close_time_ms']<=order['expires_at_ms'] and touched and self.number(bar['open'])>self.number(z['invalidation']):
                self.check(entry_seen==1,'domain_entry_evaluation_missing','INCOMPLETE')
        for owner,raw in self.s.execute('SELECT owner,b FROM d_evaluation WHERE event=?',(key,)):
            e=json.loads(raw);position=self.state('positions',owner);order=self.state('orders',owner)
            if position is None or order is None:raise DomainFailure('INCOMPLETE','domain_final_state')
            before=e['before'];q=self.number(before['quantity']);cap=self.number(e['available'])
            step=self.number(order['quantity_step'])
            if e['stop'] and e['target']:
                self.check(position['status']=='ambiguous' and position.get('ambiguity_seen') is True,'domain_ambiguity_state')
                self.check(self.state('accounts',order['portfolio_id'])['paused'] is True,'domain_ambiguity_pause')
            elif e['stop']:
                closed=self.floor(min(q,cap),step)
                self.check(position.get('stop_triggered') is True and self.number(position['quantity'])==q-closed,'domain_sticky_stop')
                if q>closed:
                    self.check(position['status']=='exit_pending' and self.state('accounts',order['portfolio_id'])['paused'] is True,'domain_stop_pending')
            elif e['target']:
                expected_done=before['tp1_done'];used=Decimal(0)
                if not expected_done:
                    desired=self.number(e['tp1_remaining']) if e['tp1_remaining'] is not None else self.floor(q/2,step)
                    if desired<=0:desired=q
                    desired=min(desired,q);used=self.floor(min(desired,cap),step);expected_done=desired==used
                    self.check(self.number(position['tp1_remaining'])==desired-used and position['tp1_done']==expected_done,'domain_tp1_transition')
                second=Decimal(0)
                if expected_done and q>used and self.number(bar['high'])>=self.number(before['target_2']):
                    second=self.floor(min(q-used,cap-used),step)
                self.check(self.number(position['quantity'])==q-used-second,'domain_target_quantity')
            else:
                entered=sum((self.number(tx['quantity']) for _,_,tx in self.a.rows('transactions','AND owner=? AND event=?',(owner,key)) if tx['kind']=='entry'),Decimal(0))
                self.check(self.number(position['quantity'])==q+entered and position['tp1_done']==before['tp1_done'] and
                           position.get('tp1_remaining')==e['tp1_remaining'],'domain_no_protective_change')

    def verify(self):
        meta=self.c.execute('SELECT version,body,body_hash FROM domain_meta').fetchall()
        if len(meta)!=1 or meta[0][0]!=1:raise DomainFailure('INCOMPLETE','domain_version')
        self.meta=json.loads(meta[0][1])
        if type(self.meta.get('schema_version')) is not int:
            raise DomainFailure('CORRUPT','domain_version_type')
        if self.meta.get('schema_version')!=1 or self.meta.get('coverage') not in ('genesis','legacy_boundary'):
            raise DomainFailure('INCOMPLETE','domain_version')
        self.check(_hash(self.meta)==meta[0][2],'domain_metadata_hash','CORRUPT')
        registry={r[0] for r in self.c.execute('SELECT name FROM domain_tables')}
        if not self.check(set(('accounts','orders','positions','transactions','events','commands','analyses')).issubset(registry)
                   and registry.issubset(MUTABLE|FACTS),'domain_registry','CORRUPT'):
            raise DomainFailure('CORRUPT','domain_registry_stopped')
        objects={r[0]:(r[1],r[2] or '') for r in self.c.execute('SELECT name,type,sql FROM sqlite_master')}
        for table in registry:
            self.check(objects.get(table,('',))[0]=='table','domain_registered_table','CORRUPT')
            for action in ('insert','delete', *(['update'] if table in MUTABLE else [])):
                sql=objects.get('domain_capture_'+table+'_'+action,('',''))[1].upper().replace(' ','')
                self.check(('RAISE(ABORT' if action=='delete' else 'DOMAIN_CAPTURE(') in sql,'domain_capture_guard','CORRUPT')
        for table in ('domain_events','domain_meta','domain_tables','domain_head'):
            for action in ('insert','update','delete'):
                sql=objects.get(table+'_'+action,('',''))[1].upper().replace(' ','')
                self.check(('DOMAIN_INTERNAL(' if action=='insert' or table=='domain_head' else 'RAISE(ABORT') in sql,
                           'domain_immutable_guard','CORRUPT')
        for name in ('domain_account_sequence','domain_source_sequence'):
            expected=['portfolio_id','sequence'] if name=='domain_account_sequence' else ['source_id','sequence']
            self.check(objects.get(name,('',))[0]=='index' and [r[2] for r in self.c.execute(f'PRAGMA index_info({name})')]==expected,'domain_index','CORRUPT')
        if self.c.execute('SELECT 1 FROM domain_events WHERE length(CAST(body AS BLOB))>? LIMIT 1',(self.a.max_body_bytes,)).fetchone():
            raise DomainFailure('INCOMPLETE','domain_body_budget')
        previous=ZERO
        for seq,eid,checksum,account,source,raw in self.c.execute('SELECT * FROM domain_events ORDER BY sequence'):
            self.seq+=1;self.a.total+=1;self.a.bytes_read+=len(raw.encode())
            if self.a.total>self.a.max_records or self.a.bytes_read>self.a.max_total_body_bytes:raise DomainFailure('INCOMPLETE','domain_record_budget')
            e=json.loads(raw)
            if type(e['schema_version']) is not int or type(e['sequence']) is not int:
                raise DomainFailure('CORRUPT','domain_version_type')
            if e['schema_version']!=1:raise DomainFailure('INCOMPLETE','domain_version')
            if not self.check(seq==self.seq==e['sequence'] and e['previous_event_hash']==previous and
                              _hash(e)==checksum and eid==_hash({'schema_version':1,'sequence':seq,'event_hash':checksum}),
                              'domain_chain','CORRUPT'):
                raise DomainFailure('CORRUPT','domain_chain_stopped')
            previous=checksum
            self.check(account==e['portfolio_id'] and source==(e['source'] or {}).get('event_id'),'domain_columns','CORRUPT')
            self.check(type(e['recorded_at_ms']) is int and e['recorded_at_ms']>=0 and
                       type(e['effective_at_ms']) is int and e['effective_at_ms']>=0,'domain_timestamp','CORRUPT')
            kind=e['event_type']
            if kind not in KINDS:raise DomainFailure('INCOMPLETE','domain_event_type')
            p=e['payload']
            if kind=='coverage.started':self.check(seq==1 and p==self.meta,'domain_coverage_start','CORRUPT')
            elif kind=='schema.table_registered':self.s.execute('INSERT INTO d_registered VALUES(?)',(p['table'],))
            elif kind=='state.baseline':
                self.check(_hash(p['body'])==p['body_hash'],'domain_baseline_hash','CORRUPT')
                self.check(p['body'].get('portfolio_id')==e['portfolio_id'],'domain_baseline_account')
                self.s.execute('INSERT INTO d_state VALUES(?,?,?)',(p['table'],p['id'],json.dumps(p['body'])))
            elif kind=='state.changed':self.state_change(e)
            elif kind=='record.created':
                table,key,body=self.ref(p)
                if table=='transactions':self.financial(e,key,body)
                elif table=='events':self.finalize_market(e)
            elif kind in ('command.requested','command.accepted','command.rejected'):
                self.request(e)
            elif kind=='command.replayed':
                cmd=self.command(e)
                row=self.c.execute('SELECT hash,body_hash FROM commands WHERE scope=? AND key=?',(cmd['scope'],cmd['key'])).fetchone()
                self.check(row==(cmd['request_digest'],p['response_hash']),'domain_replay_ack')
                self.s.execute('INSERT OR REPLACE INTO d_command VALUES(?,?,?)',(cmd['command_id'],cmd['request_digest'],kind))
                self.s.execute('DELETE FROM d_pending WHERE k=? AND digest=?',(cmd['command_id'],cmd['request_digest']))
            elif kind=='control.requested':self.s.execute('INSERT OR REPLACE INTO d_control VALUES(?,?)',(_hash(e['source']),json.dumps(p)))
            elif kind=='market.received':self.market(e)
            elif kind=='order.bar_started':self.bar_started(e)
            elif kind=='protective.evaluated':self.evaluate(e)
            elif kind in ('entry.decision','exit.decision'):self.decision(e)
            elif kind=='protective.blocked':
                position=self.state('positions',p['order_id'])
                self.check(position is not None and position['status']=='ambiguous','domain_ambiguity_source')
                self.s.execute('UPDATE d_bar SET blocked=1 WHERE event=? AND owner=?',((e['source'] or {}).get('event_id'),p['order_id']))
        self.a.report['records']['domain_events']=self.seq
        self.check(self.c.execute('SELECT sequence,event_hash FROM domain_head WHERE id=1').fetchone()==(self.seq,previous),'domain_head','CORRUPT')
        self.check({r[0] for r in self.s.execute('SELECT t FROM d_registered')}==registry,'domain_registry_coverage','CORRUPT')
        for table in registry:
            if table in MUTABLE:
                actual=0
                for key,raw,h in self.c.execute(f'SELECT id,body,body_hash FROM {table} ORDER BY rowid'):
                    actual+=1;state=self.state(table,key)
                    self.check(state is not None and _hash(state)==h==_hash(json.loads(raw)),'domain_projection')
                self.check(actual==self.s.execute('SELECT count(*) FROM d_state WHERE t=?',(table,)).fetchone()[0],'domain_projection_count')
            else:
                cutoff=self.meta['legacy_cutoffs'].get(table,0)
                for row in self.c.execute(f'SELECT * FROM {table} WHERE rowid>?',(cutoff,)):
                    key=_hash({'scope':row[0],'key':row[1]}) if table=='commands' else row[0]
                    self.check(self.s.execute('SELECT 1 FROM d_fact WHERE t=? AND k=?',(table,key)).fetchone() is not None,'domain_fact_coverage')
                    if table=='commands':
                        self.check(self.s.execute('SELECT 1 FROM d_ack WHERE k=? AND digest=?',(key,row[2])).fetchone() is not None,'domain_ack_coverage')
        self.check(self.s.execute('SELECT 1 FROM d_pending LIMIT 1').fetchone() is None,'domain_command_outcome_missing','INCOMPLETE')
        if self.meta['coverage']!='genesis':self.check(False,'domain_legacy_history','INCOMPLETE')
        return {'status':self.status,'coverage':self.meta['coverage'],'events':self.seq,
                'scope':'chain_state_commands_and_recorded_execution_decisions'}


def verify(audit, *, require=False):
    columns={r[1] for r in audit.c.execute('PRAGMA table_info(product_meta)')}
    version=audit.c.execute('SELECT domain_version FROM product_meta').fetchone()[0] if 'domain_version' in columns else 0
    present=audit.c.execute("SELECT 1 FROM sqlite_master WHERE name LIKE 'domain_%' LIMIT 1").fetchone()
    if not version and not present:
        if require:audit.check(False,'domain_not_enabled',status='INCOMPLETE')
        return {'status':'INCOMPLETE','coverage':'legacy','events':0,'reason':'not_enabled'}
    if not version and present:
        audit.check(False,'domain_partial_schema',status='CORRUPT')
        return {'status':'CORRUPT','coverage':'unknown','events':0}
    if version!=1:
        audit.check(False,'domain_version',status='INCOMPLETE')
        return {'status':'INCOMPLETE','coverage':'unknown','events':0}
    required={'domain_meta','domain_head','domain_tables','domain_events'}
    actual={r[0] for r in audit.c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not required.issubset(actual):
        audit.check(False,'domain_missing_schema',status='CORRUPT')
        return {'status':'CORRUPT','coverage':'unknown','events':0}
    replay=Replay(audit)
    try:return replay.verify()
    except DomainFailure as error:
        replay.check(False,error.code,error.status)
        return {'status':replay.status,'coverage':(replay.meta or {}).get('coverage','unknown'),'events':replay.seq}
