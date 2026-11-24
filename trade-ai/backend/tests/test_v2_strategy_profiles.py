"""Whitelisted versioned choices can narrow eligibility, never bypass risk."""
from dataclasses import replace
from unittest import TestCase
from market_ai.v2.strategy_profiles import StrategyProfile, evaluate_profile, validate_history
from market_ai.v2.research import run_backtest
from tests.test_v2_research import dataset, config

class StrategyProfileTests(TestCase):
    def test_valid_profile_is_versioned_and_permutation_canonical(self):
        a=StrategyProfile(required_methods=('roc12','adx14_wilder'))
        b=StrategyProfile(required_methods=('adx14_wilder','roc12'))
        self.assertEqual(a.profile_id,b.profile_id)
        self.assertEqual(StrategyProfile.from_dict(a.body()),a)
    def test_risk_fields_unknown_methods_types_duplicates_and_roles_are_rejected(self):
        for kw in ({'risk_limit':'1'},{'required_methods':('magic',)},{'minimum_confirmations':True},
                   {'required_methods':('roc12','roc12')},{'bias_timeframe':'1m','setup_timeframe':'1H','trigger_timeframe':'15m'},
                   {'allowed_regimes':('range',),'strategy_ids':('trend_momentum_v2',)}):
            with self.subTest(kw=kw),self.assertRaises((ValueError,TypeError)):StrategyProfile(**kw)
    def test_wait_bad_quality_or_risk_is_never_allowed_by_a_profile(self):
        p=StrategyProfile(required_methods=())
        r={'direction':'bullish','quality':{'ok':True},'risk':{'status':'eligible_for_paper'},
           'router':{'strategy_id':p.strategy_ids[0]},'strategy_setups':{p.strategy_ids[0]:{'version':p.body()['strategy_versions'][p.strategy_ids[0]]}},'regime':{'regime':'trend'},'supporting_evidence':[{'bucket':x,'confirmed':True} for x in ('trend','momentum')]}
        self.assertTrue(evaluate_profile(p,r,{'methods':{}})['passes'])
        for key,value in (('direction','WAIT'),('quality',{'ok':False}),('risk',{'status':'wait'})):
            z={**r,key:value};self.assertFalse(evaluate_profile(p,z,{'methods':{}})['passes'])
        self.assertFalse(evaluate_profile(p,r,{'methods':{}})['trade_permission'])
    def test_confirmation_counts_deduplicate_correlated_evidence(self):
        p=StrategyProfile(required_methods=())
        r={'direction':'bullish','quality':{'ok':True},'risk':{'status':'eligible_for_paper'},'router':{'strategy_id':p.strategy_ids[0]},'strategy_setups':{p.strategy_ids[0]:{'version':p.body()['strategy_versions'][p.strategy_ids[0]]}},'regime':{'regime':'trend'},'supporting_evidence':[{'bucket':'same','confirmed':True}]*5}
        self.assertFalse(evaluate_profile(p,r,{'methods':{}})['passes'])
    def test_revision_history_is_hash_linked_and_strict(self):
        first=StrategyProfile();second=replace(first,revision=2,parent_id=first.profile_id,minimum_confirmations=3)
        self.assertEqual(validate_history((first,second)),'PASS')
        with self.assertRaises(ValueError):validate_history((first,replace(second,parent_id='0'*64)))
        with self.assertRaises(ValueError):validate_history((first,first))
        with self.assertRaises(ValueError):StrategyProfile.from_dict({**first.body(),'authorization':'forbidden'})
    def test_research_profile_can_only_reduce_orders_and_is_bound_to_report(self):
        p=StrategyProfile(required_methods=('roc12',))
        r=run_backtest(dataset(),config(simulate_orders=True),profile=p)
        self.assertEqual(r['profile_id'],p.profile_id);self.assertEqual(r['integrity_status'],'PASS',r['audit']);self.assertEqual(r['orders'],1)
        q=replace(p,minimum_confirmations=5)
        blocked=run_backtest(dataset(),config(simulate_orders=True),profile=q)
        self.assertEqual(blocked['orders'],0);self.assertEqual(blocked['integrity_status'],'PASS')
    def test_profile_configuration_mismatch_fails_before_simulation(self):
        p=StrategyProfile(bias_timeframe='4H',setup_timeframe='1H',trigger_timeframe='15m')
        with self.assertRaises(ValueError):run_backtest(dataset(),config(),profile=p)
    def test_method_unavailability_cannot_be_promoted_to_confirmation(self):
        p=StrategyProfile(required_methods=('roc12',))
        r={'direction':'bullish','quality':{'ok':True},'risk':{'status':'eligible_for_paper'},'router':{'strategy_id':p.strategy_ids[0]},'strategy_setups':{p.strategy_ids[0]:{'version':p.body()['strategy_versions'][p.strategy_ids[0]]}},'regime':{'regime':'trend'},'supporting_evidence':[{'bucket':x,'confirmed':True} for x in ('trend','momentum')]}
        self.assertFalse(evaluate_profile(p,r,{'methods':{'roc12':{'status':'warmup'}}})['passes'])
        r['strategy_setups'][p.strategy_ids[0]]['version']='unsupported'
        self.assertEqual(evaluate_profile(p,r,{'methods':{'roc12':{'status':'available'}}})['reason'],'strategy_version_missing_or_mismatch')

    def test_profile_cli_revision_and_research_cli_binding(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from contextlib import redirect_stdout
        from io import StringIO
        import json
        from unittest.mock import patch
        from scripts.profile_v2 import main as create
        from scripts.research_v2 import main as research
        from market_ai.v2.strategy_profiles import load_profile
        from tests.test_v2_research import NOW,TF
        with TemporaryDirectory(prefix='v2-profile-') as root:
            a=Path(root)/'first.json';b=Path(root)/'second.json'
            with redirect_stdout(StringIO()):
                self.assertEqual(create(['--output',str(a)]),0)
                self.assertEqual(create(['--output',str(b),'--parent',str(a),'--confirmations','3']),0)
            self.assertEqual(validate_history((load_profile(a),load_profile(b))),'PASS')
            output=StringIO()
            with patch('scripts.research_v2.load_dataset',return_value=dataset()),redirect_stdout(output):
                code=research(['explicit-fixture.json','--profile',str(a),'--start-ms',str(NOW),'--end-ms',str(NOW+3*TF),'--paper'])
            r=json.loads(output.getvalue());self.assertEqual(code,0);self.assertEqual(r['profile_id'],load_profile(a).profile_id);self.assertEqual(r['orders'],1)
            before=a.read_bytes()
            with self.assertRaises(SystemExit):create(['--output',str(a)])
            self.assertEqual(a.read_bytes(),before)

    def test_existing_profile_freezes_strategy_versions_across_runtime_catalog_changes(self):
        from unittest.mock import patch
        from market_ai.v2.strategy_profiles import STRATEGIES
        p=StrategyProfile(required_methods=());identity=p.profile_id;body=p.body()
        newer=tuple(replace(s,version='future') for s in STRATEGIES)
        with patch('market_ai.v2.strategy_profiles.STRATEGIES',newer):
            self.assertEqual(p.profile_id,identity);self.assertEqual(p.body(),body)
            with self.assertRaises(ValueError):StrategyProfile.from_dict(body)
