from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator


class LocalEventBus:
    """Best-effort process-local UI hints; durable service messaging lives in MessageBusPort."""

    def __init__(self):
        self._subscribers: set[asyncio.Queue] = set()

    def publish(self, event: dict) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    async def subscribe(self) -> AsyncIterator[dict]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.add(queue)
        try:
            while True:
                try:
                    yield await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield {"type": "heartbeat"}
        finally:
            self._subscribers.discard(queue)
