"""Read-only source preflight, verified backup and review ZIP. Never applies/restarts."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
BACKEND=(Path(__file__).resolve().parents[2] / 'day-trader-skill')
ORIGINAL=(Path(__file__).resolve().parents[2] / 'trade-ai-forex-web')
RELEASE=ROOT/'release/reconciled-56cbd7e'
BACKEND_SHA='56cbd7e05a40b106deda9298e2be28b488d0d952'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def git(root,*args): return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
def save(path,data): path.write_text(json.dumps(data,indent=2,sort_keys=True),encoding='utf-8')
def protected():
    files=list((ORIGINAL/'src').rglob('*'))+list((ORIGINAL/'public').rglob('*'))
    files += [p for p in ORIGINAL.iterdir() if p.suffix in ('.py','.json','.ts','.js','.html')]
    result={str(p):sha(p) for p in files if p.is_file()}
    result.update({str(BACKEND/p):sha(BACKEND/p) for p in git(BACKEND,'ls-files').splitlines()})
    return result

def preflight():
    if git(BACKEND,'rev-parse','HEAD')!=BACKEND_SHA or git(BACKEND,'status','--porcelain'):
        raise ValueError('Backend source drift')
    expected=json.loads((RELEASE/'protected-before.json').read_text())
    if protected()!=expected: raise ValueError('Protected original/backend source drift')
    rc=json.loads((ROOT/'release/rc/manifest.json').read_text())
    if any(sha(ROOT/row['file'])!=row['source_sha256'] for row in rc['files']):
        raise ValueError('PWA source/payload mismatch')
    subprocess.run(['node','tools/promotion-apply.mjs'],cwd=ROOT,check=True,capture_output=True)
    print('PASS source identities, protected hashes and PWA zero-write dry-run')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['snapshot','backup','preflight','seal','seal-blocked'])
    args=p.parse_args()
    if args.action=='snapshot':
        dest=RELEASE/'protected-before.json'
        if dest.exists(): raise ValueError('Keep existing source snapshot')
        save(dest,protected()); print('Protected snapshot captured'); return
    blocked=args.action=='seal-blocked'
    if blocked:
        if git(BACKEND,'rev-parse','HEAD')!=BACKEND_SHA or git(BACKEND,'status','--porcelain'):
            raise ValueError('Backend drift prevents even review packaging')
        before=json.loads((RELEASE/'protected-before.json').read_text())
        after=protected()
        drift=[{'file':name,'before':before.get(name),'after':after.get(name)}
               for name in sorted(set(before)|set(after)) if before.get(name)!=after.get(name)]
        if not drift: raise ValueError('Blocked review mode requires actual drift')
        save(RELEASE/'drift.json',{'status':'BLOCKED','deployable':False,'drift':drift})
    else:
        preflight()
    if args.action=='backup':
        dest=RELEASE/'preapproval-backup'
        dest.mkdir()
        manifest=json.loads((ROOT/'release/rc/manifest.json').read_text())
        hashes={}
        for row in manifest['guards']:
            name=row['file']; source=ORIGINAL/name
            if sha(source)!=row['sha256']: raise ValueError('Backup guard drift')
            output=dest/name; output.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,output)
            if sha(output)!=row['sha256']: raise ValueError('Backup hash mismatch')
            hashes[name]=sha(output)
        save(RELEASE/'backup-manifest.json',hashes)
        print('PASS',len(hashes),'backup hashes'); return
    if args.action in ('seal','seal-blocked'):
        hashes=json.loads((RELEASE/'backup-manifest.json').read_text())
        if any(sha(RELEASE/'preapproval-backup'/name)!=digest for name,digest in hashes.items()):
            raise ValueError('Backup corruption')
        files={}
        for folder in ['tools','docs','src','public','tests']:
            for name in git(ROOT,'ls-files',folder).splitlines(): files[name]=ROOT/name
        for name in git(ROOT,'ls-files').splitlines():
            if '/' not in name: files[name]=ROOT/name
        for folder in ['release/rc','release/reconciled-56cbd7e','release/cutover/backend-3c8adb8',
                       'release/cutover/v2-pinned','release/cutover/failback-v2']:
            for source in (ROOT/folder).rglob('*'):
                if (source.is_file() and not any(part in source.parts for part in
                        ('__pycache__','.git','trade-ai-v2-antigravity'))
                        and source.suffix not in ('.pyc','.log')):
                    files[source.relative_to(ROOT).as_posix()]=source
        for name in ['failback-config.json','runtime-config.json']:
            files['release/cutover/'+name]=ROOT/'release/cutover'/name
        for pattern in ['verified-release-backend*.log','reconciled-unit.log','reconciled-build.log',
                        'verified-reconciled-lint.log','reconciled-operation-tests.log',
                        'reconciled-additive.log','reconciled-runtime-tests.log',
                        'final-reconciled-*.log','reconciled-browser.log',
                        'verified-reconciled-browser.log','release-backend311.log',
                        'reconciled-runtime.json']:
            for source in (ROOT/'.artifacts').glob(pattern):
                files['evidence/'+source.name]=source
        for name in ['candidate-results.json','candidate-manifest.json','failback-results.json',
                     'failback-manifest.json','e2e-results.json']:
            source=ROOT/'.artifacts/cutover'/name
            if source.is_file(): files['evidence/'+name]=source
        files.pop('release/reconciled-56cbd7e/source-manifest.json',None)
        manifest={'backend_sha':BACKEND_SHA,'pwa_rc_sha':'34c6ec2e1a02893cd1d8301d8bf6c5048c6aeb05',
                  'pwa_tooling_sha':git(ROOT,'rev-parse','HEAD'),'approval_received':False,
                  'status':'BLOCKED' if blocked else 'READY_FOR_APPROVAL',
                  'deployable':not blocked,
                  'files':{name:sha(source) for name,source in sorted(files.items())}}
        save(RELEASE/'source-manifest.json',manifest)
        files['release/reconciled-56cbd7e/source-manifest.json']=RELEASE/'source-manifest.json'
        archive=ROOT/('release/TRADE_AI_V3_RECONCILED_56cbd7e_34c6ec2'+
                      ('_BLOCKED_REVIEW' if blocked else '')+'.zip')
        with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as out:
            for name,source in sorted(files.items()): out.write(source,name)
        with zipfile.ZipFile(archive) as zipped:
            if zipped.testzip(): raise ValueError('Archive CRC failed')
            for name,digest in manifest['files'].items():
                if hashlib.sha256(zipped.read(name)).hexdigest()!=digest: raise ValueError('Archive hash mismatch')
        archive.with_suffix('.zip.sha256').write_text(sha(archive)+'  '+archive.name+'\n')
        print('PASS sealed ZIP',sha(archive),len(files),'files')

if __name__=='__main__': main()
