"""Informational global sessions and explicit broker-hours policy."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

SESSIONS = {'Asian': ('Asia/Tokyo', 9, 18),
            'London': ('Europe/London', 8, 17),
            'New_York': ('America/New_York', 8, 17)}

def active_sessions(now):
    if now.tzinfo is None: raise ValueError('UTC-aware datetime required')
    names=[]
    for name,(zone,start,end) in SESSIONS.items():
        local=now.astimezone(ZoneInfo(zone))
        if local.weekday()<5 and start <= local.hour < end: names.append(name)
    if 'London' in names and 'New_York' in names: names.append('London_New_York_overlap')
    return names

def _minutes(value, allow_end=False):
    if not isinstance(value,str) or len(value)!=5 or value[2]!=':':
        raise ValueError('invalid HH:MM')
    h,m=int(value[:2]),int(value[3:])
    if h<0 or m<0 or m>59 or h>23 and not (allow_end and h==24 and m==0):
        raise ValueError('invalid HH:MM')
    return h*60+m

def broker_status(now, symbol, trade_allowed=None, hours=None, warning_minutes=30):
    """Explicit local broker schedule with overnight windows and date overrides."""
    if now.tzinfo is None: raise ValueError('UTC-aware datetime required')
    if trade_allowed is False: return {'status':'DISABLED','reason':'broker trading disabled'}
    if isinstance(hours, dict) and hours.get('kind') == 'VERIFIED_HISTORICAL_TRADE':
        stamp = now.timestamp()
        if not any(a <= stamp < b for a, b in hours['coverage']):
            return {'status': 'UNKNOWN', 'reason': 'outside verified historical trade coverage'}
        if any(a <= stamp < b for a, b in hours['close_only']):
            return {'status': 'DISABLED', 'reason': 'verified historical close-only interval'}
        for a, b in hours['open']:
            if a <= stamp < b:
                return {'status': 'CLOSING_SOON' if b-stamp <= warning_minutes*60 else 'OPEN',
                        'reason': 'verified dated trade interval'}
        return {'status': 'CLOSED', 'reason': 'outside verified dated trade interval'}
    if not hours:
        if now.weekday() in (5,6): return {'status':'CLOSED','reason':'Forex weekend; broker hours unverified'}
        return {'status':'UNKNOWN','reason':'broker hours not verified'}
    try:
        local=now.astimezone(ZoneInfo(hours['timezone']))
        weekly=hours['weekly']
        overrides=hours.get('date_overrides',{})
        if not isinstance(weekly,dict) or not isinstance(overrides,dict): raise ValueError('invalid policy')
        def windows(day):
            date=day.date().isoformat()
            if date in overrides:
                value=overrides[date]
                if value is None: return []
                return value
            return weekly.get(str(day.weekday()),[])
        minute=local.hour*60+local.minute
        for day,offset in ((local,-0),(local-timedelta(days=1),1440)):
            for pair in windows(day):
                start,end=pair
                a,b=_minutes(start),_minutes(end,True)
                if a==b: raise ValueError('zero-length window')
                if b<a: b+=1440
                current=minute+offset
                if a<=current<b:
                    remaining=b-current
                    return {'status':'CLOSING_SOON' if remaining<=warning_minutes else 'OPEN',
                            'reason':'configured broker hours','closes_at':end}
                if offset==0 and 0<a-current<=warning_minutes:
                    return {'status':'OPENING_SOON','reason':'configured broker hours','opens_at':start}
        return {'status':'CLOSED','reason':'outside configured broker hours'}
    except (KeyError,TypeError,ValueError,IndexError) as exc:
        return {'status':'UNKNOWN','reason':f'invalid broker-hours policy: {exc}'}


def broker_interval_closed(start_utc, end_utc, hours):
    """True only if every minute in [start, end) is outside declared sessions.

    Schedule boundaries are minute precision. A missing bar must not be
    authorized by OPENING_SOON, disabled trading or an unverified weekend.
    """
    if not hours or start_utc.tzinfo is None or end_utc.tzinfo is None or end_utc <= start_utc:
        return False
    if not isinstance(hours, dict) or not isinstance(hours.get('weekly'), dict):
        return False
    if set(hours['weekly']) != {str(day) for day in range(7)}:
        return False  # Missing weekdays are unknown, not confirmed closures.
    if start_utc.second or start_utc.microsecond or end_utc.second or end_utc.microsecond:
        return False
    minute = start_utc
    while minute < end_utc:
        state = broker_status(minute, '', None, hours, warning_minutes=0)['status']
        if state != 'CLOSED':
            return False
        minute += timedelta(minutes=1)
    return True


def broker_bucket_has_quote(start_utc, end_utc, hours):
    """A candle bucket may begin before the first quote in an open session.

    This minute-resolution check is only used with a provider candle carrying
    positive tick volume. It never turns an unverified schedule into evidence.
    """
    if (not hours or start_utc.tzinfo is None or end_utc.tzinfo is None
            or end_utc <= start_utc or not isinstance(hours, dict)
            or not isinstance(hours.get('weekly'), dict)
            or set(hours['weekly']) != {str(day) for day in range(7)}):
        return False
    minute = start_utc
    while minute < end_utc:
        if broker_status(minute, '', None, hours, warning_minutes=0)['status'] in ('OPEN', 'CLOSING_SOON'):
            return True
        minute += timedelta(minutes=1)
    return False

def session_snapshot(now, symbol, trade_allowed=None, hours=None):
    return {'timestamp':now.astimezone(timezone.utc).isoformat(), 'symbol':symbol,
            'sessions':active_sessions(now),'broker':broker_status(now,symbol,trade_allowed,hours)}
