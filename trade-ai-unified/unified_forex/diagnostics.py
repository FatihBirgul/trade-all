"""Read-only diagnostic extension; shares retained MT5 SDK allowlist."""
from datetime import datetime,timezone
from forex.mt5_diagnostic import diagnose as retained_diagnose
from forex.core import SYMBOLS,DataError,finite
from .market import schedule_contract


def diagnose(provider,symbols=SYMBOLS):
    if not symbols or not set(symbols)<=set(SYMBOLS):raise ValueError('Supported diagnostic symbols required')
    report=retained_diagnose(provider,symbols)
    report.update(version='fx-readonly-diagnostic-v7-1',execution_permission=False,mt5_validation='UNVERIFIED')
    for symbol in symbols:
        row=report['symbols'].get(symbol)
        if not row or row['status']!='OK':continue
        try:
            m=provider.metadata(symbol);q=provider.quote(symbol)
            row['contract']={k:m.get(k) for k in ('broker_symbol','broker_server','digits','point','tick_size','tick_value','tick_value_profit','tick_value_loss','contract_size','volume_min','volume_max','volume_step','stops_level','freeze_level','trade_mode','allowed_directions','account_currency','profit_currency','margin_currency','margin_free','leverage')}
            row['quote']={k:q.get(k) for k in ('bid','ask','time')}
            row['quote']['age_seconds']=datetime.now(timezone.utc).timestamp()-finite(q['time'],'tick time')
            row['schedule_provenance']=schedule_contract(m)
            samples=[]
            if hasattr(provider,'loss_for'):
                for side in m.get('allowed_directions',[]):
                    entry=q['ask'] if side=='BUY' else q['bid'];stop=entry+(1 if side=='SELL' else -1)*m['tick_size']*100
                    if stop<=0:continue
                    pnl=finite(provider.loss_for(symbol,side,m['volume_min'],entry,stop),'broker stop result')
                    samples.append(dict(direction=side,lots=m['volume_min'],entry=entry,stop=stop,
                                        pnl_account_currency=pnl,loss_sign_valid=pnl<0,
                                        authoritative=provider.name=='mt5'))
            row['readonly_profit_samples']=samples
            row['margin_check']='INFORMATION_ONLY; no order_check or order submission'
        except (DataError,KeyError,TypeError,ValueError):row.update(status='PARTIAL',reason='read-only diagnostic metadata or calculation unavailable')
    return report
