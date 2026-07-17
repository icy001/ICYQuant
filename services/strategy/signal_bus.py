"""
Signal event bus.
"""

from __future__ import annotations


class SignalBus:
    def __init__(self):
        self._handlers = []

    def subscribe(
        self,
        handler,
    ):
        self._handlers.append(handler)

    async def publish(
        self,
        signal,
    ):
        for handler in self._handlers:
            await handler(signal)