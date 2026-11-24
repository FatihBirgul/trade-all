"""Prepare/seal an isolated, operator-reviewed runtime bundle. Never deploys."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import uuid
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'release/attested-8008-56cbd7e'
PYTHON=ROOT/'.artifacts/cutover/runtime-venv/Scripts/python.exe'
BACKEND=(Path(__file__).resolve().parents[2] / 'day-trader-skill')
SHA='56cbd7e05a40b106deda9298e2be28b488d0d952'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,indent=2,sort_keys=True),encoding='utf-8')
def git(root,*args):return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/name.replace('_','-').__add__('.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def prepare():
    if git(BACKEND,'rev-parse','HEAD')!=SHA or git(BACKEND,'status','--porcelain'):
        raise ValueError('Unexpected backend source')
    source=OUT/'backend';source.mkdir()
    with zipfile.ZipFile(OUT/'backend.zip') as zipped:zipped.extractall(source)
    manifest={'build_sha':SHA,'files':{p.relative_to(source).as_posix():sha(p)
               for p in sorted(source.rglob('*')) if p.is_file()}}
    save(OUT/'source.json',manifest)
    assets=OUT/'assets/engines';assets.mkdir(parents=True)
    candle=assets/'candlestick.py'
    shutil.copyfile(ROOT/'release/cutover/v2-pinned/engines/candlestick.py',candle)
    if sha(candle)!='45ee833fd3a5ffd178a4ee565e5914f79e9fb0b1c2aa62fe16b703057f63542c':
        raise ValueError('V2 candlestick pin changed')
    dependency_identity=json.loads(subprocess.check_output(
        [str(PYTHON),'-B',str(ROOT/'tools/attested-runtime.py'),'dependencies'],text=True))
    save(OUT/'dependencies.json',dependency_identity)
    config={'build_sha':SHA,'release_id':'trade-ai-v5-8008-'+uuid.uuid4().hex,
            'dependencies':dependency_identity,
            'environment':json.loads((ROOT/'release/reconciled-56cbd7e/runtime-config.json').read_text())['environment']}
    spread=source/'docs/examples/exness_cent_spread_policy.unapproved.json'
    config['environment'].update(MT5_SPREAD_POLICY_FILE=str(spread),V2_CANDLESTICK_FILE=str(candle))
    config['assets']={str(candle):sha(candle),str(spread):sha(spread)}
    save(OUT/'config.json',config)
    failback_source=OUT/'failback-backend';failback_source.mkdir()
    with zipfile.ZipFile(OUT/'backend.zip') as zipped:zipped.extractall(failback_source)
    failback_candle=OUT/'failback-assets/engines/candlestick.py';failback_candle.parent.mkdir(parents=True)
    shutil.copyfile(candle,failback_candle)
    fallback=json.loads(json.dumps(config));fallback['release_id']=config['release_id']+'-failback'
    failback_spread=failback_source/'docs/examples/exness_cent_spread_policy.unapproved.json'
    fallback['environment'].update(MT5_SPREAD_POLICY_FILE=str(failback_spread),V2_CANDLESTICK_FILE=str(failback_candle))
    fallback['assets']={str(failback_candle):sha(failback_candle),str(failback_spread):sha(failback_spread)}
    save(OUT/'failback-config.json',fallback)
    runtime=load('attested_runtime')
    observation={'current_8008':runtime.process_identity(runtime.port_owner(8008)),
                 'exact_running_version':'EXACT_RUNNING_VERSION_UNVERIFIABLE_WITHOUT_CUTOVER',
                 'source_checkout_sha':git((Path.home() / 'trade-ai-v3-runtime-candidate'),'rev-parse','HEAD'),
                 'safe_prior_observation':json.loads((ROOT/'.artifacts/runtime8008-initial.json').read_text()),
                 'backup_scope':'Verified source + observed safe launch fields; not an old RAM/private-env image'}
    save(OUT/'current-runtime-backup.json',observation)
    shutil.copyfile(ROOT/'release/runtime8008-56cbd7e/protected-before.json',OUT/'protected-before.json')
    commands={'python':str(PYTHON),'launcher':str(ROOT/'tools/attested-runtime.py'),
        'release':str(source),'failback_release':str(failback_source),'source_manifest':str(OUT/'source.json'),
        'source_sha256':sha(OUT/'source.json'),'config':str(OUT/'config.json'),
        'config_sha256':sha(OUT/'config.json'),'failback_config':str(OUT/'failback-config.json'),
        'failback_config_sha256':sha(OUT/'failback-config.json'),'reference':str(OUT/'reference-code-structure.json')}
    save(OUT/'launch-inputs.json',commands)
    subprocess.run([str(PYTHON),'-B',commands['launcher'],'reference',*arguments(commands),
                    '--reference',commands['reference']],cwd=ROOT,check=True)
    print('PASS fresh source/config/dependency pins and independent startup reference')

def arguments(c,fallback=False):
    return ['--release',c['failback_release'] if fallback else c['release'],'--source-manifest',c['source_manifest'],
            '--source-sha256',c['source_sha256'],'--config',c['failback_config'] if fallback else c['config'],
            '--config-sha256',c['failback_config_sha256'] if fallback else c['config_sha256']]

def seal():
    results=json.loads((OUT/'acceptance.json').read_text())
    if results['status']!='PASS':raise ValueError('Acceptance is incomplete')
    gate=load('runtime8008_preflight')
    before=json.loads((OUT/'protected-before.json').read_text());current=gate.protected()
    drift=[{'file':name,'before':before.get(name),'after':current.get(name)}
           for name in sorted(set(before)|set(current)) if before.get(name)!=current.get(name)]
    if any(row['file'].startswith(str(BACKEND)) or row['file']==str(gate.ORIGINAL/'vite.config.ts') for row in drift):
        raise ValueError('Backend/proxy drift blocks runtime-only release')
    save(OUT/'pwa-target-drift.json',{'pwa_apply_authorized':False,'drift':drift,
                                    'gate':'TARGET_DRIFT_REQUIRES_REVIEW' if drift else 'NOT_AUTHORIZED'})
    files={}
    for name in ('tools/.gitattributes','tools/attested-runtime.py','tools/attested-release.py','tools/attested-acceptance.py','tools/attested-cutover.py',
                 'tests/attested_runtime_test.py','tests/attested-client.test.mjs','docs/V3_ATTESTED_RUNTIME_HANDOFF_TR.md'):
        files[name]=ROOT/name
    active={'backend.zip','dependencies.json','source.json','config.json','failback-config.json',
            'launch-inputs.json','reference-code-structure.json','current-runtime-backup.json',
            'protected-before.json','acceptance.json','pwa-target-drift.json',
            Path(results['primary']['startup']).name,Path(results['failback']['startup']).name}
    for path in OUT.rglob('*'):
        relative=path.relative_to(OUT).as_posix()
        if (path.is_file() and '__pycache__' not in path.parts
                and (relative in active or relative.startswith(('backend/','failback-backend/',
                    'assets/engines/','failback-assets/engines/')))):
            files[path.relative_to(ROOT).as_posix()]=path
    for path in (ROOT/'release/runtime8008-56cbd7e').rglob('*'):
        if path.is_file():files[path.relative_to(ROOT).as_posix()]=path
    files['release/rc/manifest.json']=ROOT/'release/rc/manifest.json'
    files['tools/runtime8008-preflight.py']=ROOT/'tools/runtime8008-preflight.py'
    for path in (ROOT/'.artifacts').glob('attested-*.log'):
        files['evidence/'+path.name]=path
    files.pop('release/attested-8008-56cbd7e/package-manifest.json',None)
    manifest={'status':'READY_FOR_APPROVAL','scope':'8008_RUNTIME_ONLY',
              'approval_received':False,'pwa_apply_authorized':False,
              'pwa_gate':'TARGET_DRIFT_REQUIRES_REVIEW' if drift else 'NOT_AUTHORIZED',
              'build_sha':SHA,'tooling_sha':git(ROOT,'rev-parse','HEAD'),
              'next_authorization':'8008 runtime replacement and tested failback ONLY; no PWA APPLY',
              'files':{name:sha(path) for name,path in files.items()}}
    save(OUT/'package-manifest.json',manifest)
    files['release/attested-8008-56cbd7e/package-manifest.json']=OUT/'package-manifest.json'
    archive=ROOT/'release/TRADE_AI_V3_ATTESTED_8008_56cbd7e_READY.zip'
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as zipped:
        for name,path in files.items():zipped.write(path,name)
    with zipfile.ZipFile(archive) as zipped:
        if zipped.testzip():raise ValueError('Archive CRC failure')
        for name,expected in manifest['files'].items():
            if hashlib.sha256(zipped.read(name)).hexdigest()!=expected:raise ValueError('Archive content failure')
    archive.with_suffix('.zip.sha256').write_text(sha(archive)+'  '+archive.name+'\n')
    print('PASS READY_FOR_APPROVAL runtime package',sha(archive),len(files),'files')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','seal'])
    args=parser.parse_args()
    prepare() if args.action=='prepare' else seal()

if __name__=='__main__':main()
