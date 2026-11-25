"""Deploy anahtarinin GitHub Secret'a yapistirilirken bozulan bicimlerinin onarilmasi."""
import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "ssh_key_normalize.py"
spec = importlib.util.spec_from_file_location("ssh_key_normalize", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

pytestmark = pytest.mark.skipif(shutil.which("ssh-keygen") is None, reason="ssh-keygen yok")


@pytest.fixture(scope="module")
def keypair(tmp_path_factory):
    folder = tmp_path_factory.mktemp("key")
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "test", "-f", str(folder / "k")], check=True)
    return (folder / "k").read_text(), (folder / "k.pub").read_text().split()[1]


def public_of(key_text, tmp_path):
    target = tmp_path / "out"
    target.write_text(key_text)
    target.chmod(0o600)
    result = subprocess.run(["ssh-keygen", "-y", "-f", str(target)], capture_output=True, text=True)
    return result.stdout.split()[1] if result.returncode == 0 else None


def mangle(key: str) -> dict[str, str]:
    lines = key.strip().split("\n")
    return {
        "duzgun": key,
        "sonda satir sonu yok": key.strip(),
        "windows satir sonlari": key.replace("\n", "\r\n"),
        "tek satir (satir sonlari bosluk)": " ".join(lines),
        "satir sonu bosluklari": "\n".join(line + "   " for line in lines),
        "girintili ve bos satirli": "\n\n".join("    " + line for line in lines),
        "yazi olarak \\n": "\\n".join(lines),
        "basinda ve sonunda fazladan metin": "ozel anahtar:\n" + key + "\n(buraya kadar)",
        # Canli durum (2026-11-25): yalnizca govde yapistirilmis; tani "uzunluk=328 satir=5 BEGIN=yok END=yok".
        "yalnizca govde (baslik ve bitis satiri yok)": "\n".join(lines[1:-1]),
        "bitis satiri yok": "\n".join(lines[:-1]),
        "baslik satiri yok": "\n".join(lines[1:]),
        "govde tek satir": "".join(lines[1:-1]),
                "terminal 60 sutunda sarmis": "\n".join(part for line in lines for part in (line[:40], line[40:]) if part),
    }


def test_every_common_paste_damage_is_repaired_to_the_same_key(keypair, tmp_path):
    key, public = keypair
    assert public_of(key, tmp_path) == public
    for name, damaged in mangle(key).items():
        repaired = module.normalize(damaged)
        assert public_of(repaired, tmp_path) == public, name
        assert repaired.endswith("-----\n") and "\r" not in repaired, name


def test_damage_that_ssh_itself_rejects(keypair, tmp_path):
    """Onarimin gercekten gerekli oldugunu gosterir: ssh bu bicimleri oldugu gibi okuyamaz."""
    key, _ = keypair
    damaged = mangle(key)
    assert public_of(damaged["tek satir (satir sonlari bosluk)"], tmp_path) is None
    assert public_of(damaged["yazi olarak \\n"], tmp_path) is None


def test_bare_body_without_the_openssh_signature_is_not_wrapped():
    """Baslik eklemek yalnizca govde OpenSSH imzasiyla basliyorsa yapilir; rastgele metin anahtar sayilmaz."""
    for bad in ("QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo=" * 8, "AAAAC3NzaC1lZDI1NTE5AAAAIabc" * 10):
        with pytest.raises(ValueError, match="blogu bulunamadi"):
            module.normalize(bad)


@pytest.mark.parametrize("bad, expected", [
    ("", "blogu bulunamadi"),
    ("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIabc github-deploy", "blogu bulunamadi"),  # acik anahtar yapistirilmis
    ("-----BEGIN OPENSSH PRIVATE KEY-----\nAAAA", "blogu bulunamadi"),  # govde anahtar degil
    ("-----BEGIN OPENSSH PRIVATE KEY-----\n***\n-----END OPENSSH PRIVATE KEY-----", "beklenmeyen karakter"),
    ("-----BEGIN OPENSSH PRIVATE KEY-----\n-----END OPENSSH PRIVATE KEY-----", "beklenmeyen karakter"),
])
def test_unrepairable_input_is_rejected_with_a_reason(bad, expected):
    with pytest.raises(ValueError, match=expected):
        module.normalize(bad)


def test_cli_writes_a_private_file_and_never_prints_the_key(keypair, tmp_path):
    key, public = keypair
    out = tmp_path / "deploy_key"
    env = {**os.environ, "VPS_SSH_KEY": key.replace("\n", "\r\n")}
    result = subprocess.run(["python3", str(SCRIPT), str(out)], env=env, capture_output=True, text=True)
    assert result.returncode == 0 and result.stdout == "" and result.stderr == ""
    assert oct(out.stat().st_mode & 0o777) == "0o600"
    assert public_of(out.read_text(), tmp_path) == public

    body = key.split("\n")[1]
    broken = subprocess.run(["python3", str(SCRIPT), str(tmp_path / "x")], capture_output=True, text=True,
                            env={**os.environ, "VPS_SSH_KEY": key.replace("-----END", "---SON")})
    assert broken.returncode == 1 and "::error::VPS_SSH_KEY okunamadi" in broken.stdout
    assert "BEGIN=var END=yok" in broken.stdout
    assert body not in broken.stdout and body not in broken.stderr  # anahtar icerigi asla yazilmaz
    assert not (tmp_path / "x").exists()
