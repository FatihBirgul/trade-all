import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('cutover_runtime',ROOT/'tools/cutover-runtime.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class GuardTests(unittest.TestCase):
    def test_trading_and_account_control_calls_are_not_exposed(self):
        proxy=module.ReadOnlyTerminal(object())
        for name in ['order_send','order_check','login','logout','orders_get','positions_get']:
            with self.assertRaises(AttributeError):getattr(proxy,name)

    def test_read_methods_and_constants_are_passed_through(self):
        class Fake:
            symbol_info=lambda self,s:s
            SYMBOL_CALC_MODE_FOREX=0
        proxy=module.ReadOnlyTerminal(Fake())
        self.assertEqual(proxy.symbol_info('EURUSDc'),'EURUSDc')
        self.assertEqual(proxy.SYMBOL_CALC_MODE_FOREX,0)

    def test_protected_ports_require_explicit_live_operation_flag(self):
        for port in [5173,8005,8006,8007]:
            r=subprocess.run([sys.executable,'-B',str(ROOT/'tools/cutover-runtime.py'),'--release','missing','--config','missing','--config-sha256','0'*64,'--manifest','missing','--port',str(port)],capture_output=True,text=True)
            self.assertEqual(r.returncode,2)
            self.assertIn('Protected port',r.stderr)

    def test_config_tampering_blocks_before_mt5_import(self):
        config=ROOT/'release/cutover/runtime-config.json'
        r=subprocess.run([sys.executable,'-B',str(ROOT/'tools/cutover-runtime.py'),'--release','missing','--config',str(config),'--config-sha256','0'*64,'--manifest','missing','--port','18006'],capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0)
        self.assertIn('Exact approved runtime configuration required',r.stderr)

if __name__=='__main__':unittest.main(verbosity=2)
