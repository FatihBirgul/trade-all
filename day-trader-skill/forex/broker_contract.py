"""Current MT5 observations with field-level trust; never historical authority."""
from decimal import Decimal
import math

from .core import DataError, finite, SYMBOLS, DATA_SYMBOLS

ALIASES = {s: s+'c' for s in DATA_SYMBOLS}
POSITIVE = ('contract_size', 'point', 'tick_size', 'tick_value_profit', 'tick_value_loss',
            'volume_min', 'volume_max', 'volume_step')


def contract_observation(meta, observed_at):
    fields, missing, conflicts = {}, [], []

    def field(key, valid, conflict=False):
        value = meta.get(key)
        status = 'CURRENT_MT5_OBSERVED' if valid else 'CONFLICTING' if conflict else 'UNVERIFIED'
        fields[key] = {'value': value, 'trust': status}
        if not valid:
            (conflicts if conflict else missing).append(key)

    symbol = meta.get('symbol')
    field('symbol', symbol in ALIASES)
    field('broker_symbol', symbol in ALIASES and meta.get('broker_symbol') == ALIASES[symbol],
          meta.get('broker_symbol') is not None and symbol in ALIASES and meta['broker_symbol'] != ALIASES[symbol])
    field('broker_server', meta.get('broker_server') == 'Exness-MT5Real50', meta.get('broker_server') not in (None, 'Exness-MT5Real50'))
    field('account_currency', meta.get('account_currency') == 'USC', meta.get('account_currency') not in (None, 'USC'))
    for key, expected in (('base_currency', symbol[:3] if symbol in ALIASES else None),
                          ('profit_currency', symbol[3:] if symbol in ALIASES else None),
                          ('margin_currency', symbol[:3] if symbol in ALIASES else None)):
        value = meta.get(key)
        field(key, value is not None and value == expected, value is not None and value != expected)
    for key in POSITIVE:
        value = meta.get(key)
        valid = type(value) in (int, float) and math.isfinite(value) and value > 0
        field(key, valid, value is not None and not valid)
    for key in ('stops_level', 'freeze_level'):
        value = meta.get(key)
        field(key, type(value) in (int, float) and math.isfinite(value) and value >= 0,
              value is not None and not (type(value) in (int, float) and math.isfinite(value) and value >= 0))
    digits = meta.get('digits')
    field('digits', type(digits) is int and 0 <= digits <= 12, digits is not None and not (type(digits) is int and 0 <= digits <= 12))
    calc = meta.get('trade_calc_mode_name')
    field('trade_calc_mode_name', calc in ('FOREX', 'FOREX_NO_LEVERAGE', 'CFD', 'CFDLEVERAGE'), calc not in (None, 'FOREX', 'FOREX_NO_LEVERAGE', 'CFD', 'CFDLEVERAGE'))
    calc_number = meta.get('trade_calc_mode')
    expected_calc = {'FOREX': 0, 'FOREX_NO_LEVERAGE': 5, 'CFD': 2, 'CFDLEVERAGE': 4}.get(calc)
    field('trade_calc_mode', type(calc_number) is int and expected_calc is not None and calc_number == expected_calc,
          calc_number is not None and (type(calc_number) is not int or calc_number != expected_calc))
    mode = meta.get('trade_mode')
    field('trade_mode', type(mode) is int and mode in (0, 1, 2, 3, 4), mode is not None and not (type(mode) is int and mode in (0, 1, 2, 3, 4)))
    if fields['point']['trust'] == fields['digits']['trust'] == 'CURRENT_MT5_OBSERVED':
        if Decimal(str(meta['point'])) != Decimal(10) ** -digits:
            field('point', False, True)
    if all(fields[k]['trust'] == 'CURRENT_MT5_OBSERVED' for k in ('tick_size', 'point')):
        ratio = Decimal(str(meta['tick_size']))/Decimal(str(meta['point']))
        if ratio < 1 or ratio != ratio.to_integral_value():
            field('tick_size', False, True)
    if all(fields[k]['trust'] == 'CURRENT_MT5_OBSERVED' for k in ('volume_min', 'volume_max', 'volume_step')):
        if meta['volume_min'] > meta['volume_max']:
            field('volume_max', False, True)
    classification = ('PRECIOUS_METAL_PAIR' if symbol == 'XAUUSD' else 'FOREX_PAIR') if symbol in ALIASES else None
    identity_ok = all(fields[k]['trust'] == 'CURRENT_MT5_OBSERVED'
                      for k in ('symbol', 'broker_symbol', 'base_currency', 'profit_currency'))
    return {'status': 'CONFLICTING' if conflicts else 'UNVERIFIED' if missing else 'CURRENT_MT5_OBSERVED',
            'observed_at_utc': observed_at, 'historical_status': 'UNVERIFIED',
            'market_classification': {'value': classification if identity_ok else None,
                                      'trust': 'CURRENT_MT5_OBSERVED' if identity_ok else 'UNVERIFIED'},
            'fields': fields, 'missing_fields': sorted(set(missing)), 'conflicting_fields': sorted(set(conflicts))}


def financial_contract_check(meta, entry, stop, lots, broker_loss):
    """Cross-check current contract slope where the currency conversion is explicit."""
    if not meta.get('broker_contract_required'):
        return
    if meta.get('symbol') not in SYMBOLS:
        raise DataError('financial contract not validated for symbol')
    trust = meta.get('broker_contract', {})
    if trust.get('status') != 'CURRENT_MT5_OBSERVED':
        raise DataError('broker contract current metadata unverified or conflicting')
    if meta.get('account_currency') != 'USC' or meta.get('profit_currency') not in ('USD', 'JPY'):
        raise DataError('broker contract currency conversion unavailable')
    # USD -> USC is explicit cent denomination, never equality of currency units.
    # JPY -> USC requires the same fresh USDJPY quote; reciprocal bid/ask gives
    # a conversion interval. Broker/tick and contract-slope checks are separate.
    profit_amount = abs(entry-stop)*finite(meta.get('contract_size'), 'contract_size')*lots
    if meta['profit_currency'] == 'USD':
        minimum = maximum = profit_amount*100
    else:
        from .spread_policy import observed_spread
        quote, as_of = meta.get('_valuation_quote'), meta.get('_valuation_as_of')
        if meta.get('symbol') != 'USDJPY' or not isinstance(quote, dict) or as_of is None:
            raise DataError('broker contract currency conversion unavailable')
        observed_spread(quote, meta, as_of)  # Reject stale/inverted/mis-scaled conversion.
        minimum = profit_amount*100/quote['ask']
        maximum = profit_amount*100/quote['bid']
    if broker_loss < minimum-max(.01, minimum*.01) or broker_loss > maximum+max(.01, maximum*.01):
        raise DataError('broker contract size disagrees with loss oracle')
