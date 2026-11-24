import json
import os
from trade_gateway.control import LocalControl


def test_only_matching_local_run_requests_graceful_shutdown(tmp_path):
    stopped=[]
    control=LocalControl(tmp_path,lambda:stopped.append(True))
    control.start()
    control.stopfile.write_text(json.dumps({'pid':os.getpid(),'run_id':'wrong'}))
    assert not control.check_stop() and not stopped
    control.stopfile.write_text(json.dumps({'pid':os.getpid(),'run_id':control.run_id}))
    assert control.check_stop() and stopped
    control.close()
    assert not control.pidfile.exists() and not control.stopfile.exists()


def test_existing_gateway_control_record_is_not_overwritten(tmp_path):
    control=LocalControl(tmp_path,lambda:None)
    control.pidfile.write_text('{"pid":123,"run_id":"existing"}')
    try:
        control.start()
        assert False,'Must reject an existing control record'
    except FileExistsError:
        pass
    control.close()
    assert json.loads(control.pidfile.read_text())['run_id']=='existing'
