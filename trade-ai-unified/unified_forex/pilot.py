"""Shareable Windows pilot evidence. Whitelist fields, never dump account/terminal objects."""
from hashlib import sha256
from datetime import datetime,timezone
from math import isfinite
from .diagnostics import diagnose
from .engine import code_digest
from forex.contracts import canonical

VERSION='fx-windows-pilot-v8-1'
FIELDS=('broker_symbol','broker_server','digits','point','tick_size','tick_value','tick_value_profit','tick_value_loss',
        'contract_size','volume_min','volume_max','volume_step','stops_level','freeze_level','trade_mode','allowed_directions',
        'account_currency','profit_currency','margin_currency','leverage')


def _safe(value):
    if value is None or type(value) is bool:return value
    if type(value) in (int,float):return value if isfinite(value) else None
    if isinstance(value,str):
        if len(value)>128 or any(s in value for s in ('@','/','\\',':')):return 'REDACTED'
        return value
    if isinstance(value,list) and len(value)<=4:return [_safe(v) for v in value]
    return None


def export(provider,symbols=('XAUUSD','EURUSD','GBPUSD','USDJPY')):
    result={'version':VERSION,'timestamp':datetime.now(timezone.utc).isoformat(),
        'code_sha256':code_digest(),'execution_permission':False,'mt5_validation':'UNVERIFIED',
        'terminal_connected':False,'symbols':{},'account_number_exported':False,
        'recommended_next_test':'Review exact aliases, tick/profit/grid/session declarations; observe demo quotes only.'}
    try:raw=diagnose(provider,symbols)
    except Exception:
        result['status']='DATA_UNAVAILABLE';result['reason']='read-only diagnostic unavailable; inspect local terminal'
        return result
    result['terminal_connected']=(raw.get('terminal') or {}).get('connected') is True
    for symbol in symbols:
        item=raw.get('symbols',{}).get(symbol,{})
        m=item.get('contract',{})
        row={'status':item.get('status','UNAVAILABLE'),'contract':{k:_safe(m.get(k)) for k in FIELDS},
             'quote':{k:_safe((item.get('quote') or {}).get(k)) for k in ('bid','ask','time','age_seconds')},
             'schedule_trust':(item.get('schedule_provenance') or {}).get('trust','UNAVAILABLE'),
             'schedule_authenticated':False,'missing_configuration':[],
             'profit_samples':[{k:_safe(s.get(k)) for k in ('direction','lots','entry','stop','pnl_account_currency','loss_sign_valid')}
                               for s in item.get('readonly_profit_samples',[])[:2]],
             'margin_samples':[],'swap_status':'UNVERIFIED'}
        if row['schedule_trust']=='UNAVAILABLE':row['missing_configuration'].append('declared_broker_hours_and_source')
        if not m.get('broker_symbol'):row['missing_configuration'].append('exact_symbol_alias_and_contract')
        for side in m.get('allowed_directions',[])[:2]:
            if side not in ('BUY','SELL') or not hasattr(provider,'margin_for'):continue
            try:
                q=item['quote'];price=q['ask'] if side=='BUY' else q['bid']
                amount=provider.margin_for(symbol,side,m['volume_min'],price)
                row['margin_samples'].append({'direction':side,'lots':m['volume_min'],'account_currency':m.get('account_currency'),
                    'margin':_safe(amount),'basis':'READONLY_BROKER_CALCULATION_NOT_ORDER_APPROVAL'})
            except Exception:row['margin_status']='UNAVAILABLE'
        result['symbols'][symbol]=row
    result['status']='READONLY_EVIDENCE_EXPORTED' if result['terminal_connected'] else 'DATA_UNAVAILABLE'
    result['evidence_sha256']=sha256(canonical(result).encode()).hexdigest()
    return result


def reconcile(expected,observed):
    """Compare sanitized financial contract fields, never user account records."""
    return {'version':VERSION,'differences':{symbol:{key:{'expected':_safe(old.get(key)),'observed':_safe((observed['symbols'].get(symbol,{}).get('contract') or {}).get(key))}
        for key in FIELDS if old.get(key)!=(observed['symbols'].get(symbol,{}).get('contract') or {}).get(key)}
        for symbol,old in expected.items() if symbol in ('XAUUSD','EURUSD','GBPUSD','USDJPY')},
        'market_validation':False,'execution_permission':False}
