"""Binance Futures liquidation WebSocket listener.

Maintains a small in-memory cache of recent liquidation events from Binance
USDⓈ-M Futures.

This module is responsible only for transport/state:
- connects to Binance WebSocket,
- receives liquidation events,
- normalizes the stream payload into provider-style dictionaries,
- keeps a bounded recent-event cache,
- reconnects automatically after disconnects.

Directional interpretation remains inside liquidation.py.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from typing import Deque, Dict, List, Optional, Set

import websockets
from websockets.exceptions import (
    ConnectionClosed,
    WebSocketException,
)


logger = logging.getLogger(
    "market_ai.liquidation_stream"
)


class LiquidationStream:
    """Background Binance liquidation stream with bounded in-memory cache."""

    BASE_URL = (
        "wss://fstream.binance.com/ws"
    )

    def __init__(
        self,
        symbols: Optional[List[str]] = None,
        max_events: int = 500,
        reconnect_delay: float = 5.0,
    ):
        self.symbols: Set[str] = {
            str(symbol).lower()
            for symbol in (
                symbols or []
            )
            if symbol
        }

        self.max_events = max(
            int(max_events),
            1,
        )

        self.reconnect_delay = max(
            float(reconnect_delay),
            0.5,
        )

        self._events: Deque[Dict] = deque(
            maxlen=self.max_events
        )

        self._task: Optional[
            asyncio.Task
        ] = None

        self._stop_event = asyncio.Event()

        self._lock = asyncio.Lock()

        self._connected = False

        self._last_error: Optional[str] = None

        self._last_event_timestamp: Optional[
            int
        ] = None

    # ------------------------------------------------------------------
    # URL
    # ------------------------------------------------------------------
    def _build_url(self) -> str:
        """Build combined stream URL for configured symbols."""
        if not self.symbols:
            raise ValueError(
                "At least one symbol is required."
            )

        streams = "/".join(
            f"{symbol}@forceOrder"
            for symbol in sorted(
                self.symbols
            )
        )

        return (
            f"{self.BASE_URL}/"
            f"{streams}"
        )

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------
    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    @property
    def last_event_timestamp(
        self,
    ) -> Optional[int]:
        return self._last_event_timestamp

    # ------------------------------------------------------------------
    # Start / Stop
    # ------------------------------------------------------------------
    async def start(self) -> None:
        """Start the background listener exactly once."""
        if self._task is not None:
            if not self._task.done():
                return

        self._stop_event.clear()

        self._task = asyncio.create_task(
            self._run(),
            name=(
                "market-ai-liquidation-stream"
            ),
        )

    async def stop(self) -> None:
        """Stop the background listener."""
        self._stop_event.set()

        task = self._task

        if task is None:
            self._connected = False
            return

        if (
            task is asyncio.current_task()
        ):
            return

        if not task.done():
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._task = None
        self._connected = False

    # ------------------------------------------------------------------
    # Cache access
    # ------------------------------------------------------------------
    async def get_events(
        self,
        symbol: Optional[str] = None,
        since_ms: Optional[int] = None,
    ) -> List[Dict]:
        """Return a snapshot of cached normalized liquidation events."""
        normalized_symbol = (
            str(symbol).upper()
            if symbol
            else None
        )

        cutoff = (
            int(since_ms)
            if since_ms is not None
            else None
        )

        async with self._lock:
            events = list(
                self._events
            )

        result = []

        for event in events:
            if (
                normalized_symbol
                and event.get(
                    "symbol"
                )
                != normalized_symbol
            ):
                continue

            timestamp = int(
                event.get(
                    "trade_time",
                    0,
                )
                or 0
            )

            if (
                cutoff is not None
                and timestamp < cutoff
            ):
                continue

            result.append(
                dict(event)
            )

        return result

    async def clear(self) -> None:
        """Clear cached liquidation events."""
        async with self._lock:
            self._events.clear()

        self._last_event_timestamp = None

    async def event_count(
        self,
        symbol: Optional[str] = None,
    ) -> int:
        """Return current cached event count."""
        events = await self.get_events(
            symbol=symbol
        )

        return len(events)

    # ------------------------------------------------------------------
    # Event normalization
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize(
        payload: Dict,
    ) -> Optional[Dict]:
        """Normalize Binance force-order WebSocket payload."""
        if not isinstance(
            payload,
            dict,
        ):
            return None

        order = payload.get(
            "o"
        )

        if not isinstance(
            order,
            dict,
        ):
            return None

        symbol = order.get(
            "s"
        )

        side = order.get(
            "S"
        )

        price = order.get(
            "p"
        )

        average_price = order.get(
            "ap"
        )

        original_quantity = order.get(
            "q"
        )

        executed_quantity = order.get(
            "z"
        )

        trade_time = order.get(
            "T"
        )

        event_time = payload.get(
            "E"
        )

        if not symbol:
            return None

        if side not in (
            "BUY",
            "SELL",
        ):
            return None

        try:
            price_value = float(
                price
            )

            average_price_value = float(
                average_price
                or price
            )

            original_quantity_value = (
                float(
                    original_quantity
                )
            )

            executed_quantity_value = (
                float(
                    executed_quantity
                    or original_quantity
                )
            )

            trade_time_value = int(
                trade_time
                or event_time
                or 0
            )

            event_time_value = int(
                event_time
                or trade_time
                or 0
            )

        except (
            TypeError,
            ValueError,
        ):
            return None

        if (
            price_value <= 0
            or executed_quantity_value <= 0
        ):
            return None

        return {
            "symbol": str(
                symbol
            ).upper(),

            "price": price_value,

            "average_price": (
                average_price_value
            ),

            "original_quantity": (
                original_quantity_value
            ),

            "executed_quantity": (
                executed_quantity_value
            ),

            "side": side,

            "trade_time": (
                trade_time_value
            ),

            "update_time": (
                event_time_value
            ),

            "stream_event_time": (
                event_time_value
            ),

            "position_side": order.get(
                "ps"
            ),

            "order_type": order.get(
                "o"
            ),

            "time_in_force": order.get(
                "f"
            ),

            "execution_type": order.get(
                "x"
            ),

            "status": order.get(
                "X"
            ),
        }

    # ------------------------------------------------------------------
    # Listener
    # ------------------------------------------------------------------
    async def _run(self) -> None:
        """Run the reconnecting WebSocket listener."""
        while not self._stop_event.is_set():
            url = None

            try:
                url = self._build_url()

                logger.info(
                    "Connecting liquidation stream: %s",
                    url,
                )

                async with websockets.connect(
                    url,
                    open_timeout=15,
                    close_timeout=5,
                    ping_interval=20,
                    ping_timeout=20,
                    max_size=2 * 1024 * 1024,
                ) as websocket:
                    self._connected = True
                    self._last_error = None

                    logger.info(
                        "Liquidation stream connected."
                    )

                    while not self._stop_event.is_set():
                        raw = await asyncio.wait_for(
                            websocket.recv(),
                            timeout=45,
                        )

                        payload = json.loads(
                            raw
                        )

                        event = self._normalize(
                            payload
                        )

                        if event is None:
                            continue

                        async with self._lock:
                            self._events.append(
                                event
                            )

                        self._last_event_timestamp = (
                            event.get(
                                "trade_time"
                            )
                        )

                        logger.debug(
                            "Liquidation event received: %s",
                            event,
                        )

            except asyncio.TimeoutError:
                # No liquidation event arrived within the local receive
                # timeout. The connection may still be healthy, so simply
                # reconnect to keep the listener fresh.
                logger.debug(
                    "Liquidation stream receive timeout."
                )

            except (
                ConnectionClosed,
                WebSocketException,
                OSError,
            ) as e:
                self._last_error = str(
                    e
                )

                logger.warning(
                    "Liquidation stream disconnected: %s",
                    e,
                )

            except (
                json.JSONDecodeError,
                TypeError,
                ValueError,
            ) as e:
                self._last_error = str(
                    e
                )

                logger.warning(
                    "Invalid liquidation stream payload: %s",
                    e,
                )

            except Exception as e:
                self._last_error = str(
                    e
                )

                logger.exception(
                    "Unexpected liquidation stream error."
                )

            finally:
                self._connected = False

            if self._stop_event.is_set():
                break

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.reconnect_delay,
                )

            except asyncio.TimeoutError:
                continue

        self._connected = False

        logger.info(
            "Liquidation stream stopped."
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
_default_stream: Optional[
    LiquidationStream
] = None


def get_liquidation_stream(
    symbols: Optional[List[str]] = None,
) -> LiquidationStream:
    """Return the process-wide liquidation stream instance.

    If a stream already exists, its existing configuration is preserved.
    """
    global _default_stream

    if _default_stream is None:
        _default_stream = LiquidationStream(
            symbols=symbols,
            max_events=500,
        )

    return _default_stream