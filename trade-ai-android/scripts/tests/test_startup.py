"""Regression tests for source identity and real aapt-shaped startup resource bags."""
import importlib.util,json,shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('startup_check',ROOT/'scripts/verify-startup.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
RESOURCE='''resource 0x7f060002 color/splashscreen_background
  () #ff111316
  (night) #ff111316
resource 0x7f120001 style/AppTheme
  () (style) size=1
    0x01010054=@color/splashscreen_background
resource 0x7f120002 style/Theme.App.SplashScreen
  () (style) size=5 parent=style/Theme.SplashScreen (0x7f120003)
    windowSplashScreenBackground=@color/splashscreen_background
    windowSplashScreenAnimatedIcon=@drawable/splashscreen_logo
    postSplashScreenTheme=@style/AppTheme
    0x010104e0=false
    0x0101056c=false
'''
MANIFEST='''E: manifest
  E: application
    E: activity
      A: android:name="com.fatihbirgul.tradeai.MainActivity"
      A: android:theme=@0x7f120002
'''
class StartupTests(unittest.TestCase):
 def test_source_is_dark_and_original_launcher_assets_are_unchanged(self):self.assertEqual(v.source(ROOT)['brand_identity'],'unchanged')
 def test_white_day_or_night_config_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);shutil.copytree(ROOT/'assets',p/'assets')
   for name in ('app.json','package.json'):shutil.copyfile(ROOT/name,p/name)
   c=json.loads((p/'app.json').read_text());s=next(x[1] for x in c['expo']['plugins'] if isinstance(x,list) and x[0]=='expo-splash-screen');s['dark']['backgroundColor']='#FFFFFF';(p/'app.json').write_text(json.dumps(c))
   with self.assertRaises(AssertionError):v.source(p)
 def test_compiled_dark_theme_and_real_launch_reference(self):
  with patch.object(v.subprocess,'check_output',side_effect=[RESOURCE,MANIFEST]):self.assertTrue(v.apk('fixture.apk','fixture-aapt')['compiled_android12_theme'])
 def test_compiled_white_background_or_wrong_main_activity_theme_fails(self):
  for resource,manifest in [(RESOURCE.replace('#ff111316','#ffffffff',1),MANIFEST),(RESOURCE,MANIFEST.replace('@0x7f120002','@0x7f120001'))]:
   with patch.object(v.subprocess,'check_output',side_effect=[resource,manifest]):
    with self.assertRaises(AssertionError):v.apk('fixture.apk','fixture-aapt')
 def test_post_splash_window_cannot_revert_to_default_white(self):
  with patch.object(v.subprocess,'check_output',side_effect=[RESOURCE.replace('0x01010054=@color/splashscreen_background','0x01010054=#ffffffff'),MANIFEST]):
   with self.assertRaises(AssertionError):v.apk('fixture.apk','fixture-aapt')
 def test_reversed_native_plugin_order_cannot_silently_erase_dark_window_overrides(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);shutil.copytree(ROOT/'assets',p/'assets')
   for name in ('app.json','package.json'):shutil.copyfile(ROOT/name,p/name)
   c=json.loads((p/'app.json').read_text());plugins=c['expo']['plugins'];plugins.remove('./plugins/withLaunchWindow.cjs');plugins.append('./plugins/withLaunchWindow.cjs');(p/'app.json').write_text(json.dumps(c))
   with self.assertRaises(AssertionError):v.source(p)
if __name__=='__main__':unittest.main()
