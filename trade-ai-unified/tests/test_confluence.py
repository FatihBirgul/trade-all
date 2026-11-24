import unittest
from unified_forex.confluence import Observation,combine


def observation(**changes):
    base=dict(source='independent-fixture',event_id='same-candle',category='trend',direction='bullish',
              strength=40.0,confirmed=True,age_bars=0,timeframe='M15',known_at=1000,algorithm_version='test-v1')
    return Observation(**{**base,**changes})


class TrueConfluence(unittest.TestCase):
    def test_same_event_different_categories_cannot_inflate_source_engine(self):
        rows=[observation(),observation(source='other',category='momentum',bucket='different')]
        result=combine(rows,as_of=1000)
        self.assertEqual(result['event_deduplicated_count'],1)
        self.assertEqual(result['deduplicated_evidence_count'],1)
        self.assertEqual(result['bullish_strength'],40)
        self.assertIsNone(result['success_probability'])

    def test_opposing_unequal_strength_is_not_hidden_by_bucket_winner(self):
        result=combine([observation(),observation(direction='bearish',strength=90.0)],as_of=1000)
        self.assertTrue(result['conflict_veto'])
        self.assertEqual(result['directional_context'],['bearish','bullish'])

    def test_future_unconfirmed_and_volatility_cannot_authorize_direction(self):
        rows=[observation(known_at=1001),observation(confirmed=False),observation(category='volatility',strength=100.0)]
        result=combine(rows,as_of=1000)
        self.assertEqual(result['direction'],'neutral')
        self.assertEqual(result['directional_context'],[])
