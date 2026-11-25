import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "status.sh"


def run(tmp_path, body, *args):
    target = tmp_path / "health.json"
    if body is not None:
        target.write_text(body)
    env = {**os.environ, "TRADEBOT_HEALTH_URL": f"file://{target}"}
    return subprocess.run(["bash", str(SCRIPT), *args], env=env, capture_output=True, text=True, timeout=30)


def test_reports_connected_streams(tmp_path):
    body = '{"status":"ok","stream_connected":true,"halted":false,"last_scan":{"scanned":30,"errors":0}}'
    result = run(tmp_path, body)
    assert result.returncode == 0
    assert f"saglik: {body}" in result.stdout and "akislar: bagli" in result.stdout


def test_disconnected_streams_are_reported_as_failure(tmp_path):
    result = run(tmp_path, '{"status":"ok","stream_connected":false}', "--wait", "0")
    assert result.returncode == 2
    assert "BAGLI DEGIL" in result.stderr and "stream_connected" in result.stdout


def test_no_answer_is_a_failure(tmp_path):
    result = run(tmp_path, None)
    assert result.returncode == 1 and "yanit yok" in result.stderr



def test_prints_the_scan_summary_when_the_server_has_one(tmp_path):
    summary = tmp_path / "summary.json"
    summary.write_text('{"scans":4,"would_open":1}')
    target = tmp_path / "health.json"
    target.write_text('{"status":"ok","stream_connected":true}')
    env = {**os.environ, "TRADEBOT_HEALTH_URL": f"file://{target}", "TRADEBOT_SUMMARY_URL": f"file://{summary}"}
    result = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0 and 'ozet: {"scans":4,"would_open":1}' in result.stdout


def test_missing_summary_on_an_older_server_is_not_an_error(tmp_path):
    result = run(tmp_path, '{"status":"ok","stream_connected":true}')
    assert result.returncode == 0 and "ozet:" not in result.stdout
