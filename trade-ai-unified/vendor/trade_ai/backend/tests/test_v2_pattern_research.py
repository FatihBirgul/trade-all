"""Causal pattern research, never a standalone trading permission."""
from dataclasses import replace
from decimal import localcontext, ROUND_DOWN
from unittest import TestCase
from market_ai.v2.market_data_contract import Candle, Instrument
from market_ai.v2.pattern_research import detect_patterns, confluence_evidence, CATALOG
from market_ai.engines.confluence import build_confluence
TF=60000
I=Instrument('BTCUSDT','crypto_spot','fixture','last','spot','USDT')
def bars(tail=()):
    values=[(100,101,99,100.1)]*30+list(tail)
    return [Candle(I,i*TF,(i+1)*TF,True,*row,100,'real','fixture_spot') for i,row in enumerate(values)]
def detect(b):
    return detect_patterns(b,timeframe='1m',as_of_ms=b[-1].close_time_ms,max_age_ms=TF,tick_size='0.01')
class PatternResearchTests(TestCase):
    def test_existing_taxonomy_is_reused_with_explicit_context(self):
        b=bars([(100,103,99,102),(101.9,102,98,98.1)])
        r=detect(b)
        self.assertEqual(r['status'],'available');self.assertEqual(r['validation_status'],'DETECTION_IMPLEMENTED');self.assertFalse(r['trade_permission']);self.assertTrue(r['patterns'])
        for p in r['patterns']:
            for k in ('pattern_id','pattern_version','formed_at','confirmed_at','timeframe','trend_context','support_resistance_context','volatility_context','volume_confirmation','quality_status','explanation'):self.assertIn(k,p)
            self.assertLessEqual(p['formed_at'],b[-1].close_time_ms)
    def test_new_gap_and_containment_families_positive_and_mirror(self):
        cases={
          'harami_cross':[(105,106,95,96),(100,100.3,99.7,100)],
          'three_inside':[(105,106,95,96),(98,101,97,100),(100,107,99,106)],
          'three_outside':[(101,102,97,98),(97,104,96,103),(103,106,102,105)],
          'kicking':[(105,105,95,95),(107,117,107,117)],
          'abandoned_baby':[(105,106,95,96),(93,94,92,93),(96,106,95,105)],
          'tasuki_gap':[(95,101,94,100),(103,109,102,108),(107,108,100,101.5)],
          'matching_low':[(105,106,99,100),(103,104,99,100)],
          'counterattack':[(105,106,94,95),(92,96,91,95)],
          'rising_three_methods':[(100,111,99,110),(108,109,103,104),(106,108,102,103),(105,107,101,102),(103,113,102,112)],
          'morning_doji_star':[(105,106,95,96),(94,94.3,93.7,94),(95,104,94.5,103)],
        }
        for family,tail in cases.items():
            for mirror in (False,True):
                with self.subTest(family=family,mirror=mirror):
                    data=tail if not mirror else [(200-o,200-l,200-h,200-c) for o,h,l,c in tail]
                    ids={p['family'] for p in detect(bars(data))['patterns']}
                    wanted={'rising_three_methods':'falling_three_methods','morning_doji_star':'evening_doji_star','matching_low':'matching_high'}.get(family,family) if mirror else family
                    self.assertIn(wanted,ids)
    def test_gapped_patterns_do_not_accept_a_non_gap(self):
        self.assertNotIn('kicking',{p['family'] for p in detect(bars([(105,105,95,95),(94,104,94,104)]))['patterns']})
        self.assertNotIn('abandoned_baby',{p['family'] for p in detect(bars([(105,106,95,96),(96,97,95,96),(97,106,96,105)]))['patterns']})
    def test_tasuki_gap_must_remain_open_and_line_sizes_use_prior_context(self):
        closed=detect(bars([(95,101,94,100),(103,109,102,108),(107,108,100,101)]))
        self.assertNotIn('tasuki_gap',{p['family'] for p in closed['patterns']})
        for tail,family in (([(100,112,99,110)],'long_line'), ([(100,100.06,99.99,100.04)],'short_line')):
            self.assertIn(family,{p['family'] for p in detect(bars(tail))['patterns']})
    def test_future_unfinished_gap_and_stale_data_are_rejected(self):
        b=bars()
        for bad in (b[:-1]+[replace(b[-1],is_final=False)],b[:-2]+b[-1:],b[:-1]+[replace(b[-1],high=float('nan'))]):self.assertEqual(detect(bad)['status'],'unavailable')
        for asof in (b[-1].close_time_ms-TF,b[-1].close_time_ms+2*TF):self.assertEqual(detect_patterns(b,timeframe='1m',as_of_ms=asof,max_age_ms=TF,tick_size='0.01')['status'],'unavailable')
    def test_prefix_confirmation_never_uses_a_future_bar(self):
        b=bars([(105,105,95,95),(107,117,107,117)])
        before=detect(b);p=next(p for p in before['patterns'] if p['family']=='kicking');self.assertIsNone(p['confirmed_at'])
        nextbar=replace(b[-1],open_time_ms=b[-1].close_time_ms,close_time_ms=b[-1].close_time_ms+TF,open=117,high=121,low=116,close=120)
        p=next(p for p in detect(b+[nextbar])['patterns'] if p['family']=='kicking');self.assertEqual(p['confirmed_at'],nextbar.close_time_ms);self.assertEqual(detect(b),before)
    def test_no_fake_volume_and_single_evidence_bucket(self):
        b=[replace(x,volume_kind='unavailable',volume=None) for x in bars([(105,105,95,95),(107,117,107,117),(117,121,116,120)])]
        r=detect(b);self.assertEqual(r['status'],'available');self.assertTrue(all(p['volume_confirmation']['status']=='unavailable' for p in r['patterns']))
        e=confluence_evidence(r);self.assertTrue(e);self.assertEqual(len({x.bucket for x in e}),1);self.assertLessEqual(build_confluence(e)['deduplicated_evidence_count'],1)
    def test_decimal_context_and_repeated_detection_are_deterministic(self):
        b=bars([(105,106,95,96),(100,100.3,99.7,100)]);expected=detect(b)
        with localcontext() as ctx:
            ctx.prec=4;ctx.rounding=ROUND_DOWN;self.assertEqual(detect(b),expected)
    def test_configuration_resource_limits_and_catalog_honesty(self):
        for tick in ('NaN','Infinity','0','-1',True):
            with self.subTest(tick=tick),self.assertRaises(ValueError):detect_patterns(bars(),timeframe='1m',as_of_ms=32*TF,max_age_ms=TF,tick_size=tick)
        self.assertEqual(CATALOG['hikkake_modified']['status'],'MISSING');self.assertEqual(CATALOG['hikkake']['status'],'IMPLEMENTED')
        with self.assertRaises(ValueError):detect_patterns(bars()*300,timeframe='1m',as_of_ms=TF,max_age_ms=TF,tick_size='0.01')

    def test_stream_budget_is_enforced_before_materializing_entire_input(self):
        consumed=[]
        def source():
            for x in range(10000):consumed.append(x);yield bars()[0]
        with self.assertRaises(ValueError):detect_patterns(source(),timeframe='1m',as_of_ms=TF,max_age_ms=TF,tick_size='0.01')
        self.assertEqual(len(consumed),4097)
