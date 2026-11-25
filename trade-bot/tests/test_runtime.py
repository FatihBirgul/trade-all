import re

from tests.exness.test_client import settings
from tradebot import __main__ as entry
from tradebot.api.auth import redeem_pair_code
from tradebot.runtime import build_runtime, create_pair_code
from tradebot.store.repo import Repo


def test_pair_command_prints_a_code_usable_by_the_service(tmp_path, monkeypatch, capsys):
    config = settings(TRADEBOT_DB_PATH=str(tmp_path / "bot.db"))
    monkeypatch.setattr(entry, "load_settings", lambda: config)
    assert entry.main(["pair"]) == 0
    code = capsys.readouterr().out.strip()
    assert re.fullmatch(r"[0-9]{6}", code)
    repo = Repo(config.db_path)
    import time
    assert redeem_pair_code(repo, code, now=time.time()) is not None


def test_unknown_argument_and_missing_settings_exit_cleanly(monkeypatch, capsys):
    assert entry.main(["nope"]) == 2

    def missing():
        raise ValueError("eksik ortam degiskeni: EXNESS_API_KEY")
    monkeypatch.setattr(entry, "load_settings", missing)
    assert entry.main(["pair"]) == 2


async def test_build_runtime_wires_bot_and_repo(tmp_path):
    config = settings(TRADEBOT_DB_PATH=str(tmp_path / "bot.db"))
    runtime = build_runtime(config)
    assert runtime.bot.repo is runtime.repo and runtime.bot.client is runtime.client
    assert runtime.repo.bot_state().halted is False
    await runtime.client.aclose()
    runtime.repo.close()
    assert create_pair_code(config).isdigit()
