"""
Execution report handler.
"""

from __future__ import annotations

from .mapper import OrderMapper
from .state_machine import OrderStateMachine


class ExecutionReportHandler:
    def __init__(self, repository):
        self.repository = repository

    async def process(self, report):
        model = await self.repository.get(report.order_id)

        if model is None:
            raise LookupError("order not found")

        model.status = OrderStateMachine.apply(
            model.status,
            report.transition,
        )

        model.filled_quantity = report.filled_quantity
        model.average_price = report.average_price

        await self.repository.update_with_version(model)

        return OrderMapper.to_domain(model)