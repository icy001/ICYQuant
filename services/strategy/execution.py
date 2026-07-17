"""
Strategy execution adapter.
"""

from __future__ import annotations

from .execution_result import ExecutionResult


class StrategyExecutionAdapter:
    def __init__(
        self,
        order_engine,
        mapper,
    ):
        self.order_engine = order_engine
        self.mapper = mapper

    async def execute(
        self,
        signal,
    ) -> ExecutionResult:
        command = self.mapper.map(signal)

        order = await self.order_engine.submit(command)

        return ExecutionResult(
            accepted=True,
            order_id=order.id,
        )