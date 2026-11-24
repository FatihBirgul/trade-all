"""Source/native/APK icon graph verification; no physical-device claim."""
import argparse,hashlib,json,re,struct,subprocess,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
ANDROID='{http://schemas.android.com/apk/res/android}'
def verify_source(root):
 root=Path(root);brand=root/'assets/brand';manifest=json.loads((brand/'manifest.json').read_text());config=json.loads((root/'app.json').read_text())['expo']
 expected={'foregroundImage':'./assets/brand/adaptive-foreground.png','backgroundImage':'./assets/brand/adaptive-background.png','monochromeImage':'./assets/brand/adaptive-monochrome.png'}
 assert config['icon']=='./assets/brand/icon.png'
 assert config['android']['adaptiveIcon']['backgroundColor']=='#111316'
 assert all(config['android']['adaptiveIcon'].get(k)==v for k,v in expected.items())
 for name,digest in manifest['files'].items():
  data=(brand/name).read_bytes();assert hashlib.sha256(data).hexdigest()==digest,'Brand source checksum mismatch: '+name
  if name.endswith('.png'):assert data[:8]==b'\x89PNG\r\n\x1a\n' and struct.unpack('>II',data[16:24])==(1024,1024)
  if name.endswith('.svg'):
   tree=ET.fromstring(data);assert not any(n.tag.rsplit('}',1)[-1] in ('text','image','script','foreignObject') for n in tree.iter())
 return manifest

def verify_native(path):
 root=Path(path)/'app/src/main';app=ET.parse(root/'AndroidManifest.xml').getroot().find('application')
 assert app is not None and app.get(ANDROID+'icon')=='@mipmap/ic_launcher'
 assert app.get(ANDROID+'roundIcon')=='@mipmap/ic_launcher_round'
 files=list((root/'res').glob('mipmap-anydpi*/ic_launcher*.xml'));assert len(files)>=2
 for file in files:
  tree=ET.parse(file).getroot();assert tree.tag=='adaptive-icon'
  for tag in ('background','foreground','monochrome'):
   node=tree.find(tag);assert node is not None,'Adaptive layer missing: '+tag
   ref=node.get(ANDROID+'drawable');match=re.fullmatch(r'@(mipmap|drawable)/(\w+)',ref or '');assert match,'Missing adaptive drawable reference'
   images=[p for p in (root/'res').glob(match[1]+'*/'+match[2]+'.*') if p.suffix in ('.png','.webp')];assert images,'Adaptive raster layer missing: '+ref
   for image in images:
    raw=image.read_bytes();assert raw.startswith(b'\x89PNG') or raw[:4]==b'RIFF' and raw[8:12]==b'WEBP','Invalid native icon raster'
 print('PASS native launcher + round/adaptive foreground/background/monochrome references')

def resource_blocks(text):
 return {m.group(2):(m.group(1),m.group(3)) for m in re.finditer(r'resource (0x[0-9a-fA-F]+) (?:[\w.]+:)?(mipmap/\w+)\s*\n(.*?)(?=\n\s*resource |\Z)',text,re.S)}

def verify_apk(apk,aapt):
 resources=subprocess.check_output([aapt,'dump','resources',str(apk)],text=True);blocks=resource_blocks(resources)
 expected={name:blocks['mipmap/ic_launcher_'+name][0] for name in ('foreground','background','monochrome')}
 launcher=blocks['mipmap/ic_launcher'][1];xmls=set(re.findall(r'(res/[^\s]+\.xml)',launcher));assert xmls,'Packaged adaptive icon XML missing'
 with zipfile.ZipFile(apk) as z:
  assert z.testzip() is None
  for name in xmls:
   assert name in z.namelist()
   tree=subprocess.check_output([aapt,'dump','xmltree',str(apk),'--file',name],text=True)
   assert 'adaptive-icon' in tree
   for tag,ref in expected.items():
    section=re.search(r'E: '+tag+r'\b(.*?)(?=\n\s*E:|\Z)',tree,re.S)
    assert section and ref.lower() in section[1].lower(),'Packaged adaptive reference missing or crossed: '+tag
 print('PASS actual APK adaptive XML references packaged foreground/background/monochrome IDs')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--native',type=Path);p.add_argument('--apk',type=Path);p.add_argument('--aapt');a=p.parse_args();verify_source(a.root);print('PASS brand source hashes,1024 PNGs and configured icon paths')
 if a.native:verify_native(a.native)
 if a.apk:
  assert a.aapt,'--aapt required for actual APK resource graph';verify_apk(a.apk,a.aapt)
if __name__=='__main__':main()
