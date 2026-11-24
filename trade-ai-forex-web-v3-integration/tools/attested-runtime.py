"""Local startup provenance for a NEW process; never attests an old process.

Operator-owned source/config/manifest directories are a trust prerequisite.
This is not cryptographic remote attestation. No public diagnostics endpoint.
"""
import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import types
import uuid

BUILD='56cbd7e05a40b106deda9298e2be28b488d0d952'
PROTECTED={5173,8005,8006,8007,8008}
PACKAGES={'numpy':'numpy','fastapi':'fastapi','pydantic':'pydantic',
          'pydantic_core':'pydantic_core','starlette':'starlette','uvicorn':'uvicorn','MetaTrader5':'MetaTrader5'}
ENV_KEYS={'MT5_ANALYSIS_POLICY','MT5_EXPECTED_REAL_SERVER','MT5_EXPECTED_REAL_CURRENCY',
          'MT5_SYMBOL_MAP','MT5_BROKER_HOURS','MT5_SPREAD_POLICY_FILE',
          'V2_CHART_GIT_ROOT','V2_CANDLESTICK_FILE','V2_CANDLESTICK_SHA256'}
READ_CALLS={'initialize','shutdown','last_error','terminal_info','account_info',
            'symbol_info','symbol_info_tick','copy_rates_from_pos','order_calc_profit'}

class IntegrityError(ValueError): pass
def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(raw): return hashlib.sha256(raw).hexdigest()
def file_hash(path): return digest(Path(path).read_bytes())
def utc_now(): return datetime.now(timezone.utc).isoformat()

def no_links(path):
    for part in (Path(path),*Path(path).parents):
        info=part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
            raise IntegrityError('Link/reparse source refused')

def pinned_json(path,expected):
    raw=Path(path).read_bytes()
    if digest(raw)!=expected: raise IntegrityError('Pinned document digest mismatch')
    return json.loads(raw)

def verify_source(root,document):
    root=Path(root).absolute(); no_links(root)
    if document.get('build_sha')!=BUILD or not document.get('files'):
        raise IntegrityError('Wrong source checkpoint')
    actual={}
    for path in root.rglob('*'):
        no_links(path)
        if path.is_file():
            if path.suffix=='.pyc' or '__pycache__' in path.parts:
                raise IntegrityError('Precompiled source cache refused')
            actual[path.relative_to(root).as_posix()]=file_hash(path)
    if actual!=document['files']: raise IntegrityError('Source inventory/content drift')
    return digest(canonical(actual))

def validate_environment(config):
    env=config.get('environment',{})
    if set(env)!=ENV_KEYS: raise IntegrityError('Unreviewed configuration keys')
    if (config.get('build_sha')!=BUILD or env.get('MT5_ANALYSIS_POLICY')!='REAL_READONLY_DATA'
            or env.get('MT5_EXPECTED_REAL_SERVER')!='Exness-MT5Real50'
            or env.get('MT5_EXPECTED_REAL_CURRENCY')!='USC'
            or json.loads(env['MT5_SYMBOL_MAP'])!={s:s+'c' for s in ('XAUUSD','EURUSD','GBPUSD','USDJPY')}
            or env['MT5_BROKER_HOURS']!='{}'):
        raise IntegrityError('Read-only server/currency/alias configuration mismatch')
    for path,expected in config.get('assets',{}).items():
        no_links(Path(path))
        if file_hash(path)!=expected: raise IntegrityError('Pinned runtime asset drift')
    return env

def dependencies():
    versions={}; files={}
    for distribution,module_name in PACKAGES.items():
        module=importlib.import_module(module_name)
        versions[distribution]=importlib.metadata.version(distribution)
        files[str(Path(module.__file__).resolve())]=file_hash(module.__file__)
    binary=importlib.import_module('numpy._core._multiarray_umath')
    files[str(Path(binary.__file__).resolve())]=file_hash(binary.__file__)
    if sys.version_info[:2]!=(3,11) or versions['numpy']!='2.2.6':
        raise IntegrityError('Python 3.11 / NumPy 2.2.6 required')
    return {'versions':versions,'critical_entry_files':files,'python':sys.version.split()[0],
            'python_prefix':sys.prefix,'python_executable':sys.executable}

def process_identity(pid):
    """OS process creation identity only; no debugger or process-memory reads."""
    from ctypes import wintypes as w
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];kernel.OpenProcess.restype=w.HANDLE
    kernel.GetProcessTimes.argtypes=[w.HANDLE,*([ctypes.POINTER(w.FILETIME)]*4)]
    kernel.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,ctypes.POINTER(w.DWORD)]
    kernel.CloseHandle.argtypes=[w.HANDLE]
    handle=kernel.OpenProcess(0x1000,False,pid)
    if not handle: raise IntegrityError('Process identity unavailable')
    try:
        values=[w.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle,*[ctypes.byref(x) for x in values]):
            raise IntegrityError('Process start identity unavailable')
        created=(values[0].dwHighDateTime<<32)|values[0].dwLowDateTime
        path=ctypes.create_unicode_buffer(32768);size=w.DWORD(len(path))
        if not kernel.QueryFullProcessImageNameW(handle,0,path,ctypes.byref(size)):
            raise IntegrityError('Process executable unavailable')
        return {'pid':pid,'creation_filetime_100ns':created,'os_executable':path.value}
    finally: kernel.CloseHandle(handle)

def port_owner(port):
    if type(port) is not int or not 1<=port<=65535: raise IntegrityError('Invalid port')
    command=f'Get-NetTCPConnection -State Listen -LocalPort {port} | Select-Object -ExpandProperty OwningProcess -Unique'
    result=subprocess.check_output(['powershell.exe','-NoProfile','-Command',command],
                                   text=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)).strip()
    if not result.isdigit(): raise IntegrityError('Listener identity unavailable or ambiguous')
    return int(result)

def check_port(port,approved=False):
    if not 1<=port<=65535 or (port in PROTECTED and not(port==8008 and approved)):
        raise IntegrityError('Protected port: separate 8008 cutover approval required')

def load_release(root):
    root=Path(root).resolve()
    if any(name=='forex' or name.startswith('forex.') for name in sys.modules):
        raise IntegrityError('Fresh interpreter required; Forex already imported')
    # A fresh cache namespace prevents reading old source .pyc caches.
    sys.dont_write_bytecode=True
    sys.pycache_prefix=str(Path(os.environ.get('TEMP','.'))/('trade-ai-no-cache-'+uuid.uuid4().hex))
    sys.path.insert(0,str(root))
    import forex
    origins={}
    for source in sorted((root/'forex').glob('*.py')):
        name='forex' if source.stem=='__init__' else 'forex.'+source.stem
        module=importlib.import_module(name)
        origin=Path(module.__file__).resolve()
        if origin!=source.resolve(): raise IntegrityError('Imported module origin mismatch')
        origins[name]={'relative_path':origin.relative_to(root).as_posix(),'sha256':file_hash(origin)}
    return origins,loaded_fingerprint

def code_structure(code):
    """Semantic code fields, without marshal's mutable string-intern flags.

    CPython's adaptive execution cache is intentionally excluded; it changes
    during normal execution and is not an application code replacement.
    """
    def value(item):
        if isinstance(item,types.CodeType):return code_structure(item)
        if isinstance(item,bytes):return {'bytes':item.hex()}
        if isinstance(item,tuple):return {'tuple':[value(x) for x in item]}
        if isinstance(item,frozenset):return {'frozenset':sorted((value(x) for x in item),key=lambda x:canonical(x))}
        if item is Ellipsis:return {'ellipsis':True}
        if item is None or type(item) in (str,int,float,bool):return item
        raise IntegrityError('Unsupported code constant')
    return {'bytecode':code.co_code.hex(),'constants':[value(x) for x in code.co_consts],
        'names':code.co_names,'varnames':code.co_varnames,'cellvars':code.co_cellvars,
        'freevars':code.co_freevars,'argcount':code.co_argcount,
        'posonlyargcount':code.co_posonlyargcount,'kwonlyargcount':code.co_kwonlyargcount,
        'flags':code.co_flags,'stacksize':code.co_stacksize,'firstlineno':code.co_firstlineno,
        'linetable':code.co_linetable.hex(),'exceptiontable':code.co_exceptiontable.hex()}

def loaded_fingerprint():
    functions={}
    for name,module in sorted(list(sys.modules.items())):
        if not name.startswith('forex.') or module is None:continue
        for key,value in sorted(vars(module).items()):
            candidates={key:value}
            if isinstance(value,type) and value.__module__==name:
                candidates={key+'.'+member:method for member,method in vars(value).items()}
            for qualified,candidate in candidates.items():
                if isinstance(candidate,(staticmethod,classmethod)):candidate=candidate.__func__
                seen=set()
                while hasattr(candidate,'__wrapped__') and id(candidate) not in seen:
                    seen.add(id(candidate));candidate=candidate.__wrapped__
                if isinstance(candidate,types.FunctionType) and candidate.__module__==name:
                    functions[name+'.'+qualified]=digest(canonical(code_structure(candidate.__code__)))
    if not functions:raise IntegrityError('No loaded Forex code')
    return {'algorithm':'local-code-structure-1','python_cache_tag':sys.implementation.cache_tag,
            'function_count':len(functions),'loaded_function_code_sha256':digest(canonical(functions)),
            'function_hashes':functions}

class ReadOnlyTerminal:
    def __init__(self,module): self.module=module
    def __getattr__(self,name):
        if name in READ_CALLS or name.startswith(('ACCOUNT_TRADE_MODE_','TIMEFRAME_','ORDER_TYPE_','SYMBOL_CALC_MODE_')):
            return getattr(self.module,name)
        raise AttributeError('Terminal operation not allowlisted')

def validate_startup(record,config,source_digest,config_digest,reference,port,identity):
    binding=dict(record);saved=binding.pop('binding_sha256',None)
    if digest(canonical(binding))!=saved: raise IntegrityError('Startup record corruption')
    if (record.get('mode')!='LOCAL_FROZEN_STARTUP_PROVENANCE'
            or record.get('build_sha')!=BUILD or record.get('release_id')!=config['release_id']
            or record.get('source_manifest_sha256')!=source_digest
            or record.get('config_sha256')!=config_digest or record.get('port')!=port
            or record.get('process')!=identity or record.get('execution_permission') is not False
            or record.get('loaded')!=reference['loaded']
            or record.get('module_origins')!=reference['module_origins']
            or record.get('dependencies')!=config['dependencies']):
        raise IntegrityError('Missing/mismatching startup identity')

class IntegrityGuard:
    def __init__(self,app,check): self.app=app;self.check=check
    async def __call__(self,scope,receive,send):
        if scope['type']=='http':
            try:self.check()
            except Exception as exc:
                print('IntegrityGuard blocked: '+(str(exc) if isinstance(exc,IntegrityError)
                      else 'runtime integrity check failed'),file=sys.stderr,flush=True)
                raw=b'{"status":"RELEASE_INTEGRITY_BLOCKED","execution_permission":false}'
                await send({'type':'http.response.start','status':503,'headers':[(b'content-type',b'application/json')]})
                await send({'type':'http.response.body','body':raw});return
        await self.app(scope,receive,send)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['dependencies','reference','serve','verify'])
    parser.add_argument('--release',type=Path)
    parser.add_argument('--source-manifest',type=Path)
    parser.add_argument('--source-sha256')
    parser.add_argument('--config',type=Path)
    parser.add_argument('--config-sha256')
    parser.add_argument('--reference',type=Path)
    parser.add_argument('--startup',type=Path)
    parser.add_argument('--port',type=int)
    parser.add_argument('--operator-approved-cutover',action='store_true')
    args=parser.parse_args(argv)
    if args.mode=='dependencies':print(json.dumps(dependencies(),indent=2));return
    if args.mode=='serve':check_port(args.port,args.operator_approved_cutover)
    source=pinned_json(args.source_manifest,args.source_sha256)
    config=pinned_json(args.config,args.config_sha256)
    verify_source(args.release,source)
    env=validate_environment(config)
    # Validate pinned dependency bytes before importing their entry modules.
    for path,expected in config['dependencies']['critical_entry_files'].items():
        no_links(Path(path))
        if file_hash(path)!=expected:raise IntegrityError('Dependency bytes drift before import')
    if dependencies()!=config['dependencies']:raise IntegrityError('Dependency identity drift')
    for key in list(os.environ):
        if key.startswith(('MT5_','V2_')):del os.environ[key]
    os.environ.update(env)
    if args.mode=='verify':
        record=json.loads(args.startup.read_text())
        reference=json.loads(args.reference.read_text())
        validate_startup(record,config,args.source_sha256,args.config_sha256,reference,
                         args.port,process_identity(port_owner(args.port)))
        if record['launcher_sha256']!=file_hash(__file__):raise IntegrityError('Launcher drift')
        print(json.dumps({'status':'PASS_LOCAL_STARTUP_PROVENANCE','build_sha':BUILD,
                          'pid':record['process']['pid'],'port':args.port,'release_id':config['release_id']}));return
    origins,fingerprint=load_release(args.release)
    import forex.api as api
    from forex.v2_bridge import configured_v2_extension
    api.app.state.analytical_extension=configured_v2_extension()
    import forex.historical_sessions as historical
    if historical.PRODUCTION_REVIEWS:raise IntegrityError('Historical approval list must remain empty')
    verify_source(args.release,source)
    frozen=fingerprint()
    if args.mode=='reference':
        with args.reference.open('x',encoding='utf-8') as out:
            json.dump({'build_sha':BUILD,'loaded':frozen,'module_origins':origins},out,indent=2)
        print('PASS independent loaded-code reference');return
    reference=json.loads(args.reference.read_text())
    if frozen!=reference['loaded'] or origins!=reference['module_origins']:
        raise IntegrityError('Loaded code differs from independent fresh reference')
    import MetaTrader5 as mt5
    from forex.providers import MT5Provider
    provider=MT5Provider(mt5=ReadOnlyTerminal(mt5))
    if provider.historical_evidence.candidates:raise IntegrityError('No historical inputs approved')
    gate=provider.account_preflight('REAL_READONLY_DATA','Exness-MT5Real50','USC')
    if gate.get('balance') is not None or gate.get('status')!='PASS':raise IntegrityError('Broker read-only preflight')
    api.app.state.provider=provider
    def integrity_check():
        if file_hash(args.config)!=args.config_sha256:raise IntegrityError('Config drift')
        validate_environment(config)
        verify_source(args.release,source)
        for path,expected in config['dependencies']['critical_entry_files'].items():
            if file_hash(path)!=expected:raise IntegrityError('Dependency file drift')
        if fingerprint()!=frozen:raise IntegrityError('Loaded code changed after startup')
    integrity_check()
    record={'mode':'LOCAL_FROZEN_STARTUP_PROVENANCE','build_sha':BUILD,'release_id':config['release_id'],
            'source_manifest_sha256':args.source_sha256,'config_sha256':args.config_sha256,
            'launcher_sha256':file_hash(__file__),'startup_utc':utc_now(),
            'process':process_identity(os.getpid()),'parent_pid':os.getppid(),'port':args.port,
            'python_executable':sys.executable,'python_version':sys.version.split()[0],
            'dependencies':config['dependencies'],'module_origins':origins,'loaded':frozen,
            'policy':'REAL_READONLY_DATA','server':'Exness-MT5Real50','currency':'USC',
            'execution_permission':False,'real_balance_used':False}
    record['binding_sha256']=digest(canonical(record))
    with args.startup.open('x',encoding='utf-8') as out:json.dump(record,out,indent=2)
    import uvicorn
    uvicorn.run(IntegrityGuard(api.app,integrity_check),host='127.0.0.1',port=args.port,
                reload=False,access_log=False,log_level='warning')

if __name__=='__main__':main()
