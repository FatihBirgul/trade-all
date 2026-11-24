import unittest,json
from unittest.mock import Mock,patch
from fixtures import fixture,META
from unified_forex.pilot import export,reconcile
from unified_forex.providers import ContractMT5Provider
from forex.core import DataError


class SafeWindowsPilot(unittest.TestCase):
    def test_shareable_evidence_drops_sensitive_terminal_and_exception_fields(self):
        p=fixture();p.health=Mock(return_value={'connected':True,'login':123,'path':'C:\\secret','username':'private-user'})
        p.margin_for=Mock(return_value=12.5)
        r=export(p,('XAUUSD',));raw=json.dumps(r)
        for secret in ('C:\\secret','private-user','"login"','margin_free'):self.assertNotIn(secret,raw)
        self.assertEqual(r['symbols']['XAUUSD']['margin_samples'][0]['margin'],12.5)
        self.assertFalse(r['execution_permission']);self.assertEqual(r['mt5_validation'],'UNVERIFIED')
        with patch('unified_forex.pilot.diagnose',side_effect=DataError('password=secret account=123')):
            refused=export(p)
        self.assertNotIn('password',str(refused));self.assertEqual(refused['status'],'DATA_UNAVAILABLE')
        diff=reconcile({'XAUUSD':{**META,'tick_size':.1}},r)
        self.assertIn('tick_size',diff['differences']['XAUUSD'])
    def test_margin_is_readonly_and_execution_methods_remain_rejected(self):
        p=ContractMT5Provider.__new__(ContractMT5Provider)
        from threading import RLock
        p.lock=RLock();p.mt5=Mock();p.mt5.ORDER_TYPE_BUY=0;p.mt5.order_calc_margin.return_value=25
        p._symbol=Mock(return_value=('XAUUSD.broker',None))
        self.assertEqual(p.margin_for('XAUUSD','BUY',.01,2000),25)
        p.mt5.order_calc_margin.assert_called_once_with(0,'XAUUSD.broker',.01,2000)
        for method in ('order_send','order_check','positions_get'):
            with self.assertRaises(DataError):p._call(method)
        p.mt5.order_send.assert_not_called();p.mt5.order_check.assert_not_called()
