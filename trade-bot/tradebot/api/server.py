"""FastAPI uygulamasi. Varsayilan olarak yalnizca 127.0.0.1'e baglanir; disa acilis ters vekil ile yapilir."""

from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import FastAPI

from ..app import Bot
from .routes import build_router


def create_app(bot: Bot, *, clock: Callable[[], float] = time.time, stream_interval: float = 2.0) -> FastAPI:
    app = FastAPI(title="Trade Bot", docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(build_router(bot, clock, stream_interval))
    return app


async def serve(bot: Bot, bind: str) -> None:
    import uvicorn

    host, _, port = bind.rpartition(":")
    config = uvicorn.Config(create_app(bot), host=host or "127.0.0.1", port=int(port), log_level="warning",
                            access_log=False)
    await uvicorn.Server(config).serve()
