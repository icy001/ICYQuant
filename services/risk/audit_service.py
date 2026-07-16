"""
Risk audit service.
"""

from __future__ import annotations

from datetime import datetime

from .events import RiskAuditEvent


class RiskAuditService:
    def __init__(
        self,
        repository,
    ):
        self.repository = repository

    async def record(
        self,
        order_id: str,
        account_id: str,
        result,
        rule=None,
    ):
        event = RiskAuditEvent(
            order_id=order_id,
            account_id=account_id,
            decision=result.decision.value,
            rule=rule,
            reason=result.reason,
            created_at=datetime.utcnow(),
        )

        await self.repository.save(event)

        return event