"""Giris noktasi.

    python -m tradebot         botu (ve kontrol API'sini) calistirir
    python -m tradebot pair    uygulama icin tek kullanimlik eslestirme kodu uretir
    python -m tradebot revoke  tum cihaz token'larini iptal eder (yeniden eslestirme gerekir)
"""

from __future__ import annotations

import asyncio
import logging
import sys

from .config import load_settings


def _logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        stream=sys.stdout)
    logging.getLogger("httpx").setLevel(logging.WARNING)  # istek satirlari (URL'ler) loga dusmesin


async def _serve() -> None:
    from .runtime import build_runtime

    runtime = build_runtime(load_settings())
    await runtime.run()


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    _logging()
    try:
        if argv[:1] == ["pair"]:
            from .runtime import create_pair_code

            print(create_pair_code(load_settings()))
            return 0
        if argv[:1] == ["revoke"]:
            from .runtime import revoke_tokens

            print(f"{revoke_tokens(load_settings())} token iptal edildi")
            return 0
        if argv:
            print(__doc__)
            return 2
        asyncio.run(_serve())
    except ValueError as exc:  # eksik/gecersiz ayar: sirlari yazmadan net mesaj
        logging.getLogger("tradebot").error("ayar hatasi: %s", exc)
        return 2
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
