"""
Trade application service.
"""

from __future__ import annotations

from .events import TradeCreated
from .exceptions import DuplicateExecutionError
from .mapper import TradeMapper
from .publisher import TradeEventPublisher


class TradeService:
    def __init__(
        self,
        repository,
        publisher=None,
    ):
        self.repository = repository
        self.publisher = (
            publisher
            or TradeEventPublisher()
        )

    async def create_from_execution(
        self,
        report,
        order,
    ):
        execution_id = getattr(
            report,
            "execution_id",
            None,
        )

        if execution_id:
            existing = await self.repository.find_by_execution_id(
                execution_id
            )

            if existing:
                raise DuplicateExecutionError(
                    execution_id
                )

        trade = TradeMapper.from_execution_report(
            report,
            order,
        )

        model = await self.repository.save(trade)

        await self.publisher.publish(
            TradeCreated(
                trade_id=model.id,
                order_id=model.order_id,
            )
        )

        return TradeMapper.to_domain(model)