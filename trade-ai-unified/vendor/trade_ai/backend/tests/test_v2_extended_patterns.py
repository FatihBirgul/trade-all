"""New candle families: positive/negative, exact boundary and causal expiry."""
from dataclasses import replace
from unittest import TestCase
from tests.test_v2_pattern_research import bars, detect, TF


def match(result,family,formed_at=None):
    return next(p for p in result['patterns'] if p['family']==family and (formed_at is None or p['formed_at']==formed_at))

class ExtendedPatternTests(TestCase):
    def test_hikkake_requires_inside_then_false_break_and_later_extreme_cross(self):
        tail=[(100,110,90,100),(100,106,94,101),(99,105,93,94)]
        for mirror in (False,True):
            t=tail if not mirror else [(200-o,200-l,200-h,200-c) for o,h,l,c in tail]
            b=bars(t);p=match(detect(b),'hikkake');self.assertIsNone(p['confirmed_at']);formed=p['formed_at']
            nxt=(104,108,100,107) if not mirror else (96,100,92,93)
            z=replace(b[-1],open_time_ms=b[-1].close_time_ms,close_time_ms=b[-1].close_time_ms+TF,open=nxt[0],high=nxt[1],low=nxt[2],close=nxt[3])
            q=match(detect(b+[z]),'hikkake',formed);self.assertEqual(q['confirmed_at'],z.close_time_ms)
            self.assertEqual(q['direction'],'bearish' if mirror else 'bullish');self.assertIsNone(match(detect(b),'hikkake')['confirmed_at'])
    def test_hikkake_equality_is_not_confirmation_and_fourth_bar_is_too_late(self):
        b=bars([(100,110,90,100),(100,106,94,101),(99,105,93,94)])
        formed=b[-1].close_time_ms
        for i,close in enumerate((106,105,105,107)):
            b.append(replace(b[-1],open_time_ms=formed+i*TF,close_time_ms=formed+(i+1)*TF,open=104,high=max(107,close),low=103,close=close))
        p=match(detect(b),'hikkake',formed);self.assertIsNone(p['confirmed_at']);self.assertEqual(p['quality_status'],'confirmation_expired')
    def test_hikkake_without_inside_bar_does_not_exist(self):
        r=detect(bars([(100,110,90,100),(100,111,94,101),(99,105,93,94)]))
        self.assertNotIn('hikkake',{p['family'] for p in r['patterns']})
    def test_ladder_and_mat_hold_intrinsic_confirmation_and_mirrors(self):
        cases={
            'ladder_bottom':[(110,111,99,100),(105,106,94,95),(100,101,89,90),(92,99,87,91),(94,102,93,101)],
            'mat_hold':[(100,111,99,110),(112,113,108,109),(110,111,107,108),(109,110,106,107),(108,115,107,114)]}
        for family,tail in cases.items():
            for mirror in (False,True):
                t=tail if not mirror else [(220-o,220-l,220-h,220-c) for o,h,l,c in tail]
                b=bars(t);wanted='ladder_top' if family=='ladder_bottom' and mirror else family
                p=match(detect(b),wanted);self.assertEqual(p['confirmed_at'],b[-1].close_time_ms)
                self.assertEqual(p['direction'],'bearish' if mirror else 'bullish')
                self.assertNotIn(wanted,{p['family'] for p in detect(b[:-1])['patterns'] if p['formed_at']==b[-1].close_time_ms})
    def test_mat_hold_breaking_first_body_midpoint_is_rejected(self):
        tail=[(100,111,99,110),(112,113,108,109),(110,111,104,108),(109,110,106,107),(108,115,107,114)]
        self.assertNotIn('mat_hold',{p['family'] for p in detect(bars(tail))['patterns']})
    def test_concealing_baby_needs_confirmation_above_formation_high(self):
        b=bars([(110,110,100,100),(100,100,90,90),(88,95,84,85),(96,97,82,83)])
        p=match(detect(b),'concealing_baby_swallow');self.assertIsNone(p['confirmed_at']);formed=p['formed_at']
        z=replace(b[-1],open_time_ms=formed,close_time_ms=formed+TF,open=94,high=101,low=93,close=96)
        self.assertIsNone(match(detect(b+[z]),'concealing_baby_swallow',formed)['confirmed_at'])
        z=replace(z,close=100);self.assertEqual(match(detect(b+[z]),'concealing_baby_swallow',formed)['confirmed_at'],z.close_time_ms)
    def test_no_full_second_body_or_missing_gap_rejects_concealing_baby(self):
        b=bars([(110,110,100,100),(100,101,89,90),(88,95,84,85),(96,97,82,83)])
        self.assertNotIn('concealing_baby_swallow',{p['family'] for p in detect(b)['patterns']})
