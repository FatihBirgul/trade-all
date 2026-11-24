import unittest,os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from types import SimpleNamespace
from unified_forex.ingestion import _read,bounded_json,_signature


class FileRaceBoundary(unittest.TestCase):
    def test_windows_cross_api_ctime_difference_is_not_same_handle_mutation(self):
        a=SimpleNamespace(st_dev=1,st_ino=2,st_size=3,st_mtime_ns=4,st_ctime_ns=5)
        b=SimpleNamespace(st_dev=1,st_ino=2,st_size=3,st_mtime_ns=4,st_ctime_ns=6)
        self.assertEqual(_signature(a,cross_path=True,platform='nt'),_signature(b,cross_path=True,platform='nt'))
        self.assertNotEqual(_signature(a),_signature(b))
    def test_same_size_mutation_is_rejected_after_read(self):
        with TemporaryDirectory() as d:
            p=Path(d,'x.json');p.write_text('[]');real=os.fstat
            seen={}
            def changing(fd):
                info=real(fd)
                if not __import__('stat').S_ISREG(info.st_mode):return info
                seen[fd]=seen.get(fd,0)+1
                if seen[fd]==2:
                    fields={k:getattr(info,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode')}
                    fields['st_mtime_ns']+=1;return SimpleNamespace(**fields)
                return info
            with patch('unified_forex.ingestion.os.fstat',side_effect=changing):
                with self.assertRaisesRegex(ValueError,'changed'):_read(d,'x.json')
    def test_json_nesting_duplicate_keys_and_strict_boundary_refusal(self):
        self.assertEqual(bounded_json('{"literal":"[{}]"}'),{'literal':'[{}]'})
        for raw in ('['*33+'0'+']'*33,'{"a":1,"a":2}','[NaN]'):
            with self.assertRaises(ValueError):bounded_json(raw)
        with TemporaryDirectory() as d:
            Path(d,'x.json').write_text('[]')
            with patch('unified_forex.ingestion.os.supports_dir_fd',set()):
                with self.assertRaisesRegex(ValueError,'Descriptor boundary unavailable'):_read(d,'x.json',require_descriptor=True)
