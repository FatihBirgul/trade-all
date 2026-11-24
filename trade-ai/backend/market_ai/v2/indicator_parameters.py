"""Frozen research-only parameters; existing live/default indicator paths untouched.

EMA/SMA/RSI and Bollinger reuse legacy pandas functions. RSI/ATR-SMA are explicitly
not Wilder. ADX/Supertrend use existing research Wilder seeding with chosen period.
No prediction labels, risk override, mutable globals or new execution routes.
"""
from dataclasses import dataclass,asdict
from decimal import Decimal as D,Context,localcontext,ROUND_HALF_EVEN
from hashlib import sha256
from itertools import islice
import math,re
import pandas as pd
from market_ai.engines import technical
from .technical_research import wilder
from .technical_adapter import TIMEFRAME_MS
from .market_data_contract import validate_series
from .decision_record import _canonical
from .strategies import STRATEGIES
VERSION='v2-indicator-parameters-1'
CONTEXT=Context(prec=60,rounding=ROUND_HALF_EVEN)
def digest(x):return sha256(_canonical(x).encode()).hexdigest()
def versions():return tuple(sorted((s.strategy_id,s.version) for s in STRATEGIES))
@dataclass(frozen=True)
class IndicatorParameters:
 ema_period:int=20
 sma_period:int=20
 rsi_period:int=14
 macd_fast:int=12
 macd_slow:int=26
 macd_signal:int=9
 atr_period:int=14
 adx_period:int=14
 supertrend_period:int=10
 supertrend_multiplier:str='3'
 donchian_period:int=20
 stochastic_period:int=14
 stochastic_smooth:int=3
 bollinger_period:int=20
 bollinger_multiplier:str='2'
 confirmation_filter:str='none'
 bias_timeframe:str|None=None
 bias_confirmation:bool=False
 implementation_version:str=VERSION
 strategy_versions:tuple=tuple(sorted((s.strategy_id,s.version) for s in STRATEGIES))
 def __post_init__(self):
  for key in ('ema_period','sma_period','rsi_period','macd_fast','macd_slow','macd_signal','atr_period','adx_period','supertrend_period','donchian_period','stochastic_period','stochastic_smooth','bollinger_period'):
   value=getattr(self,key);maximum=200 if key in ('ema_period','sma_period','macd_slow','donchian_period') else 20 if key=='stochastic_smooth' else 100
   if type(value) is not int or not (1 if key=='stochastic_smooth' else 2)<=value<=maximum:raise ValueError('Unsupported bounded indicator period')
  if self.macd_fast>=self.macd_slow or self.implementation_version!=VERSION or type(self.strategy_versions) is not tuple or self.strategy_versions!=versions():raise ValueError('Indicator/strategy version mismatch or MACD ordering')
  if self.confirmation_filter not in ('none','close_vs_ema','close_vs_sma','rsi_midline') or type(self.bias_confirmation) is not bool or self.bias_timeframe is not None and self.bias_timeframe not in TIMEFRAME_MS or self.bias_confirmation and self.bias_timeframe is None:raise ValueError('Unsupported research filter/frame')
  with localcontext(CONTEXT):
   for key,low,high in (('supertrend_multiplier',D(1),D(10)),('bollinger_multiplier',D('.1'),D(5))):
    value=getattr(self,key)
    if type(value) is not str or not re.fullmatch(r'[0-9]{1,2}(?:\.[0-9]{1,4})?',value) or not low<=D(value)<=high:raise ValueError('Finite decimal-string multiplier required')
    object.__setattr__(self,key,format(D(value).normalize(),'f'))
 @property
 def parameter_id(self):return digest(asdict(self))
 @property
 def warmup_bars(self):return max(self.ema_period*2,self.sma_period,self.rsi_period+1,self.macd_slow*2+self.macd_signal,2*self.adx_period,self.atr_period+1,self.supertrend_period+1,self.donchian_period+1,self.stochastic_period+self.stochastic_smooth-1,self.bollinger_period)

def compute_parameters(candles,parameters,*,timeframe,as_of_ms,max_age_ms,bias_candles=None):
 if not isinstance(parameters,IndicatorParameters):raise ValueError('Immutable research parameters required')
 p=parameters;bars=tuple(islice(candles,1025))
 result={'implementation_version':VERSION,'parameter_id':p.parameter_id,'strategy_versions':dict(p.strategy_versions),'warmup_bars':p.warmup_bars,'status':'unavailable','trade_permission':False,'evidence_status':'INSUFFICIENT_EVIDENCE','timeframe':timeframe,'as_of_ms':as_of_ms,'methods':{}}
 if len(bars)>1024 or timeframe not in TIMEFRAME_MS:return {**result,'reason':'resource_or_frame_budget'}
 q=validate_series(bars,timeframe_ms=TIMEFRAME_MS[timeframe],as_of_ms=as_of_ms,max_age_ms=max_age_ms,min_bars=p.warmup_bars)
 if not q.ok or any(b.open_time_ms%TIMEFRAME_MS[timeframe] for b in bars):return {**result,'reason':'closed_data_or_warmup','issues':[i.code for i in q.issues]}
 with localcontext(CONTEXT):
  h,l,c=([D(str(getattr(b,k))) for b in bars] for k in ('high','low','close'));n=len(bars)
  if any(abs(x)>D('1e100') for x in (*h,*l,*c)):return {**result,'reason':'numeric_range'}
  def txt(x):return format(D(0) if x==0 else x,'f')
  def scalar(x):
   x=float(x)
   if not math.isfinite(x):raise ValueError('Nonfinite indicator output')
   return txt(D(str(x)))
  s=pd.Series([float(x) for x in c]);frame=pd.DataFrame({'high':[float(x) for x in h],'low':[float(x) for x in l],'close':s})
  line=technical.ema(s,p.macd_fast)-technical.ema(s,p.macd_slow);signal=technical.ema(line,p.macd_signal)
  upper,middle,lower=technical.bollinger(s,p.bollinger_period,float(p.bollinger_multiplier))
  methods={'close':txt(c[-1]),'ema':scalar(technical.ema(s,p.ema_period).iloc[-1]),'sma':scalar(technical.sma(s,p.sma_period).iloc[-1]),'rsi_sma':scalar(technical.rsi(s,p.rsi_period).iloc[-1]),'macd_line':scalar(line.iloc[-1]),'macd_signal':scalar(signal.iloc[-1]),'macd_histogram':scalar((line-signal).iloc[-1]),'atr_sma':scalar(technical.atr(frame,p.atr_period).iloc[-1]),'bollinger_upper':scalar(upper.iloc[-1]),'bollinger_middle':scalar(middle.iloc[-1]),'bollinger_lower':scalar(lower.iloc[-1]),'donchian_upper':txt(max(h[-p.donchian_period-1:-1])),'donchian_lower':txt(min(l[-p.donchian_period-1:-1]))}
  stochastic=[]
  for i in range(n-p.stochastic_smooth,n):
   high,low=max(h[i-p.stochastic_period+1:i+1]),min(l[i-p.stochastic_period+1:i+1])
   stochastic.append((c[i]-low)/(high-low)*100 if high>low else None)
  methods['stochastic_k']=txt(stochastic[-1]) if stochastic[-1] is not None else None
  methods['stochastic_d']=txt(sum(stochastic)/len(stochastic)) if all(x is not None for x in stochastic) else None
  tr=[max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1])) for i in range(1,n)];plus=[];minus=[]
  for i in range(1,n):
   up,down=h[i]-h[i-1],l[i-1]-l[i];plus.append(up if up>down and up>0 else D(0));minus.append(down if down>up and down>0 else D(0))
  a,pl,mi=(wilder(v,p.adx_period) for v in (tr,plus,minus));dx=[]
  for i in range(p.adx_period,n):
   pos=100*pl[i]/a[i] if a[i] else D(0);neg=100*mi[i]/a[i] if a[i] else D(0);dx.append(100*abs(pos-neg)/(pos+neg) if pos+neg else D(0))
  methods.update(adx_wilder=txt(wilder(dx,p.adx_period)[len(dx)]),plus_di=txt(pos),minus_di=txt(neg))
  atr=wilder(tr,p.supertrend_period);top=bottom=direction=None
  for i in range(p.supertrend_period,n):
   mid=(h[i]+l[i])/2;bu=mid+D(p.supertrend_multiplier)*atr[i];bl=mid-D(p.supertrend_multiplier)*atr[i]
   if top is None:top,bottom=bu,bl;direction='bullish' if c[i]>mid else 'bearish'
   else:
    top=bu if bu<top or c[i-1]>top else top;bottom=bl if bl>bottom or c[i-1]<bottom else bottom
    if direction=='bullish' and c[i]<bottom:direction='bearish'
    elif direction=='bearish' and c[i]>top:direction='bullish'
  methods.update(supertrend=txt(bottom if direction=='bullish' else top),supertrend_direction=direction)
  bias=None;bias_rows=()
  if p.bias_timeframe:
   if TIMEFRAME_MS[p.bias_timeframe]<=TIMEFRAME_MS[timeframe] or TIMEFRAME_MS[p.bias_timeframe]%TIMEFRAME_MS[timeframe]:return {**result,'reason':'invalid_bias_role'}
   bias_rows=tuple(islice(bias_candles or (),1025));bq=validate_series(bias_rows,timeframe_ms=TIMEFRAME_MS[p.bias_timeframe],as_of_ms=as_of_ms,max_age_ms=TIMEFRAME_MS[p.bias_timeframe],min_bars=2*p.ema_period)
   if len(bias_rows)>1024 or not bq.ok or any(b.instrument!=bars[0].instrument or b.source!=bars[0].source or b.open_time_ms%TIMEFRAME_MS[p.bias_timeframe] or abs(D(str(b.close)))>D('1e100') for b in bias_rows):return {**result,'reason':'missing_or_invalid_bias'}
   bs=pd.Series([float(b.close) for b in bias_rows]);bias={'timeframe':p.bias_timeframe,'close':scalar(bs.iloc[-1]),'ema':scalar(technical.ema(bs,p.ema_period).iloc[-1]),'known_at':bias_rows[-1].close_time_ms}
  input_digest=digest({'candles':bars,'bias_candles':bias_rows,'timeframe':timeframe})
  return {**result,'status':'available','input_digest':input_digest,'configuration_id':digest({'parameter_id':p.parameter_id,'input_digest':input_digest}),'methods':methods,'bias':bias,'filter_name':p.confirmation_filter,'bias_confirmation':p.bias_confirmation,'definition':'Legacy adjust=False EMA / rolling SMA-RSI-ATR / sample-std bands; research Wilder ADX and Supertrend, previous Donchian; flat stochastic undefined. Not live strategy settings.'}

def parameter_filter(report,direction):
 if report['status']!='available' or direction not in ('bullish','bearish'):return {'passes':False,'reason':'research_unavailable_or_wait','trade_permission':False}
 up=direction=='bullish';m=report['methods'];name=report['filter_name'];passed=True
 if name in ('close_vs_ema','close_vs_sma'):passed=D(m['close'])>D(m['ema' if name=='close_vs_ema' else 'sma']) if up else D(m['close'])<D(m['ema' if name=='close_vs_ema' else 'sma'])
 elif name=='rsi_midline':passed=D(m['rsi_sma'])>50 if up else D(m['rsi_sma'])<50
 if report['bias_confirmation']:
  b=report['bias'];passed=passed and (D(b['close'])>D(b['ema']) if up else D(b['close'])<D(b['ema']))
 return {'passes':bool(passed),'reason':'research_restriction_passed' if passed else 'research_restriction_failed','trade_permission':False}
