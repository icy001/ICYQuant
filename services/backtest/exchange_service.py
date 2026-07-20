"""
Exchange service.
"""

from .execution_report import ExecutionReport


class ExchangeService:
    async def execute(
        self,
        order,
    ):
        return ExecutionReport(
            order_id=order.id,
            status="FILLED",
            filled_quantity=order.quantity,
        )