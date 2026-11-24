import unittest
from dataclasses import replace
import test_v8_structure_ledger as fixtures_v8
from unified_forex.structure_ledger import StructureLedger


class V9RecoveryAudit(unittest.TestCase):
    def test_checkpoint_is_owned_and_cannot_mutate_live_ledger(self):
        f=fixtures_v8.HistoricalFVG().frame();ledger=StructureLedger();ledger.consume(f,.01)
        before=ledger.view();checkpoint=ledger.checkpoint()
        checkpoint['body']['events'][0]['low']=1
        self.assertEqual(ledger.view(),before)
    def test_incremental_data_from_another_source_is_not_same_ledger(self):
        f=fixtures_v8.HistoricalFVG().frame();ledger=StructureLedger();ledger.consume(f,.01)
        last=f.bars[-1];b=replace(last,open_time_ms=last.close_time_ms,close_time_ms=last.close_time_ms+f.duration_ms,source='different-provider')
        update=replace(f,bars=(b,),as_of_ms=b.close_time_ms)
        with self.assertRaisesRegex(ValueError,'source'):ledger.consume(update,.01)
