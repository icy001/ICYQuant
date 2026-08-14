"""Order repository boundary (Commit 33 Part 1.2).

Only ``save`` / ``get`` / ``update`` - no validation, no risk, no trading
decisions.  Concrete adapters (PostgreSQL / Redis / Event Store) can be added
later without touching the domain or the service.
"""

from __future__ import annotations

from typing import Dict, Optional, Protocol, runtime_checkable

from services.order.domain.order import Order


class OrderPersistenceError(RuntimeError):
    """Raised when the repository cannot persist an order."""


@runtime_checkable
class OrderRepository(Protocol):
    """Persistence boundary for orders."""

    def save(self, order: Order) -> None: ...

    def get(self, order_id: str) -> Optional[Order]: ...

    def update(self, order: Order) -> None: ...


class InMemoryOrderRepository:
    """In-memory repository for tests and single-process deployments.

    ``fail_on_save`` / ``fail_on_update`` inject persistence failures so the
    service's fail-closed behaviour can be verified.
    """

    def __init__(self) -> None:
        self._orders: Dict[str, Order] = {}
        self.fail_on_save = False
        self.fail_on_update = False

    def save(self, order: Order) -> None:
        if self.fail_on_save:
            raise OrderPersistenceError("order repository unavailable (injected)")
        self._orders[order.order_id] = order

    def get(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)

    def update(self, order: Order) -> None:
        if self.fail_on_update:
            raise OrderPersistenceError("order repository unavailable (injected)")
        if order.order_id not in self._orders:
            raise OrderPersistenceError(
                f"cannot update unknown order {order.order_id}"
            )
        self._orders[order.order_id] = order
