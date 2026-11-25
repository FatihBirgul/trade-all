"""Surecin parcalarini birbirine baglar: istemci, depo, bildirimci, bot ve kontrol API'si."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from .api import auth
from .api.server import serve
from .app import Bot
from .config import Settings
from .exness.client import ExnessClient
from .notify.expo import ExpoNotifier
from .store.repo import Repo


@dataclass
class Runtime:
    settings: Settings
    client: ExnessClient
    repo: Repo
    bot: Bot

    async def run(self) -> None:
        """Bot ve API ayni olay dongusunde calisir; biri durursa surec biter ve systemd yeniden baslatir."""
        tasks = [asyncio.create_task(self.bot.run(), name="bot"),
                 asyncio.create_task(serve(self.bot, self.settings.api_bind), name="api")]
        try:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                task.result()  # hata varsa yukari tasinsin
        finally:
            closer = getattr(self.bot.notifier, "aclose", None)
            if closer is not None:
                await closer()  # yoldaki bildirimler veritabani kapanmadan tamamlansin
            await self.client.aclose()
            self.repo.close()


def build_notifier(repo: Repo):
    """Kayitli cihaz yoksa ExpoNotifier zaten hicbir sey gondermez."""
    return ExpoNotifier(repo)


def build_runtime(settings: Settings) -> Runtime:
    client = ExnessClient(settings)
    repo = Repo(settings.db_path)
    bot = Bot(settings, client, repo, build_notifier(repo))
    return Runtime(settings, client, repo, bot)


def create_pair_code(settings: Settings) -> str:
    """Sunucuda calistirilir; calisan servisle ayni veritabanina tek kullanimlik kod yazar."""
    repo = Repo(settings.db_path)
    try:
        return auth.create_pair_code(repo, now=time.time())
    finally:
        repo.close()


def revoke_tokens(settings: Settings) -> int:
    """Tum cihaz token'larini siler (telefon kaybolursa). Cihazlar yeniden eslestirilmelidir."""
    repo = Repo(settings.db_path)
    try:
        repo.clear_pair_codes()
        return repo.clear_tokens()
    finally:
        repo.close()
