"""Verify source + generated/compiled native startup resources; not a device test."""
import argparse, hashlib, json, re, subprocess
from pathlib import Path
from xml.etree import ElementTree as E
BG='#111316'
# Existing 0.7.6 identity is pinned, not regenerated for this UX change.
BASE_BRAND_MANIFEST='17075640400b91bba8ca39ccd8b43d3cca0c20ec0ab7766a07e6d110cbb78320'
A='{http://schemas.android.com/apk/res/android}'
def source(root):
 root=Path(root);c=json.loads((root/'app.json').read_text())['expo'];p=json.loads((root/'package.json').read_text());m=root/'assets/brand/manifest.json'
 assert hashlib.sha256(m.read_bytes()).hexdigest()==BASE_BRAND_MANIFEST,'Existing brand manifest changed'
 for name,digest in json.loads(m.read_text())['files'].items():assert hashlib.sha256((m.parent/name).read_bytes()).hexdigest()==digest,'Existing logo changed'
 plugins={x[0]:x[1] for x in c['plugins'] if isinstance(x,list)};s=plugins['expo-splash-screen'];assert 'expo-splash-screen' in p['dependencies']
 assert s['backgroundColor']==s['dark']['backgroundColor']==c['backgroundColor']==BG
 assert s['image']==s['dark']['image']=='./assets/brand/adaptive-foreground.png' and s['imageWidth']==176 and s['resizeMode']=='contain'
 assert c['plugins'].index('./plugins/withLaunchWindow.cjs') < next(i for i,x in enumerate(c['plugins']) if isinstance(x,list) and x[0]=='expo-splash-screen'),'Launch style override must execute after Expo splash style generation'
 assert plugins['expo-navigation-bar']=={'enforceContrast':False,'style':'light','hidden':False}
 assert c['androidStatusBar']['barStyle']=='light-content'
 return {'source_background':BG,'brand_identity':'unchanged','splash_image':s['image'],'image_width_dp':176,'native_visual':'UNVERIFIED'}
def native(path):
 root=Path(path)/'app/src/main';res=root/'res'
 for folder in ('values','values-night'):
  colors={n.get('name'):n.text for n in E.parse(res/folder/'colors.xml').getroot()};assert colors['splashscreen_background'].lower()==BG
 styles={s.get('name'):s for s in E.parse(res/'values/styles.xml').getroot().findall('style')};s=styles['Theme.App.SplashScreen'];assert s.get('parent')=='Theme.SplashScreen'
 items={i.get('name'):i.text for i in s};assert items['windowSplashScreenBackground']=='@color/splashscreen_background';assert items['windowSplashScreenAnimatedIcon']=='@drawable/splashscreen_logo';assert items['postSplashScreenTheme']=='@style/AppTheme'
 assert items['android:windowLightStatusBar']==items['android:windowLightNavigationBar']=='false'
 assert {i.get('name'):i.text for i in styles['AppTheme']}['android:windowBackground']=='@color/splashscreen_background'
 manifest=E.parse(root/'AndroidManifest.xml').getroot();activity=manifest.find('application/activity');assert activity.get(A+'theme')=='@style/Theme.App.SplashScreen'
 kt=(root/'java/com/fatihbirgul/tradeai/MainActivity.kt').read_text();assert kt.index('SplashScreenManager.registerOnActivity(this)')<kt.index('super.onCreate(null)')
 pngs=list(res.glob('drawable-*/splashscreen_logo.png'));assert len(pngs)==10
 for p in pngs:assert p.read_bytes().startswith(b'\x89PNG')
 return {'native_background_day_and_night':BG,'generated_splash_pngs':len(pngs),'native_manager_registered':True}
def blocks(s):
 return {m[2].split(':')[-1]:(m[1],m[3]) for m in re.finditer(r'resource (0x[\da-fA-F]+) (\S+)\n(.*?)(?=\n\s*resource |\Z)',s,re.S)}
def apk(path,aapt):
 b=blocks(subprocess.check_output([aapt,'dump','resources',str(path)],text=True));color=b['color/splashscreen_background'][1];values=re.findall(r'#([\da-fA-F]{6,8})',color);assert values and all(x.lower()=='ff111316' for x in values),'Compiled splash is not dark in every configuration'
 theme=b['style/Theme.App.SplashScreen'][1];assert 'parent=style/Theme.SplashScreen ' in theme
 for ref in ('@color/splashscreen_background','@drawable/splashscreen_logo','@style/AppTheme'):assert ref in theme,'Missing compiled startup reference '+ref
 app=b['style/AppTheme'][1];assert '0x01010054=@color/splashscreen_background' in app,'Post-splash window background missing'
 assert '0x010104e0=false' in theme and '0x0101056c=false' in theme,'Launch system bars must use light content'
 manifest=subprocess.check_output([aapt,'dump','xmltree',str(path),'--file','AndroidManifest.xml'],text=True)
 assert any('com.fatihbirgul.tradeai.MainActivity' in part and b['style/Theme.App.SplashScreen'][0].lower() in part.lower() for part in manifest.split('E: activity')[1:]),'MainActivity launch splash theme not referenced'
 return {'compiled_splash_backgrounds':values,'compiled_android12_theme':True,'post_splash_window_background':BG,'compiled_splash_asset_reference':True,'native_visual':'UNVERIFIED'}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--native',type=Path);p.add_argument('--apk',type=Path);p.add_argument('--aapt');p.add_argument('--output',type=Path);a=p.parse_args();r=source(a.root)
 if a.native:r.update(native(a.native))
 if a.apk:
  assert a.aapt;r.update(apk(a.apk,a.aapt))
 if a.output:a.output.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
 print('PASS startup resource checks '+json.dumps(r,sort_keys=True))
if __name__=='__main__':main()
