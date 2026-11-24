"""Optional project-scoped local checkpoint persistence; disabled unless explicitly configured."""
from pathlib import Path
from hashlib import sha256
from threading import RLock
import os,re
from . import ROOT
from .ingestion import _read,bounded_json
from .structure_ledger import StructureLedger
from forex.contracts import canonical

STATE_ROOT=ROOT/'state/v9'


class CheckpointStore:
    def __init__(self,root=None):
        self.lock=RLock();self.root=None
        if root is None:return
        if any(p.is_symlink() for p in (STATE_ROOT,*STATE_ROOT.parents)):raise ValueError('Checkpoint storage root symlink refused')
        base=STATE_ROOT.resolve();selected=Path(root)
        if selected.is_symlink() or not selected.exists() or not selected.resolve().is_relative_to(base):raise ValueError('Explicit existing V9 checkpoint directory required')
        self.root=selected.resolve()
    def _key(self,key):
        if self.root is None:raise ValueError('Checkpoint persistence not configured')
        if not isinstance(key,str) or not re.fullmatch('[a-f0-9]{64}',key):raise ValueError('Opaque checkpoint key required')
        return key+'.checkpoint.json'
    def save(self,key,ledger):
        name=self._key(key);raw=canonical(ledger.checkpoint()).encode()
        if len(raw)>400000:raise ValueError('Checkpoint size exceeded')
        with self.lock:
            target=self.root/name
            if target.is_symlink():raise ValueError('Checkpoint symlink refused')
            if not target.exists() and len(list(self.root.glob('*.checkpoint.json')))>=16:raise ValueError('Checkpoint quota16 reached; no automatic user-file deletion')
            temporary=self.root/(key+'.'+os.urandom(8).hex()+'.tmp')
            fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
            try:
                with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
                os.replace(temporary,target)
            finally:
                if temporary.exists():temporary.unlink() # only our own newly-created staging file
        return {'sha256':sha256(raw).hexdigest(),'source_authenticated':False,'scope':'LOCAL_V9_CHECKPOINT_ONLY'}
    def load(self,key,*,identity,source,timeframe):
        with self.lock:
            _,raw=_read(self.root,self._key(key))
            if len(raw)>400000:raise ValueError('Checkpoint size exceeded')
            obj=StructureLedger.restore(bounded_json(raw.decode('utf-8')))
            if obj.identity!=identity or obj.source!=source or obj.timeframe!=timeframe:raise ValueError('Checkpoint provider/instrument/timeframe mismatch')
            return obj
