import unittest,json,csv,io
from pathlib import Path
from tempfile import TemporaryDirectory
from copy import deepcopy
from datetime import datetime,timezone
from fixtures import META
from unified_forex.ingestion import import_file


class LocalHistoricalImport(unittest.TestCase):
    def request(self):
        return dict(dataset_id='handmade-public-domain-test',symbol='XAUUSD',market='cfd',contract_type='cfd',venue='synthetic-broker',
            broker_symbol=META['broker_symbol'],source='handmade-test',timeframe='15m',price_basis='bid',data_kind='synthetic',
            data_version='golden1',acquisition={'retrieved_at':'2026-01-02T00:00:00Z','license_declaration':'CC0 handmade synthetic test, no market data'},
            rules={**deepcopy(META),'source':'handmade-test'})
    def test_csv_json_normalization_and_explicit_unverified_trust(self):
        path=Path(__file__).parent/'data'
        a,ma=import_file(path,'v8_handmade.csv',self.request())
        self.assertEqual(len(a.frames['15m']),4);self.assertEqual(a.frames['15m'][0].close,2001)
        rows=list(csv.DictReader(io.StringIO((path/'v8_handmade.csv').read_text())))
        for row in rows:
            for k in ('open_time_ms','close_time_ms'):row[k]=int(row[k])
            for k in ('open','high','low','close'):row[k]=float(row[k])
            row['is_final']=True
        with TemporaryDirectory() as temp:
            Path(temp,'bars.json').write_text(json.dumps(rows))
            b,mb=import_file(temp,'bars.json',self.request())
        self.assertEqual(a.digest,b.digest);self.assertNotEqual(ma['raw_file_sha256'],mb['raw_file_sha256'])
        self.assertEqual(ma['manifest']['trust'],'SYNTHETIC_TEST')
    def test_traversal_symlink_archives_size_hash_and_duplicate_keys(self):
        with TemporaryDirectory() as temp:
            p=Path(temp);p.joinpath('file.zip').write_bytes(b'archive')
            for name in ('../secret','..\\secret','/etc/passwd','C:\\secret.csv','\\\\server\\share\\data.csv','C:relative.csv','file.csv:stream','file.zip'):
                with self.assertRaises(ValueError):import_file(p,name,self.request())
            p.joinpath('huge.csv').write_bytes(b'x'*8_000_001)
            with self.assertRaises(ValueError):import_file(p,'huge.csv',self.request())
            p.joinpath('dup.json').write_text('[{"open":1,"open":2}]')
            with self.assertRaises(ValueError):import_file(p,'dup.json',self.request())
            from unittest.mock import patch
            with patch('pathlib.Path.is_symlink',return_value=True):
                with self.assertRaisesRegex(ValueError,'Symlink'):import_file(p,'dup.json',self.request())
            p.joinpath('file.parquet').write_bytes(b'PAR1')
            with self.assertRaisesRegex(ValueError,'PARQUET_UNAVAILABLE'):import_file(p,'file.parquet',self.request())
        root=Path(__file__).parent/'data';req=self.request();req['expected_raw_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'hash mismatch'):import_file(root,'v8_handmade.csv',req)
    def test_corrupt_future_unclosed_identity_and_gap_rejected(self):
        raw=(Path(__file__).parent/'data/v8_handmade.csv').read_text()
        changes=[raw.replace('2000,2002,1999,2001','2000,1998,1999,2001'),raw.replace('true','false'),
                 raw.replace('handmade-test','wrong-source'),raw.replace('2000,2002','NaN,2002'),
                 '\n'.join(raw.splitlines()[:2]+raw.splitlines()[3:]),
                 '\n'.join(raw.splitlines()[:2]+raw.splitlines()[1:])]
        with TemporaryDirectory() as temp:
            for text in changes:
                Path(temp,'bad.csv').write_text(text)
                with self.assertRaises(ValueError):import_file(temp,'bad.csv',self.request())
        with self.assertRaisesRegex(ValueError,'Future acquisition'):
            import_file(Path(__file__).parent/'data','v8_handmade.csv',self.request(),as_of=datetime(2025,1,1,tzinfo=timezone.utc))
