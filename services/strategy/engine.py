"""
Strategy engine.
"""

from __future__ import annotations

from .lifecycle import StrategyLifecycle


class StrategyEngine:
    def __init__(
        self,
        runtime,
    ):
        self.runtime = runtime
        self.state = StrategyLifecycle.CREATED

    async def start(self):
        self.state = StrategyLifecycle.RUNNING
        await self.runtime.on_start()

    async def stop(self):
        await self.runtime.on_stop()
        self.state = StrategyLifecycle.STOPPED

    async def on_market(
        self,
        event,
    ):
        return await self.runtime.on_market(event)