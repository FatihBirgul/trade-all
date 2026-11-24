import importlib.util,unittest,json,shutil,tempfile,zipfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('brand',ROOT/'scripts/verify-brand.py');brand=importlib.util.module_from_spec(spec);spec.loader.exec_module(brand)
class BrandTests(unittest.TestCase):
 def test_source_is_bound_to_real_svg_png_and_config(self):self.assertEqual(brand.verify_source(ROOT)['version'],'trade-ai-t-1')
 def test_changed_source_without_reviewed_manifest_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);shutil.copytree(ROOT/'assets',p/'assets');shutil.copyfile(ROOT/'app.json',p/'app.json');(p/'assets/brand/icon.png').write_bytes(b'wrong icon')
   with self.assertRaises(AssertionError):brand.verify_source(p)
 def test_native_missing_layer_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'app/src/main';(p/'res/mipmap-anydpi-v26').mkdir(parents=True)
   (p/'AndroidManifest.xml').write_text('<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application android:icon="@mipmap/ic_launcher" android:roundIcon="@mipmap/ic_launcher_round"/></manifest>')
   for name in ('ic_launcher','ic_launcher_round'):(p/'res/mipmap-anydpi-v26'/f'{name}.xml').write_text('<adaptive-icon/>')
   with self.assertRaises(AssertionError):brand.verify_native(Path(d))
 def test_actual_apk_graph_requires_correct_layers_not_just_names(self):
  resources='\n'.join(f'    resource 0x7f0d000{i} mipmap/ic_launcher'+('_'+name if name else '')+'\n      (v26) (file) '+('res/launcher.xml' if not name else 'res/icon.webp')+' type=XML' for i,name in enumerate(('', 'foreground','background','monochrome')))
  correct='E: adaptive-icon\n  E: foreground\n    A: android:drawable=@0x7f0d0001\n  E: background\n    A: android:drawable=@0x7f0d0002\n  E: monochrome\n    A: android:drawable=@0x7f0d0003'
  with tempfile.TemporaryDirectory() as d:
   apk=Path(d)/'fixture.apk'
   with zipfile.ZipFile(apk,'w') as z:z.writestr('res/launcher.xml','controlled compiled XML placeholder')
   with patch.object(brand.subprocess,'check_output',side_effect=[resources,correct]):brand.verify_apk(apk,'fixture-aapt')
   swapped=correct.replace('@0x7f0d0001','@0x7f0d0002',1)
   with patch.object(brand.subprocess,'check_output',side_effect=[resources,swapped]):
    with self.assertRaises(AssertionError):brand.verify_apk(apk,'fixture-aapt')
if __name__=='__main__':unittest.main()
