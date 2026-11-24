"""Isolated bounded in-memory result registry; no product DB or filesystem paths."""
from collections import OrderedDict
from hashlib import sha256
import json
from threading import RLock
from forex.contracts import canonical


class ExperimentRegistry:
    def __init__(self,capacity=32,max_bytes=8_000_000):
        if type(capacity) is not int or not 1<=capacity<=128 or type(max_bytes) is not int or not 1000<=max_bytes<=32_000_000:
            raise ValueError('Invalid bounded registry')
        self.capacity=capacity;self.max_bytes=max_bytes;self.items=OrderedDict();self.bytes=0;self.lock=RLock()
    def record(self,result):
        experiment_id=result.get('experiment_id')
        if not isinstance(experiment_id,str) or len(experiment_id)!=64 or any(c not in '0123456789abcdef' for c in experiment_id):raise ValueError('Invalid experiment ID')
        raw=canonical(result);size=len(raw.encode('utf-8'));digest=sha256(raw.encode()).hexdigest()
        if size>self.max_bytes:raise ValueError('Result exceeds registry budget')
        with self.lock:
            if experiment_id in self.items:
                if self.items[experiment_id][1]!=digest:raise ValueError('Same frozen experiment produced different result')
            else:
                while self.items and (len(self.items)>=self.capacity or self.bytes+size>self.max_bytes):
                    _,entry=self.items.popitem(last=False);self.bytes-=entry[2]
                self.items[experiment_id]=(raw,digest,size);self.bytes+=size
        return {'experiment_id':experiment_id,'result_sha256':digest,'persistence':'PROCESS_MEMORY','restart_semantics':'cleared_on_restart','independent_evidence':False}
    def get(self,experiment_id):
        with self.lock:
            row=self.items.get(experiment_id)
            return None if row is None else json.loads(row[0])
