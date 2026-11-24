"""Versioned, as-of macro revisions composed with retained Day Trader contracts."""
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
from hashlib import sha256
from pydantic import Field
from typing import Literal
import re
from forex.macro import MacroEvent,information_context as original_context

VERSION='fx-macro-revisions-v7-1'
OFFICIAL_SOURCES={
 'bls':{'url':'https://www.bls.gov/schedule/news_release/bls.ics','format':'ical','currency':'USD',
        'usage':'BLS public-domain policy; third-party attribution exceptions must still be checked'},
 'fed':{'url':'https://www.federalreserve.gov/feeds/press_monetary.xml','format':'rss','currency':'USD','usage':'REVIEW_REQUIRED'},
 'ecb':{'url':'https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html','format':'html','currency':'EUR','usage':'REVIEW_REQUIRED'},
 'boe':{'url':'https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates','format':'html','currency':'GBP','usage':'REVIEW_REQUIRED'},
 'boj':{'url':'https://www.boj.or.jp/en/mopo/mpmsche_minu/','format':'html','currency':'JPY','usage':'REVIEW_REQUIRED'}}


class RevisedEvent(MacroEvent):
    revision:int=Field(default=0,ge=0,le=1_000_000,strict=True)
    underlying_event_id:str|None=Field(default=None,max_length=150)
    coverage_status:str=Field(default='UNVERIFIED',pattern='^UNVERIFIED$')
    source_published_at:datetime|None=None
    source_record_timestamp:datetime|None=None
    publication_basis:Literal['SOURCE_TIMESTAMP','FIRST_OBSERVED_RETRIEVAL']='SOURCE_TIMESTAMP'


class RevisionCalendar:
    name='declared-revision-calendar-v7'
    def __init__(self,events):
        if not isinstance(events,(list,tuple)) or len(events)>500:raise ValueError('At most500 revisions')
        self.rows=tuple(RevisedEvent.model_validate(e) for e in events)
    def selected(self,as_of):
        selected={}
        for e in self.rows:
            if e.published_at>as_of or e.retrieved_at>as_of:continue
            key=e.underlying_event_id or f'{e.currency}|{e.event_type}|{e.release_at.isoformat()}'
            old=selected.get(key)
            if old is not None and (e.published_at,e.revision,e.source)==(old.published_at,old.revision,old.source):
                if e.model_dump(exclude={'retrieved_at'})!=old.model_dump(exclude={'retrieved_at'}):raise ValueError('Conflicting equal event revision')
            if old is None or (e.published_at,e.revision,e.retrieved_at,e.source)>(old.published_at,old.revision,old.retrieved_at,old.source):selected[key]=e
            elif (e.published_at,e.revision,e.source)==(old.published_at,old.revision,old.source) and e!=old:
                raise ValueError('Conflicting equal event revision')
        return sorted(selected.values(),key=lambda e:(e.release_at,e.event_id))
    def events(self,as_of):
        return [MacroEvent.model_validate(e.model_dump(include=set(MacroEvent.model_fields))) for e in self.selected(as_of)]


def information_context(provider=None,*,as_of=None,max_age_seconds=86400):
    now=as_of or datetime.now(timezone.utc)
    result=original_context(provider,as_of=now,max_age_seconds=max_age_seconds)
    result.update(version=VERSION,coverage_status='UNVERIFIED',success_probability=None)
    if isinstance(provider,RevisionCalendar) and result['data_status']=='DECLARED_SOURCE':
        result['events']=[e.model_dump(mode='json')|{'published_utc':e.source_published_at.isoformat() if e.source_published_at else (e.published_at.isoformat() if e.publication_basis=='SOURCE_TIMESTAMP' else None),
            'known_at':max(e.published_at,e.retrieved_at).isoformat(),
            'freshness_seconds':(now-e.retrieved_at).total_seconds()} for e in provider.selected(now)]
    result['date_only_events']=[]
    if hasattr(provider,'date_events'):
        try:
            rows=provider.date_events(now)
            if len(rows)>500:raise ValueError('Date calendar budget exceeded')
            result['date_only_events']=[e for e in rows if datetime.fromisoformat(e['retrieved_utc'])<=now and (now-datetime.fromisoformat(e['retrieved_utc'])).total_seconds()<=max_age_seconds]
        except Exception:result.update(data_status='DATA_UNAVAILABLE',reason='date schedule unavailable or invalid')
    return result


def event_window(event,before_minutes,after_minutes):
    if any(type(x) is not int or not 0<=x<=180 for x in (before_minutes,after_minutes)):raise ValueError('Bounded macro windows required')
    e=RevisedEvent.model_validate(event)
    return {'start':e.release_at-timedelta(minutes=before_minutes),'end':e.release_at+timedelta(minutes=after_minutes),
            'coverage_status':'UNVERIFIED','event_id':e.event_id}


def parse_bls_ical(payload,*,retrieved_at):
    return parse_ical(payload,retrieved_at=retrieved_at,source_id='bls')


def parse_ical(payload,*,retrieved_at,source_id='bls'):
    """Strict bounded ICS subset. Missing time/provenance is never invented.

    Recurrences, all-day releases and ambiguous/nonexistent local times are
    rejected. Unsupported records remain issues; coverage is always unverified.
    """
    if not isinstance(payload,str) or len(payload.encode())>512000 or retrieved_at.tzinfo is None:raise ValueError('Bounded ICS and aware retrieval required')
    if source_id not in ('bls','bea'):raise ValueError('Unsupported official ICS source')
    source_url=OFFICIAL_SOURCES['bls']['url'] if source_id=='bls' else 'https://www.bea.gov/news/schedule/ics/online-calendar-subscription.ics'
    if 'BEGIN:VCALENDAR' not in payload or 'END:VCALENDAR' not in payload:raise ValueError('Complete iCalendar required')
    lines=[]
    for line in payload.replace('\r\n','\n').split('\n'):
        if line.startswith((' ','\t')) and lines:lines[-1]+=line[1:]
        else:lines.append(line)
    records=[];row=None;issues=[]
    for line in lines:
        if line=='BEGIN:VEVENT':
            if row is not None:raise ValueError('Nested calendar events')
            row={}
        elif line=='END:VEVENT' and row is not None:records.append(row);row=None
        elif row is not None and ':' in line:
            key,value=line.split(':',1)
            if key in row:raise ValueError('Duplicate calendar property')
            row[key]=value
    if len(records)>500:raise ValueError('Calendar record budget exceeded')
    def stamp(key,value):
        if re.search(r'(?:^|;)VALUE=DATE(?:;|$)',key) or len(value)<15:raise ValueError('Release time unavailable')
        if value.endswith('Z'):return datetime.strptime(value,'%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
        zone=key.split('TZID=',1)[1].split(';',1)[0] if 'TZID=' in key else None
        if zone=='US-Eastern':zone='America/New_York' # BLS's published VTIMEZONE name
        if not zone:raise ValueError('Calendar timezone unavailable')
        naive=datetime.strptime(value,'%Y%m%dT%H%M%S');tz=ZoneInfo(zone)
        a=naive.replace(tzinfo=tz,fold=0);b=naive.replace(tzinfo=tz,fold=1)
        if a.utcoffset()!=b.utcoffset() or a.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None)!=naive:
            raise ValueError('Ambiguous or nonexistent release time')
        return a.astimezone(timezone.utc)
    events=[]
    for record in records:
        try:
            if 'RRULE' in record:raise ValueError('Unsupported calendar recurrence')
            key=next(k for k in record if k.startswith('DTSTART'))
            release=stamp(key,record[key]);publication_key=next((k for k in record if k.startswith('DTSTAMP')),None)
            published=stamp(publication_key,record[publication_key]) if publication_key else None
            title=record['SUMMARY'].lower()
            typ='GDP' if source_id=='bea' and ('gross domestic product' in title or 'gdp' in title) else 'CPI' if 'consumer price' in title else 'NFP' if 'employment situation' in title else 'OTHER'
            uid=record['UID'];event_id=sha256(uid.encode()).hexdigest()[:32]
            events.append(RevisedEvent(event_id=event_id,underlying_event_id=event_id,source=source_id.upper()+'_ICAL_DECLARED',
                url=source_url,published_at=retrieved_at,
                source_published_at=None,source_record_timestamp=published,publication_basis='FIRST_OBSERVED_RETRIEVAL',
                release_at=release,retrieved_at=retrieved_at,
                currency='USD',event_type=typ,importance='HIGH' if typ in ('CPI','NFP','GDP') else 'UNKNOWN',revision=int(record.get('SEQUENCE','0'))))
        except (KeyError,ValueError,StopIteration):issues.append('unsupported_or_invalid_event')
    return {'events':events,'issues':issues,'coverage_status':'UNVERIFIED','source_authenticated':False,
            'payload_sha256':sha256(payload.encode()).hexdigest(),'directional_permission':False}


def fetch_bls_calendar(*,as_of=None):
    """One explicit official-source request, no redirects/retries or fallback data.

    Never called by analysis/API startup. BLS textual releases have a public-domain
    policy; no images or third-party content are copied. Network failure returns
    UNAVAILABLE, never fixtures. Returned data still has unverified event coverage.
    """
    import httpx
    now=as_of or datetime.now(timezone.utc)
    try:
        with httpx.Client(timeout=8,follow_redirects=False) as client:
            with client.stream('GET',OFFICIAL_SOURCES['bls']['url'],headers={'User-Agent':'TradeAIResearch/7.0 (read-only calendar)'}) as response:
                response.raise_for_status();parts=[];size=0
                for chunk in response.iter_bytes():
                    size+=len(chunk)
                    if size>512000:raise ValueError('Official calendar exceeds budget')
                    parts.append(chunk)
        parsed=parse_bls_ical(b''.join(parts).decode('utf-8-sig'),retrieved_at=now)
        return {**parsed,'data_status':'OFFICIAL_URL_RETRIEVED' if parsed['events'] else 'DATA_UNAVAILABLE',
                'future_event_count':sum(e.release_at>=now for e in parsed['events']),
                'latest_release_at':max((e.release_at for e in parsed['events']),default=now).isoformat(),
                'retrieved_at':now.isoformat(),'url':OFFICIAL_SOURCES['bls']['url']}
    except (httpx.HTTPError,ValueError,UnicodeError):
        return {'data_status':'DATA_UNAVAILABLE','events':[],'coverage_status':'UNVERIFIED',
                'reason':'official calendar unavailable or unsupported payload','directional_permission':False}
