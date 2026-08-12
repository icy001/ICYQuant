"""
AdmissionRepository — idempotency store for Order Admission (spec section 15).

The same request_id must always produce the same decision: a retried request
must never create a second OMS order.  The repository caches the first final
decision per request_id; every subsequent evaluation returns the cached
result.
"""

from __future__ import annotations

from uuid import UUID

from .decision import OrderAdmissionDecision


class AdmissionRepository:

    def __init__(self):
        self._decisions: dict[UUID, OrderAdmissionDecision] = {}

    def get(
        self,
        request_id: UUID,
    ) -> OrderAdmissionDecision | None:

        return self._decisions.get(
            request_id
        )

    def save(
        self,
        decision: OrderAdmissionDecision,
    ) -> None:

        self._decisions[
            decision.request_id
        ] = decision

    def has(
        self,
        request_id: UUID,
    ) -> bool:

        return request_id in self._decisions

    def count(self) -> int:
        return len(self._decisions)

    def clear(self) -> None:
        self._decisions.clear()
