"""bootstrap.sh'nin giris, dogrulama ve cikti adimlari (sistemde degisiklik yapan adimlar test modunda atlanir)."""
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / "deploy" / "bootstrap.sh"
KEY = ("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
       "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")  # RFC 8032 test anahtari

pytestmark = pytest.mark.skipif(shutil.which("ssh-keygen") is None, reason="ssh-keygen yok")


def run(tmp_path, answers, **extra):
    tty = tmp_path / "tty"
    tty.write_text("\n".join(answers) + "\n")
    hostkeys = tmp_path / "hostkeys"
    hostkeys.mkdir(exist_ok=True)
    (hostkeys / "ssh_host_ed25519_key.pub").write_text("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHOSTKEY root@vps\n")
    env = {**os.environ, "BOOTSTRAP_DRY": "1", "BOOTSTRAP_TTY": str(tty), "ENV_FILE": str(tmp_path / "etc" / "tradebot.env"),
           "DEPLOY_HOME": str(tmp_path / "home"), "SSH_HOST_KEYS": str(hostkeys), "VENV_PY": sys.executable,
           "VPS_IP": "203.0.113.7", **extra}
    return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=60)


def test_happy_path_writes_env_and_prints_secrets_without_leaking_inputs(tmp_path):
    result = run(tmp_path, ["  exnsk-live-abc123  ", KEY, "152706877", "https://gw.exness.example/"])
    assert result.returncode == 0, result.stderr
    env_file = tmp_path / "etc" / "tradebot.env"
    assert stat.S_IMODE(env_file.stat().st_mode) == 0o600
    content = env_file.read_text()
    assert "EXNESS_API_KEY='exnsk-live-abc123'" in content and f"EXNESS_PRIVATE_KEY='{KEY}'" in content
    assert "EXNESS_ACCOUNT_ID='152706877'" in content and "EXNESS_GATEWAY_HOST='gw.exness.example'" in content

    shown = result.stdout + result.stderr
    assert KEY not in shown and "exnsk-live-abc123" not in shown  # girilen sirlar ekrana yazilmaz
    assert "VPS_HOST" in shown and "203.0.113.7" in shown and "VPS_USER" in shown and "deploy" in shown
    assert "203.0.113.7 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHOSTKEY" in shown  # VPS_KNOWN_HOSTS
    assert "-----BEGIN OPENSSH PRIVATE KEY-----" in shown
    assert shown.index("VPS_KNOWN_HOSTS") < shown.index("-----BEGIN OPENSSH PRIVATE KEY-----")
    public = (tmp_path / "home" / ".ssh" / "github_deploy.pub").read_text().strip()
    assert public in (tmp_path / "home" / ".ssh" / "authorized_keys").read_text()

    # Dosya hem kabuk hem servis tarafindan okunabilir olmali
    loaded = subprocess.run(["bash", "-c", f"set -a; . '{env_file}'; echo \"$EXNESS_ACCOUNT_ID|$EXNESS_GATEWAY_HOST\""],
                            capture_output=True, text=True)
    assert loaded.stdout.strip() == "152706877|gw.exness.example"


def test_invalid_values_are_rejected_then_accepted_on_retry(tmp_path):
    bad = ["exnsk-live-abc123", "kisa-anahtar", "12ab", "gateway"]
    good = ["exnsk-live-abc123", KEY, "152706877", "gw.exness.example"]
    result = run(tmp_path, bad + good)
    assert result.returncode == 0, result.stderr
    assert "128 hex" in result.stderr and "hesap numarasi" in result.stderr and "gateway host" in result.stderr
    assert "kisa-anahtar" not in result.stdout + result.stderr
    assert "EXNESS_ACCOUNT_ID='152706877'" in (tmp_path / "etc" / "tradebot.env").read_text()


def test_key_with_mismatched_public_half_is_rejected(tmp_path):
    broken = KEY[:64] + "00" * 32
    result = run(tmp_path, ["exnsk-live-abc123", broken, "152706877", "gw.exness.example"] * 3)
    assert result.returncode == 1 and "ozel anahtar gecerli degil" in result.stderr
    assert not (tmp_path / "etc" / "tradebot.env").exists()


def test_values_that_could_break_the_env_file_are_rejected(tmp_path):
    result = run(tmp_path, ["bad'key; rm -rf /", KEY, "152706877", "gw.exness.example"] * 3)
    assert result.returncode == 1 and "API anahtari" in result.stderr
    assert not (tmp_path / "etc" / "tradebot.env").exists()


def test_rerun_keeps_existing_values_and_key(tmp_path):
    first = run(tmp_path, ["exnsk-live-abc123", KEY, "152706877", "gw.exness.example"])
    assert first.returncode == 0
    private = (tmp_path / "home" / ".ssh" / "github_deploy").read_text()
    before = (tmp_path / "etc" / "tradebot.env").read_text()
    second = run(tmp_path, [""])  # "degistirmek istiyor musunuz?" -> Enter (hayir)
    assert second.returncode == 0, second.stderr
    assert (tmp_path / "etc" / "tradebot.env").read_text() == before
    assert (tmp_path / "home" / ".ssh" / "github_deploy").read_text() == private
    authorized = (tmp_path / "home" / ".ssh" / "authorized_keys").read_text().strip().splitlines()
    assert len(authorized) == 1  # anahtar ikinci kez eklenmedi


def test_nonstandard_ssh_port_is_reported(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    sshd = fake_bin / "sshd"
    sshd.write_text("#!/bin/sh\necho 'port 2222'\n")
    sshd.chmod(0o755)
    result = run(tmp_path, ["exnsk-live-abc123", KEY, "152706877", "gw.exness.example"],
                 PATH=f"{fake_bin}:{os.environ['PATH']}")
    assert result.returncode == 0
    assert "VPS_PORT" in result.stdout and "[203.0.113.7]:2222 ssh-ed25519" in result.stdout
