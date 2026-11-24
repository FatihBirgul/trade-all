"""Content integrity is distinct from license and historical rule evidence."""
from dataclasses import replace
from unittest import TestCase
from tests.test_v2_research import dataset, NOW, TF, RULES
from market_ai.v2.research import HistoricalDataset
from market_ai.v2.historical_provenance import Manifest, capture_history, verify_manifest, digest
from market_ai.v2.spot_provider import ProviderUnavailable

class Provider:
    name='binance_public_spot';venue='binance';mode='live';source_name='binance_spot'
    def __init__(self):
        b=dataset().frames['1m'];identity=replace(b[0].instrument,venue='binance')
        self.bars=[replace(x,instrument=identity,source='binance_spot') for x in b];self.calls=[]
    def rules(self,symbol):return {**RULES,'source':'binance_exchange_info'}
    def candle_window(self,symbol,start,end):
        self.calls.append((start,end));return [b for b in self.bars if b.open_time_ms>=start and b.close_time_ms<=end]

class HistoricalProvenanceTests(TestCase):
    def capture(self,p=None):
        p=p or Provider();b=p.bars
        return capture_history(p,'BTCUSDT',b[0].open_time_ms,b[-1].close_time_ms,as_of_ms=NOW+10*TF)
    def test_missing_manifest_and_current_rules_are_incomplete_not_trusted(self):
        self.assertEqual(verify_manifest(dataset(),None)['status'],'INCOMPLETE')
        d,m=self.capture();r=verify_manifest(d,m)
        self.assertEqual(r['status'],'INCOMPLETE',r)
        self.assertEqual(d.data_kind,'historical');self.assertFalse(r['market_performance_verified'])
        self.assertIn('historical_rules_missing',{x['code'] for x in r['checks']})
    def test_paged_capture_is_exact_and_preserves_venue_and_closed_times(self):
        p=Provider();d,m=self.capture(p)
        self.assertEqual(len(p.calls),2);self.assertEqual(len(d.frames['1m']),303)
        self.assertEqual(d.identity.venue,'binance');self.assertEqual(m.body()['dataset_digest'],d.digest)
        self.assertIsNone(m.body()['raw_payload_sha256'])
    def test_hash_identity_and_cost_mismatches_are_detected(self):
        d,m=self.capture()
        for field,value in (('dataset_digest','0'*64),('venue','other')):
            body=m.body();body[field]=value
            self.assertEqual(verify_manifest(d,Manifest(body))['status'],'MISMATCH')
        self.assertEqual(verify_manifest(d,m,costs={'fee_bps':'10','spread_bps':'2','slippage_bps':'1'})['status'],'MISMATCH')
    def test_archived_rule_declaration_covers_only_its_effective_interval(self):
        d,m=self.capture();body=m.body();first,last=d.frames['1m'][0],d.frames['1m'][-1]
        body['rules']=[{'kind':'ARCHIVED_REVIEWED','effective_from_ms':first.open_time_ms,'effective_to_ms':last.close_time_ms,
                        'observed_at_ms':NOW+10*TF,'rules_digest':digest(dict(d.rules)),
                        'evidence_sha256':'a'*64,'reference':'https://example.org/fixture-rule-evidence'}]
        r=verify_manifest(d,Manifest(body))
        check=next(x for x in r['checks'] if x['code']=='historical_rules_missing');self.assertEqual(check['status'],'PASS')
        self.assertEqual(r['status'],'INCOMPLETE') # model costs and license still unverified
        body['rules'][0]['effective_to_ms']=last.open_time_ms
        self.assertEqual(next(x for x in verify_manifest(d,Manifest(body))['checks'] if x['code']=='historical_rules_missing')['status'],'INCOMPLETE')
    def test_manifest_rejects_unknown_fields_versions_and_sensitive_reference_shapes(self):
        _,m=self.capture()
        for update in ({'schema_version':True},{'token':'forbidden'},{'license_reference':'https://user:secret@example.org/a'},{'license_reference':'https://example.org/?token=secret'}):
            body=m.body();body.update(update)
            with self.subTest(update=update),self.assertRaises(ValueError):Manifest(body)
    def test_outage_gap_duplicate_and_wrong_source_never_return_partial_dataset(self):
        for fault in ('outage','gap','duplicate','source'):
            p=Provider();original=p.candle_window
            def broken(symbol,start,end):
                rows=original(symbol,start,end)
                if len(p.calls)==2:
                    if fault=='outage':raise ProviderUnavailable('controlled source outage')
                    if fault=='gap':return rows[1:]
                    if fault=='duplicate':return rows+[rows[-1]]
                    return [replace(x,source='foreign') for x in rows]
                return rows
            p.candle_window=broken
            with self.subTest(fault=fault),self.assertRaises((ValueError,ProviderUnavailable)):self.capture(p)
    def test_capture_rejects_future_unaligned_or_excessive_requests(self):
        p=Provider()
        for start,end,asof in ((0,1300*TF,2000*TF),(1,301*TF,400*TF),(0,300*TF,299*TF)):
            with self.assertRaises(ValueError):capture_history(p,'BTCUSDT',start,end,as_of_ms=asof)

    def test_capture_files_are_exclusive_roundtrip_and_failure_cleans_only_owned_outputs(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from unittest.mock import patch
        from market_ai.v2.research import load_dataset
        from market_ai.v2.historical_provenance import write_capture
        d,m=self.capture()
        with TemporaryDirectory(prefix='v2-capture-') as root:
            a=Path(root)/'data.json';b=Path(root)/'manifest.json'
            write_capture(d,m,a,b);self.assertEqual(load_dataset(a).digest,d.digest)
            before=a.read_bytes()
            with self.assertRaises(FileExistsError):write_capture(d,m,a,b)
            self.assertEqual(a.read_bytes(),before)
            c=Path(root)/'new.json';z=Path(root)/'fail.json';original=Path.open
            def fail_second(path,*args,**kwargs):
                if path==z:raise OSError('controlled write failure')
                return original(path,*args,**kwargs)
            with patch.object(Path,'open',new=fail_second),self.assertRaises(OSError):write_capture(d,m,c,z)
            self.assertFalse(c.exists());self.assertEqual(a.read_bytes(),before)

    def test_manifest_file_rejects_duplicate_keys_and_is_bounded(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from market_ai.v2.historical_provenance import load_manifest
        with TemporaryDirectory(prefix='v2-manifest-json-') as root:
            p=Path(root)/'m.json';p.write_text('{"schema_version":1,"schema_version":1}')
            with self.assertRaises(ValueError):load_manifest(p)
            p.write_text(' '*262145)
            with self.assertRaises(ValueError):load_manifest(p)
