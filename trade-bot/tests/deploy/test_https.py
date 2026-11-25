"""HTTPS disa acilis betigi ve eslestirme komutu (sistem degisikligi yapmayan test kipi)."""
import os
import subprocess
import sys
from pathlib import Path

DEPLOY = Path(__file__).parents[2] / "deploy"


def setup(tmp_path, ip):
    env = {**os.environ, "CADDY_DRY": "1", "CADDYFILE": str(tmp_path / "Caddyfile"), "VPS_IP": ip}
    return subprocess.run(["bash", str(DEPLOY / "setup-https.sh")], env=env, capture_output=True, text=True, timeout=30)


def test_host_from_ip(tmp_path):
    result = setup(tmp_path, "203.0.113.7")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "https://203-0-113-7.sslip.io"


def test_caddyfile_proxies_only_to_loopback_and_redirects_http(tmp_path):
    setup(tmp_path, "203.0.113.7")
    text = (tmp_path / "Caddyfile").read_text()
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
    assert "203-0-113-7.sslip.io {" in lines and "__HOST__" not in text
    assert [line for line in lines if line.startswith("reverse_proxy")] == ["reverse_proxy 127.0.0.1:8090"]
    # Otomatik HTTPS acik kalmali: http:// sitesi ya da auto_https kapatma yok -> HTTP istekleri HTTPS'e yonlenir
    assert not any(line.startswith("http://") or "auto_https" in line or line.startswith("tls internal") for line in lines)
    assert not any(line.startswith("log") for line in lines)  # token loga dusmesin
    assert 'Strict-Transport-Security "max-age=31536000"' in text and "max_size 64KB" in text
    assert "admin off" in lines


def test_invalid_ip_rejected(tmp_path):
    for bad in ("evil.com", "1.2.3", "999.1.1.1", "1.2.3.4; rm -rf /", "1.2.3.4/x"):
        result = setup(tmp_path, bad)
        assert result.returncode != 0, bad
        assert not (tmp_path / "Caddyfile").exists()


def test_rerun_is_idempotent(tmp_path):
    setup(tmp_path, "203.0.113.7")
    first = (tmp_path / "Caddyfile").read_text()
    setup(tmp_path, "203.0.113.7")
    assert (tmp_path / "Caddyfile").read_text() == first


def pair(tmp_path, script_body):
    fake_python = tmp_path / "python"
    fake_python.write_text(f"#!/bin/sh\n{script_body}\n")
    fake_python.chmod(0o755)
    env_file = tmp_path / "tradebot.env"
    env_file.write_text("EXNESS_API_KEY='exnsk-SECRET'\nEXNESS_PRIVATE_KEY='PRIVATESECRET'\n")
    url_file = tmp_path / "public-url"
    url_file.write_text("https://203-0-113-7.sslip.io\n")
    env = {**os.environ, "ENV_FILE": str(env_file), "APP_DIR": str(tmp_path), "VENV_PY": str(fake_python),
           "URL_FILE": str(url_file), "RUN_AS": ""}
    return subprocess.run(["bash", str(DEPLOY / "tradebot-pair")], env=env, capture_output=True, text=True, timeout=30)


def test_pair_wrapper_never_echoes_env(tmp_path):
    result = pair(tmp_path, 'echo "INFO log satiri"; echo "$EXNESS_API_KEY" >&2; echo 482913')
    assert result.returncode == 0, result.stderr
    assert "482913" in result.stdout and "https://203-0-113-7.sslip.io" in result.stdout
    assert "SECRET" not in result.stdout + result.stderr


def test_pair_wrapper_reports_failure_without_details(tmp_path):
    result = pair(tmp_path, 'echo "ayar hatasi: $EXNESS_PRIVATE_KEY"; exit 2')
    assert result.returncode == 1 and "Kod uretilemedi" in result.stderr
    assert "PRIVATESECRET" not in result.stdout + result.stderr


def test_real_pair_command_output_is_a_code(tmp_path):
    """Sarmalayicinin bekledigi bicim, gercek `python -m tradebot pair` ciktisiyla ayni."""
    env = {**os.environ, "EXNESS_API_KEY": "k", "EXNESS_PRIVATE_KEY": "0" * 64, "EXNESS_ACCOUNT_ID": "1",
           "EXNESS_GATEWAY_HOST": "gw.example", "TRADEBOT_DB_PATH": str(tmp_path / "bot.db")}
    result = subprocess.run([sys.executable, "-m", "tradebot", "pair"], env=env, capture_output=True, text=True,
                            cwd=DEPLOY.parent, timeout=60)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1].isdigit() and len(result.stdout.strip().splitlines()[-1]) == 6
