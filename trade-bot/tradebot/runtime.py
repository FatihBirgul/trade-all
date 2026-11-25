"""Surecin parcalarini birbirine baglar: istemci, depo, bildirimci, bot (ve kontrol API'si)."""

from __future__ import annotations

from dataclasses import dataclass

from .app import Bot
from .config import Settings
from .exness.client import ExnessClient
from .notify import NullNotifier
from .store.repo import Repo


@dataclass
class Runtime:
    settings: Settings
    client: ExnessClient
    repo: Repo
    bot: Bot

    async def run(self) -> None:
        try:
            await self.bot.run()
        finally:
            await self.client.aclose()
            self.repo.close()


def build_runtime(settings: Settings) -> Runtime:
    client = ExnessClient(settings)
    repo = Repo(settings.db_path)
    bot = Bot(settings, client, repo, NullNotifier())
    return Runtime(settings, client, repo, bot)


def create_pair_code(settings: Settings) -> str:
    raise NotImplementedError("eslestirme kontrol API'si ile gelir")
