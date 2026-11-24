from unittest import TestCase
from unittest.mock import patch
from tempfile import TemporaryDirectory
from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO
import json
from market_ai.v2.indicator_parameters import VERSION,versions
from tests.test_v2_walk_forward import data
from scripts.walk_forward_v2 import main,load_indicator_candidates

def protocol(d):return {'schema_version':1,'implementation_version':VERSION,'strategy_versions':dict(versions()),'dataset_digest':d.digest,'source':d.source,'candidates':[{'candidate_id':'ema-8','analysis_every_bars':10,'parameters':{'ema_period':8,'confirmation_filter':'none'}}]}
class ParameterProtocolCLITests(TestCase):
 def test_actual_offline_frozen_candidate_execution_and_source_version_binding(self):
  d=data()
  with TemporaryDirectory() as root:
   path=Path(root)/'protocol.json';path.write_text(json.dumps(protocol(d)))
   output=StringIO()
   with patch('scripts.walk_forward_v2.load_dataset',return_value=d),redirect_stdout(output):
    code=main(['synthetic.json','--parameter-candidates',str(path),'--train-bars','303','--test-bars','3','--horizon','1','--purge','1','--max-folds','1','--paper'])
   r=json.loads(output.getvalue());self.assertEqual(code,0);self.assertEqual(r['validation_status'],'OOS_EVALUATED')
   self.assertEqual(r['folds'][0]['frozen_parameters']['candidate']['parameters']['ema_period'],8)
   for changed in ({'dataset_digest':'0'*64},{'source':'other'},{'implementation_version':'future'},{'schema_version':True},{'strategy_versions':{}}):
    path.write_text(json.dumps({**protocol(d),**changed}))
    with self.assertRaises(ValueError):load_indicator_candidates(path,d)
 def test_duplicate_unknown_boolean_nan_and_oversized_protocols_rejected(self):
  d=data()
  with TemporaryDirectory() as root:
   p=Path(root)/'bad.json'
   samples=['{"schema_version":1,"schema_version":1}', ' '*16385]
   for parameters in ({'ema_period':True},{'risk_override':True},{'supertrend_multiplier':float('nan')},{'ema_period':999}):
    b=protocol(d);b['candidates'][0]['parameters']=parameters;samples.append(json.dumps(b))
   for raw in samples:
    p.write_text(raw)
    with self.assertRaises((ValueError,TypeError)):load_indicator_candidates(p,d)
