from dataclasses import replace
from unittest import TestCase
from tests.test_v2_chart_research import base,chart
from tests.test_v2_pattern_research import TF

def flag(pennant=False,mirror=False):
    b=base(60)
    for j in range(41,52):
        price=100+(j-41)
        b[j]=replace(b[j],open=price-.2,high=price+.5,low=price-.5,close=price)
    for k,j in enumerate(range(52,60)):
        high=112-k*(.4 if not pennant else .5);low=108-k*.4 if not pennant else 105+k*.3
        mid=(high+low)/2;b[j]=replace(b[j],open=mid-.1,high=high,low=low,close=mid)
    if mirror:b=[replace(x,open=220-x.open,high=220-x.low,low=220-x.high,close=220-x.close) for x in b]
    return b

def append(b,close,low=None,high=None):
    return b+[replace(b[-1],open_time_ms=b[-1].close_time_ms,close_time_ms=b[-1].close_time_ms+TF,open=close,high=high if high is not None else close+.2,low=low if low is not None else close-.2,close=close)]
class ChartCompletionTests(TestCase):
    def test_flags_and_pennants_both_sides_closed_confirmation_delay(self):
        for pennant in (False,True):
            for mirrored in (False,True):
                b=flag(pennant,mirrored);name=('bear_' if mirrored else 'bull_')+('pennant' if pennant else 'flag')
                p=next(p for p in chart(b)['patterns'] if p['pattern_id']==name and p['formed_at']==60*TF)
                self.assertIsNone(p['confirmed_at']);self.assertEqual(p['known_at'],60*TF)
                b=append(b,111 if not mirrored else 109)
                p=next(p for p in chart(b)['patterns'] if p['pattern_id']==name and p['formed_at']==60*TF);self.assertIsNone(p['confirmed_at'])
                b=append(b,112 if not mirrored else 108)
                p=next(p for p in chart(b)['patterns'] if p['pattern_id']==name and p['formed_at']==60*TF)
                self.assertEqual(p['confirmed_at'],62*TF);self.assertFalse(p['trade_permission'])
    def test_no_pole_no_envelope_and_no_future_confirmation(self):
        b=flag();before=chart(b)
        self.assertFalse(any(p['pattern_id'] in ('bull_flag','bear_flag','bull_pennant','bear_pennant') for p in chart(base(60))['patterns']))
        b[55]=replace(b[55],high=130)
        self.assertFalse(any(p['pattern_id']=='bull_flag' and p['formed_at']==60*TF for p in chart(b)['patterns']))
        chart(append(flag(),120));self.assertEqual(before,chart(flag()))
    def test_double_neckline_requires_right_pivot_then_actual_closed_cross(self):
        b=base(65);b[45]=replace(b[45],high=110);b[57]=replace(b[57],high=110)
        self.assertFalse(any(p['pattern_id']=='double_top_neckline' for p in chart(b[:60])['patterns']))
        p=next(p for p in chart(b[:61])['patterns'] if p['pattern_id']=='double_top_neckline');self.assertIsNone(p['confirmed_at']);self.assertEqual(p['known_at'],61*TF)
        b=append(b,98)
        p=next(p for p in chart(b)['patterns'] if p['pattern_id']=='double_top_neckline');self.assertEqual(p['confirmed_at'],66*TF)
        mirrored=[replace(x,open=220-x.open,high=220-x.low,low=220-x.high,close=220-x.close) for x in b]
        self.assertTrue(any(p['pattern_id']=='double_bottom_neckline' and p['confirmed_at']==66*TF for p in chart(mirrored)['patterns']))
    def test_head_shoulders_sloped_neckline_and_unequal_shoulders_rejection(self):
        b=base(75)
        for i,high in ((45,110),(55,115),(65,110)):b[i]=replace(b[i],high=high)
        b[50]=replace(b[50],low=95);b[60]=replace(b[60],low=97)
        b=append(b,98)
        p=next(p for p in chart(b)['patterns'] if p['pattern_id']=='head_and_shoulders_neckline');self.assertEqual(p['known_at'],69*TF);self.assertEqual(p['confirmed_at'],76*TF)
        b[65]=replace(b[65],high=106)
        self.assertFalse(any(p['pattern_id']=='head_and_shoulders_neckline' for p in chart(b)['patterns']))
    def test_false_flag_breakout_has_actual_failure_time(self):
        b=append(append(flag(),111),106)
        p=next(p for p in chart(b)['patterns'] if p['pattern_id']=='failed_flag_breakout' and p['formed_at']==60*TF)
        self.assertEqual(p['known_at'],62*TF);self.assertEqual(p['confirmed_at'],62*TF)
        self.assertFalse(any(p['pattern_id']=='failed_flag_breakout' for p in chart(b[:-1])['patterns']))
    def test_formation_identity_is_stable_when_confirmation_arrives(self):
        b=flag();old=next(p for p in chart(b)['patterns'] if p['pattern_id']=='bull_flag' and p['formed_at']==60*TF)
        b=append(append(b,111),112)
        new=next(p for p in chart(b)['patterns'] if p['pattern_id']=='bull_flag' and p['formed_at']==60*TF)
        self.assertEqual(old['event_id'],new['event_id']);self.assertEqual(old['source_prefix_hash'],new['source_prefix_hash'])
    def test_flag_retest_requires_confirmation_and_real_boundary_touch(self):
        b=append(append(flag(),111),112);b=append(b,112,low=108,high=112.2)
        p=next(p for p in chart(b)['patterns'] if p['pattern_id']=='flag_retest' and p['formed_at']==60*TF)
        self.assertEqual(p['known_at'],63*TF);self.assertEqual(p['confirmed_at'],63*TF)
        b[-1]=replace(b[-1],low=109)
        self.assertFalse(any(p['pattern_id']=='flag_retest' and p['formed_at']==60*TF for p in chart(b)['patterns']))
