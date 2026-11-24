"""Bounded official-source adapters. Date-only schedules never acquire invented times."""
from html.parser import HTMLParser
from datetime import datetime,date,timezone
from hashlib import sha256
import re
from pydantic import BaseModel,ConfigDict,Field
from typing import Literal
from .macro import parse_ical,RevisionCalendar
from forex.information import parse_rss

VERSION='fx-official-calendar-v8-1'
SOURCES={
 'fed_calendar':('https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm','USD','America/New_York'),
 'fed_rss':('https://www.federalreserve.gov/feeds/press_monetary.xml','USD','America/New_York'),
 'ecb':('https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html','EUR','Europe/Berlin'),
 'boe':('https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates','GBP','Europe/London'),
 'boj':('https://www.boj.or.jp/en/mopo/mpmsche_minu/','JPY','Asia/Tokyo'),
 'bea':('https://www.bea.gov/news/schedule/ics/online-calendar-subscription.ics','USD','America/New_York')}


class DateEvent(BaseModel):
    model_config=ConfigDict(extra='forbid',frozen=True)
    event_id:str
    source:str
    source_url:str
    currency:str
    category:str
    date_start:date
    date_end:date
    source_timezone:str
    release_utc:None=None
    published_utc:None=None
    retrieved_utc:datetime
    known_at:datetime
    time_precision:Literal['DATE_ONLY']='DATE_ONLY'
    coverage_state:Literal['UNVERIFIED']='UNVERIFIED'
    importance:str='HIGH'
    importance_source:str='versioned_engineering_policy_for_policy_meetings'
    algorithm_version:str=VERSION


class _Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.depth=0;self.captures=[];self.year=None
        self.rows=[];self.cells=[];self.pairs=[];self.dt=None;self.month=None;self.fed=[]
    def handle_starttag(self,tag,attrs):
        self.depth+=1;attrs=dict(attrs);kind=None
        if tag in ('h1','h2','h3','h4','th','td','dt','dd'):kind=tag
        classes=attrs.get('class','')
        if 'fomc-meeting__month' in classes:kind='fed_month'
        if 'fomc-meeting__date' in classes:kind='fed_date'
        if tag=='tr':self.cells=[]
        if kind:self.captures.append([tag,self.depth,kind,[]])
        if tag in ('br','hr','img','meta','link','input'):self.depth-=1
    def handle_data(self,data):
        for capture in self.captures:capture[3].append(data)
    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        if tag not in ('br','hr','img','meta','link','input'):self.handle_endtag(tag)
    def handle_endtag(self,tag):
        for c in list(self.captures):
            if c[0]==tag and c[1]==self.depth:
                value=' '.join(' '.join(c[3]).split());kind=c[2];self.captures.remove(c)
                if kind in ('h1','h2','h3','h4','th'):
                    year=re.search(r'\b(20\d{2})\b',value)
                    if year:self.year=int(year[1])
                elif kind=='td':self.cells.append(value)
                elif kind=='dt':self.dt=value
                elif kind=='dd' and self.dt:self.pairs.append((self.dt,value))
                elif kind=='fed_month':self.month=value
                elif kind=='fed_date' and self.month:self.fed.append((self.year,self.month,value))
        if tag=='tr' and self.cells:self.rows.append((self.year,self.cells));self.cells=[]
        self.depth=max(0,self.depth-1)


MONTHS={m.lower():i for i,m in enumerate(['January','February','March','April','May','June','July','August','September','October','November','December'],1)}
MONTHS.update({k[:3]:v for k,v in list(MONTHS.items())})


def parse_schedule(payload,source_id,*,retrieved_at):
    if source_id not in SOURCES or source_id in ('bea','fed_rss'):raise ValueError('Unsupported HTML schedule source')
    if not isinstance(payload,str) or len(payload.encode())>512000 or retrieved_at.tzinfo is None:raise ValueError('Bounded HTML and aware retrieval required')
    parser=_Page();parser.feed(payload);url,currency,zone=SOURCES[source_id];events={};issues=[]
    def emit(first,last,category):
        if first>last:raise ValueError('Invalid meeting date range')
        eid=sha256(f'{source_id}|{category}|{first}|{last}'.encode()).hexdigest()[:32]
        events[eid]=DateEvent(event_id=eid,source=source_id,source_url=url,currency=currency,category=category,
            date_start=first,date_end=last,source_timezone=zone,retrieved_utc=retrieved_at,known_at=retrieved_at)
    try:
        if source_id=='fed_calendar':
            for year,month,days in parser.fed:
                months=[MONTHS.get(m.strip().lower()) for m in re.split(r'[/–-]',month)]
                numbers=re.findall(r'\d{1,2}',days)
                if year and 1<=len(months)<=2 and all(months) and 1<=len(numbers)<=2:
                    first_month,last_month=months[0],months[-1]
                    last_year=year+int(last_month<first_month)
                    emit(date(year,first_month,int(numbers[0])),date(last_year,last_month,int(numbers[-1])),'FOMC_MEETING')
                else:issues.append('unsupported_month_or_date_range')
        elif source_id=='ecb':
            for stamp,description in parser.pairs:
                if 'monetary policy meeting' not in description.lower() or 'non-monetary' in description.lower():continue
                d=datetime.strptime(stamp.strip(),'%d/%m/%Y').date();emit(d,d,'ECB_POLICY_MEETING')
        else:
            for year,cells in parser.rows:
                if not year or not cells:continue
                text=cells[0]
                if source_id=='boe':
                    match=re.search(r'\b(\d{1,2})\s+([A-Za-z]+)\b',text)
                    if match and match[2].lower() in MONTHS:
                        d=date(year,MONTHS[match[2].lower()],int(match[1]));emit(d,d,'BOE_MPC_MEETING')
                else:
                    match=re.search(r'\b([A-Za-z]{3,9})\.?\s+(\d{1,2})[^,]*,\s*(\d{1,2})',text)
                    if match and match[1].lower() in MONTHS:
                        emit(date(year,MONTHS[match[1].lower()],int(match[2])),date(year,MONTHS[match[1].lower()],int(match[3])),'BOJ_POLICY_MEETING')
    except (ValueError,OverflowError):issues.append('source_schema_or_date_changed')
    return {'version':VERSION,'source':source_id,'events':[e.model_dump(mode='json') for e in sorted(events.values(),key=lambda e:(e.date_start,e.event_id))],
            'data_status':'OFFICIAL_SCHEDULE_PARSED' if events else 'DATA_UNAVAILABLE','issues':issues,
            'payload_sha256':sha256(payload.encode()).hexdigest(),'coverage_state':'UNVERIFIED','directional_permission':False}


def parse_official(payload,source_id,*,retrieved_at):
    if source_id=='bea':
        parsed=parse_ical(payload,retrieved_at=retrieved_at,source_id='bea')
        return {**parsed,'data_status':'OFFICIAL_SCHEDULE_PARSED' if parsed['events'] else 'DATA_UNAVAILABLE',
                'source':source_id,'coverage_state':'UNVERIFIED'}
    if source_id=='fed_rss':
        rows=parse_rss(payload,'FED_OFFICIAL_RSS',retrieved_at)
        return {'source':'fed_rss','announcements':rows,'data_status':'OFFICIAL_ANNOUNCEMENTS_PARSED' if rows else 'DATA_UNAVAILABLE',
                'retrieved_utc':retrieved_at.isoformat(),'coverage_state':'ANNOUNCEMENTS_ONLY_NOT_FORWARD_CALENDAR','directional_permission':False}
    return parse_schedule(payload,source_id,retrieved_at=retrieved_at)


def fetch_official(source_id,*,usage_reviewed=False,as_of=None):
    if source_id not in SOURCES:raise ValueError('Unknown fixed official source')
    if not usage_reviewed:return {'data_status':'USAGE_REVIEW_REQUIRED','source':source_id,'coverage_state':'UNVERIFIED'}
    import httpx
    now=as_of or datetime.now(timezone.utc)
    try:
        with httpx.Client(timeout=8,follow_redirects=False) as client:
            with client.stream('GET',SOURCES[source_id][0]) as response:
                response.raise_for_status();parts=[];size=0
                for chunk in response.iter_bytes():
                    size+=len(chunk)
                    if size>512000:raise ValueError('Source exceeds payload budget')
                    parts.append(chunk)
        return parse_official(b''.join(parts).decode('utf-8-sig'),source_id,retrieved_at=now)
    except (httpx.HTTPError,ValueError,UnicodeError):return {'source':source_id,'data_status':'DATA_UNAVAILABLE','events':[],'coverage_state':'UNVERIFIED','reason':'source unavailable or schema unsupported'}


def coverage_snapshot(result,*,source_id,retrieved_at,previous=None):
    """Compare observed schema/identity coverage without asserting completeness."""
    if source_id not in SOURCES or retrieved_at.tzinfo is None:raise ValueError('Known source and aware retrieval required')
    rows=result.get('events',[])
    if len(rows)>500:raise ValueError('Coverage monitoring budget exceeded')
    identifiers=[];upcoming=0
    for raw in rows:
        row=raw.model_dump(mode='json') if hasattr(raw,'model_dump') else raw
        identifiers.append(row['event_id'])
        if row.get('release_at'):
            upcoming+=datetime.fromisoformat(row['release_at'])>=retrieved_at
        elif row.get('date_end'):
            from zoneinfo import ZoneInfo
            upcoming+=row['date_end']>=retrieved_at.astimezone(ZoneInfo(row['source_timezone'])).date().isoformat()
    before=set(previous.get('event_ids',[])) if previous else set();after=set(identifiers)
    return {'version':'fx-macro-monitor-v9-1','source':source_id,'url':SOURCES[source_id][0],
        'retrieved_at':retrieved_at.isoformat(),'status':result.get('data_status','DATA_UNAVAILABLE'),
        'count':len(rows),'upcoming_count':upcoming,'event_ids':sorted(after),
        'added':sorted(after-before) if previous else [],'removed':sorted(before-after) if previous else [],
        'schema_issue_count':len(result.get('issues',[])),
        'schedule_status':'NO_UPCOMING_RECORDS_OBSERVED' if rows and not upcoming else 'PARTIAL_OBSERVED_COVERAGE' if rows else 'UNAVAILABLE',
        'payload_sha256':result.get('payload_sha256'),'coverage_complete':False,'source_authenticated':False,
        'limitation':'Source changes/removals are observed, not retrospectively rewritten history or all-event protection.'}


class ScheduleProvider(RevisionCalendar):
    name='official-parsed-schedules-v8'
    def __init__(self,precise=(),date_only=()):
        super().__init__(list(precise))
        if len(date_only)>500:raise ValueError('Date-event budget exceeded')
        self.dates=tuple(DateEvent.model_validate(e) for e in date_only)
    def date_events(self,as_of):
        return [e.model_dump(mode='json') for e in self.dates if e.known_at<=as_of and e.retrieved_utc<=as_of]
