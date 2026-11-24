"""Read-only Windows process/startup audit. Never starts/stops a service."""
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import urllib.request
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
PORTS=(5173,8005,8006,8007,8008)
def digest(raw):return hashlib.sha256(raw).hexdigest()
def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/(name+'.py'))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
def ps(code):
    result=subprocess.run(['powershell.exe','-NoProfile','-Command',code],capture_output=True,text=True,encoding='utf-8',errors='replace')
    if result.returncode:
        reason='ACCESS_DENIED' if re.search('access.*denied|unauthorized|yetkisiz|erişim.*engell',result.stderr,re.I) else 'NO_MATCHING_EVENTS' if re.search('NoMatchingEventsFound',result.stderr,re.I) else 'QUERY_FAILED'
        return {'query_status':'UNAVAILABLE','exit_code':result.returncode,'reason':reason}
    try:return json.loads(result.stdout.strip() or 'null')
    except ValueError:return {'query_status':'UNAVAILABLE_NON_JSON'}
def rows(value):return value if isinstance(value,list) else [] if value is None else [value]
def release_state():
    runtime=module('attested-runtime');folder=ROOT/'release/attested-8008-56cbd7e'
    inputs=folder/'launch-inputs.json';c=json.loads(inputs.read_text());source=runtime.pinned_json(c['source_manifest'],c['source_sha256'])
    inventories={k:runtime.verify_source(c[k],source) for k in ('release','failback_release')}
    pins={str(inputs):digest(inputs.read_bytes())}
    for key,hashkey in (('config','config_sha256'),('failback_config','failback_config_sha256')):
        config=runtime.pinned_json(c[key],c[hashkey]);runtime.validate_environment(config)
        for name,expected in config['dependencies']['critical_entry_files'].items():
            actual=digest(Path(name).read_bytes())
            if actual!=expected:raise ValueError('BLOCK_DEPENDENCY_BYTES')
            pins[name]=actual
    for k in ('source_manifest','config','failback_config','launcher','reference','python'):pins[c[k]]=digest(Path(c[k]).read_bytes())
    reference=json.loads(Path(c['reference']).read_text())
    if reference['build_sha']!=runtime.BUILD or reference['loaded']['loaded_function_code_sha256']!='314eab9f6fb646919191851e5fd04a6a618a525c628e8f5bc1783290a2dace7b' or reference['loaded']['function_count']!=173:raise ValueError('BLOCK_REFERENCE_IDENTITY')
    return {'build_sha':runtime.BUILD,'expected_reference_fingerprint':reference['loaded']['loaded_function_code_sha256'],
            'source_inventories':inventories,'file_pins':pins,'current_process_attestation':'EXACT_RUNNING_VERSION_UNVERIFIED'}
def sanitized(command):
    command=command or ''
    tokens=re.findall(r'"([^"]*)"|(\S+)',command)
    words=[a or b for a,b in tokens]
    scripts=[]
    for word in words:
        clean=word.strip("'\";,()")
        if re.fullmatch(r'[A-Za-z]:[\\/][^\r\n\";<>|]*\.(?:py|ps1|cmd|bat|exe)',clean,re.I):scripts.append(clean)
    return {'sha256':digest(command.encode()),'script_or_executable_paths':scripts,
            'modules':re.findall(r'(?:-m\s+)([\w.]+)',command),
            'asgi_targets':re.findall(r'\b[\w.]+:(?:app|application)\b',command),
            'ports':re.findall(r'--port\s+(\d+)',command),
            'reload_flag':bool(re.search(r'--reload\b',command)),
            'watch_flag':bool(re.search(r'--watch\b',command)),
            'inline_powershell_present':bool(re.search(r'(?i)-(?:command|encodedcommand)\b',command)),
            'inline_content':'REDACTED','raw_command_exported':False}
def snapshot():
    runtime=module('attested-runtime');inspector=module('cutover-process-inspect')
    listeners=rows(ps('Get-NetTCPConnection -State Listen -LocalPort 5173,8005,8006,8007,8008 -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,OwningProcess | ConvertTo-Json -Compress'))
    all_procs=rows(ps('Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,ExecutablePath,@{n="created_utc";e={$_.CreationDate.ToUniversalTime().ToString("o")}},CommandLine | ConvertTo-Json -Compress'))
    byid={int(p['ProcessId']):p for p in all_procs if 'ProcessId' in p}
    ports={str(p):[] for p in PORTS};identities={};chains={}
    for row in listeners:
        if 'LocalPort' not in row:continue
        pid=row['OwningProcess'];p=byid.get(pid,{})
        identity=runtime.process_identity(pid);identities[str(row['LocalPort'])]=identity
        parents=[];cursor=pid;seen=set()
        while cursor in byid and cursor not in seen and len(parents)<8:
            seen.add(cursor);q=byid[cursor];parent=byid.get(q['ParentProcessId'])
            valid=bool(parent and parent['created_utc']<=q['created_utc'])
            parents.append({k:v for k,v in q.items() if k!='CommandLine'}|{'startup':sanitized(q.get('CommandLine')),'parent_current_identity_predates_child':valid})
            if not valid:break
            cursor=q['ParentProcessId']
        chains[str(row['LocalPort'])]=parents
        try:parameters=inspector.inspect(pid)
        except OSError:parameters={'status':'UNAVAILABLE'}
        ports[str(row['LocalPort'])].append({'address':row['LocalAddress'],'identity':identity,'created_utc':p.get('created_utc'),
            'parent_pid':p.get('ParentProcessId'),'parameters':parameters,'startup':sanitized(p.get('CommandLine')),
            'watcher':'VITE_DEV_HMR' if row['LocalPort']==5173 else 'NO_RELOAD_FLAG_OBSERVED',
            'running_loaded_fingerprint':'UNVERIFIED'})
    health={}
    for port,route in ((5173,'/engine/api/v1/health'),(8005,'/api/health'),(8006,'/api/v1/health'),(8007,'/api/news'),(8008,'/api/v1/health'),(5173,'/engine/openapi.json'),(8008,'/openapi.json')):
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}{route}',timeout=5) as response:
                body=response.read();value=json.loads(body)
                health[str(port)+route]={'http':response.status,'sha256':digest(body),'safe_summary':{k:value[k] for k in ('status','provider','data_status') if k in value}}
        except (OSError,ValueError) as error:health[str(port)+route]={'http':getattr(error,'code',None),'error':type(error).__name__}
    services=rows(ps("Get-CimInstance Win32_Service | Where-Object { $_.ProcessId -in @("+','.join(str(r['OwningProcess']) for r in listeners if 'OwningProcess' in r)+") -or $_.PathName -match 'TradeAI|uvicorn|8008|V5Runtime' } | Select-Object Name,State,StartMode,ProcessId,PathName | ConvertTo-Json -Compress"))
    for s in services:
        if 'PathName' in s:s['startup']=sanitized(s.pop('PathName'))
    tasks=rows(ps("Get-ScheduledTask -ErrorAction Stop | ForEach-Object { $t=$_; foreach($a in $t.Actions){ if(($t.TaskName+' '+$t.TaskPath+' '+$a.Execute+' '+$a.Arguments+' '+$a.WorkingDirectory) -match 'TradeAI|trade-ai|uvicorn|8008|V5Runtime'){ [pscustomobject]@{name=$t.TaskName;path=$t.TaskPath;state=[string]$t.State;execute=$a.Execute;arguments=$a.Arguments;cwd=$a.WorkingDirectory} } } } | ConvertTo-Json -Compress"))
    for t in tasks:
        if 'arguments' in t:t['startup']=sanitized(str(t.get('execute',''))+' '+str(t.pop('arguments','')))
    boot=ps('Get-CimInstance Win32_OperatingSystem | Select-Object @{n="boot_utc";e={$_.LastBootUpTime.ToUniversalTime().ToString("o")}} | ConvertTo-Json -Compress')
    events=ps("Get-WinEvent -FilterHashtable @{LogName='System';Id=12,13,6005,6006,6008,1074;StartTime=(Get-Date).AddDays(-2)} -MaxEvents 30 -ErrorAction Stop | Select-Object Id,RecordId,ProviderName,@{n='utc';e={$_.TimeCreated.ToUniversalTime().ToString('o')}} | ConvertTo-Json -Compress")
    process_events=ps("Get-WinEvent -FilterHashtable @{LogName='Security';Id=4688,4689;StartTime=(Get-Date).AddDays(-2)} -MaxEvents 2000 -ErrorAction Stop | ForEach-Object { $e=$_; $x=[xml]$e.ToXml();$d=@{};foreach($v in $x.Event.EventData.Data){$d[$v.Name]=[string]$v.'#text'};if($d.NewProcessId -in @('0x2f78','0x2640','0x2f44') -or $d.ProcessId -eq '0x2640'){[pscustomobject]@{Id=$e.Id;RecordId=$e.RecordId;utc=$e.TimeCreated.ToUniversalTime().ToString('o');NewProcessId=$d.NewProcessId;ProcessId=$d.ProcessId;NewProcessName=$d.NewProcessName;ParentProcessName=$d.ParentProcessName}} } | ConvertTo-Json -Compress")
    review=module('final-pwa-review')
    return {'observed_istanbul':datetime.now(ZoneInfo('Europe/Istanbul')).isoformat(),'ports':ports,'identities':identities,'parent_chains':chains,
            'health':health,'services':services,'scheduled_tasks':tasks,'boot':boot,'system_events':events,'process_events':process_events,
            'original_hashes':review.files(review.ORIGINAL),'isolated_hashes':review.files(ROOT),'backend_sha':review.git(review.BACKEND,'rev-parse','HEAD').decode().strip(),
            'backend_status':review.git(review.BACKEND,'status','--porcelain').decode(),'pwa_head':review.git(ROOT,'rev-parse','HEAD').decode().strip(),
            'release_pins':release_state(),'credentials_exported':False,'live_mutations':False}
if __name__=='__main__':
    out=Path(sys.argv[1]).resolve()
    if out.parent.parent!=ROOT/'release':raise ValueError('Unique isolated release/evidence directory required')
    value=snapshot();out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,ensure_ascii=False)
    print(json.dumps({'audit':str(out),'pids':{p:[r['identity']['pid'] for r in rows] for p,rows in value['ports'].items()},'live_mutations':False}))
