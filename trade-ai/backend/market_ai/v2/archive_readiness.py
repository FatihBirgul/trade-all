"""Bounded read-only assessment of declared exact logical archive copies.

Not archive merging, signature validation or production restore authorization.
Every part must match the same reviewed logical manifest/domain cutoff. Split
histories and newer prefixes remain unsupported instead of silently combined.
"""
from pathlib import Path
from itertools import islice
from .archive_manifest import build_manifest,digest,VERSION as MANIFEST_VERSION
VERSION='v2-archive-copy-readiness-1'

def assess_copies(paths,expected,*,max_snapshots=10000):
    parts=tuple(islice(paths,9))
    if not 1<=len(parts)<=8:raise ValueError('One to eight explicit reviewed copy paths required')
    if type(max_snapshots) is not int or not 1<=max_snapshots<=100000:raise ValueError('Bounded snapshot budget required')
    if (not isinstance(expected,dict) or expected.get('status')!='PASS' or expected.get('version')!=MANIFEST_VERSION or
            digest({k:v for k,v in expected.items() if k!='manifest_id'})!=expected.get('manifest_id')):
        return {'version':VERSION,'status':'CORRUPT','reason':'reviewed_manifest_required','parts':[]}
    resolved=[Path(p).resolve() for p in parts]
    if len(set(resolved))!=len(resolved):raise ValueError('Duplicate copy paths do not provide separate evidence')
    output=[]
    for index,path in enumerate(resolved):
        actual=build_manifest(path,max_snapshots=max_snapshots)
        if actual.get('status')=='PASS':
            status='PASS' if actual==expected else 'MISMATCH';reason='logical_copy_and_domain_cutoff' if status=='PASS' else 'copy_or_cutoff_differs'
        elif not path.exists():status='INCOMPLETE';reason='declared_part_missing'
        else:status=actual['status'];reason=actual.get('reason','independent_audit_not_complete')
        output.append({'part':index,'status':status,'reason':reason,'manifest_id':actual.get('manifest_id')})
    order=('PASS','INCOMPLETE','MISMATCH','CORRUPT','ERROR')
    return {'version':VERSION,'status':max((p['status'] for p in output),key=order.index),
        'scope':'exact_logical_copies_only','parts':output,'expected_manifest_id':expected['manifest_id'],
        'signature_available':False,'restore_performed':False,
        'limitations':['Each file is independently audited at its read snapshot; no atomic multi-file snapshot or external authenticity proof.',
                       'No split-history reconstruction, prefix merge, repair, migration or deployment.']}
