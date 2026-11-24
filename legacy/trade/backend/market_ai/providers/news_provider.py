"""News provider abstraction.

V1 ships a `NullNewsProvider` that honestly reports news as UNAVAILABLE rather
than fabricating headlines. When the user supplies a news API key later, add a
concrete provider (e.g. CryptoPanic / NewsAPI) implementing `get_news` and
register it in `get_news_provider`.
"""
from __future__ import annotations

from typing import List, Optional

from ..config import NEWS_PROVIDER


class NewsProvider:
    name = "abstract"
    available = False

    async def get_news(self, symbol: str) -> dict:
        raise NotImplementedError


class NullNewsProvider(NewsProvider):
    name = "none"
    available = False

    async def get_news(self, symbol: str) -> dict:
        return {
            "available": False,
            "provider": "none",
            "message": "News provider not configured. Technical analysis continues without news.",
            "articles": [],
            "sentiment": {"label": "neutral", "score": 0.0, "note": "News unavailable"},
        }


_news_provider: Optional[NewsProvider] = None


def get_news_provider() -> NewsProvider:
    global _news_provider
    if _news_provider is None:
        # Only NullNewsProvider is wired for V1; real providers slot in here.
        _news_provider = NullNewsProvider()
    return _news_provider
