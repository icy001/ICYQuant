"""OrderRepository port — persistence boundary for orders.

Business code must NOT access the database directly. All access goes
through OrderService → OrderRepository.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from services.oms.domain.order import Order


class OrderRepository(ABC):
    """Abstract order repository."""

    @abstractmethod
    def get(self, order_id: str) -> Optional[Order]:
        """Get an order by ID. Returns None if not found."""

    @abstractmethod
    def save(self, order: Order) -> None:
        """Persist a new order."""

    @abstractmethod
    def update(self, order: Order) -> None:
        """Update an existing order."""

    @abstractmethod
    def find_by_client_order_id(self, client_order_id: str) -> Optional[Order]:
        """Find an order by client_order_id (for idempotency)."""

    @abstractmethod
    def find_by_parent_order_id(self, parent_order_id: str) -> List[Order]:
        """Find all child orders of a parent."""

    @abstractmethod
    def get_all(self) -> List[Order]:
        """Return all orders (for queries)."""


class InMemoryOrderRepository(OrderRepository):
    """Simple in-memory repository for testing and development."""

    def __init__(self) -> None:
        self._orders: Dict[str, Order] = {}
        self._by_client: Dict[str, str] = {}  # client_order_id → order_id

    def get(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)

    def save(self, order: Order) -> None:
        oid = order.order_id.order_id
        self._orders[oid] = order
        if order.order_id.client_order_id:
            self._by_client[order.order_id.client_order_id] = oid

    def update(self, order: Order) -> None:
        oid = order.order_id.order_id
        self._orders[oid] = order

    def find_by_client_order_id(self, client_order_id: str) -> Optional[Order]:
        oid = self._by_client.get(client_order_id)
        if oid is None:
            return None
        return self._orders.get(oid)

    def find_by_parent_order_id(self, parent_order_id: str) -> List[Order]:
        return [
            o for o in self._orders.values()
            if o.order_id.parent_order_id == parent_order_id
        ]

    def get_all(self) -> List[Order]:
        return list(self._orders.values())
