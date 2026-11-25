"""Verify actual native metadata/signature; emit public build evidence, no keys."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile
REFERENCE_CERT='fac61745dc0903786fb9ede62a962b399f7348f0bb6f899b8332667591033b9c'

def digest(stream):
    h=hashlib.sha256()
    for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def inspect(apk,config,badging,signature,commit,release_signed=False):
    if not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('Exact source SHA required')
    package=re.search(r"^package: name='([^']+)' versionCode='([0-9]+)' versionName='([^']*)'",badging,re.M)
    if package is None:raise ValueError('Native package metadata missing')
    identity,code,version=package.groups();code=int(code)
    if identity!='com.fatihbirgul.tradeai' or identity!=config['android']['package'] or code!=config['android']['versionCode'] or version!=config['version']:
        raise ValueError('Actual APK and source configuration mismatch')
    if 'Verified using v2 scheme (APK Signature Scheme v2): true' not in signature:raise ValueError('Verified V2 signature required for this internal APK')
    certificates=sorted(set(x.lower() for x in re.findall(r'certificate SHA-256 digest: ([a-fA-F0-9]{64})',signature)))
    if len(certificates)!=1:raise ValueError('Ambiguous signer identity')
    with apk.open('rb') as f:sha=digest(f)
    with zipfile.ZipFile(apk) as z:
        if z.testzip() is not None:raise ValueError('Invalid APK CRC')
        bundles=[n for n in z.namelist() if n.endswith('index.android.bundle')]
        abis=sorted({n.split('/')[1] for n in z.namelist() if n.startswith('lib/') and n.endswith('.so')})
        if len(bundles)!=1 or abis!=['arm64-v8a']:raise ValueError('Missing bundle or unexpected native architecture')
        with z.open(bundles[0]) as f:bundle_hash=digest(f)
    return {'source_commit':commit,'apk_sha256':sha,'package_id':identity,'version_name':version,'version_code':code,
        'abis':abis,'signature_v2_verified':True,'certificate_sha256':certificates[0],
        'reference_certificate_sha256':REFERENCE_CERT,'certificate_matches_reference':certificates[0]==REFERENCE_CERT,
        'embedded_bundle_sha256':bundle_hash,'zip_crc_verified':True,'device_validation':'UNVERIFIED',
        'signing':('release key supplied through repository secrets' if release_signed else 'internal development debug signing; not a production release'),
        'update_claim':'certificate comparison only; installed device version/certificate and actual installation remain unverified'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('apk',type=Path);p.add_argument('--aapt',required=True);p.add_argument('--apksigner',required=True);p.add_argument('--commit',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--release-signed',action='store_true')
    a=p.parse_args();head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    if head!=a.commit:raise ValueError('Checkout does not match declared source commit')
    badging=subprocess.check_output([a.aapt,'dump','badging',str(a.apk)],text=True)
    signature=subprocess.check_output([a.apksigner,'verify','--verbose','--print-certs',str(a.apk)],text=True)
    print(signature)
    report=inspect(a.apk,json.loads(Path('app.json').read_text())['expo'],badging,signature,a.commit,a.release_signed)
    a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2,sort_keys=True))
if __name__=='__main__':main()
