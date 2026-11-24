"""Private startup attestation for a newly launched interpreter, not remote proof."""
import hashlib
import json
import marshal
import sys
import types


def _normalized(code):
    return code.replace(co_filename='', co_consts=tuple(
        _normalized(value) if isinstance(value, types.CodeType) else value for value in code.co_consts))


def loaded_fingerprint():
    functions = {}
    for name, module in sorted(list(sys.modules.items())):
        if not name.startswith('forex.') or module is None:
            continue
        for key, value in sorted(vars(module).items()):
            candidates = {key: value}
            if isinstance(value, type) and value.__module__ == name:
                candidates = {key+'.'+member: method for member, method in vars(value).items()}
            for qualified, candidate in candidates.items():
                if isinstance(candidate, (staticmethod, classmethod)):
                    candidate = candidate.__func__
                seen = set()
                while hasattr(candidate, '__wrapped__') and id(candidate) not in seen:
                    seen.add(id(candidate))
                    candidate = candidate.__wrapped__
                if isinstance(candidate, types.FunctionType) and candidate.__module__ == name:
                    functions[name+'.'+qualified] = hashlib.sha256(marshal.dumps(_normalized(candidate.__code__))).hexdigest()
    if not functions:
        raise RuntimeError('No loaded Forex functions to attest')
    return {'python_cache_tag': sys.implementation.cache_tag, 'function_count': len(functions),
            'loaded_function_code_sha256': hashlib.sha256(json.dumps(functions, sort_keys=True).encode()).hexdigest()}
