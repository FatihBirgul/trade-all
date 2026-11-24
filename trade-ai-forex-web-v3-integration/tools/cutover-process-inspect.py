"""Windows read-only process parameters; never exports credentials or account IDs."""
import ctypes as c
from ctypes import wintypes as w
import json
from pathlib import Path

SAFE = {'MT5_ANALYSIS_POLICY', 'MT5_EXPECTED_REAL_SERVER', 'MT5_EXPECTED_REAL_CURRENCY',
        'MT5_SYMBOL_MAP', 'MT5_BROKER_HOURS', 'MT5_MAX_SPREAD', 'MT5_SPREAD_POLICY_FILE',
        'V2_CHART_GIT_ROOT', 'V2_CANDLESTICK_FILE', 'V2_CANDLESTICK_SHA256', 'PYTHONPATH',
        'PYTHONDONTWRITEBYTECODE', 'VIRTUAL_ENV'}

def inspect(pid):
    kernel = c.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    kernel.OpenProcess.restype = w.HANDLE
    kernel.ReadProcessMemory.argtypes = [w.HANDLE, c.c_void_p, c.c_void_p, c.c_size_t, c.POINTER(c.c_size_t)]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    handle = kernel.OpenProcess(0x410, False, pid)
    if not handle:
        raise OSError('Cannot read process parameters')
    def read(address, size):
        buf = c.create_string_buffer(size); count = c.c_size_t()
        kernel.ReadProcessMemory(handle, address, buf, size, c.byref(count))
        if not count.value:
            raise OSError('Cannot read process memory')
        return buf.raw[:count.value]
    def ptr(address):
        return int.from_bytes(read(address, 8), 'little')
    def unicode_string(address):
        length = int.from_bytes(read(address, 2), 'little')
        return read(ptr(address + 8), length).decode('utf-16-le')
    try:
        # PROCESS_BASIC_INFORMATION on this 64-bit Windows host.
        info = (c.c_void_p * 6)()
        nt = c.WinDLL('ntdll').NtQueryInformationProcess
        nt.argtypes = [w.HANDLE, w.ULONG, c.c_void_p, w.ULONG, c.c_void_p]
        if nt(handle, 0, c.byref(info), c.sizeof(info), None):
            raise OSError('Process query failed')
        params = ptr(info[1] + 0x20)
        environment = ptr(params + 0x80)
        raw = b''
        for offset in range(0, 262144, 1024):
            raw += read(environment + offset, 1024)
            end = next((i for i in range(0, len(raw)-3, 2) if raw[i:i+4] == b'\0\0\0\0'), None)
            if end is not None:
                text = raw[:end].decode('utf-16-le', errors='strict')
                break
        else:
            raise OSError('Environment too large')
        env = dict(item.split('=', 1) for item in text.split('\0') if '=' in item and not item.startswith('='))
        unknown = [k for k in env if k.startswith(('MT5_', 'V2_')) and k not in SAFE]
        return {'pid': pid, 'cwd': unicode_string(params + 0x38),
                'safe_environment': {k: env[k] for k in sorted(SAFE) if k in env},
                'unretained_trading_environment_key_count': len(unknown),
                'credentials_exported': False, 'account_number_exported': False}
    finally:
        kernel.CloseHandle(handle)

if __name__ == '__main__':
    import sys
    result = inspect(int(sys.argv[1]))
    Path(sys.argv[2]).write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))
