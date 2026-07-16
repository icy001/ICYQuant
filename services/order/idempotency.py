"""
Simple in-memory idempotency registry.

Production implementation:

Redis

or

Database Unique Index
"""

from __future__ import annotations

from uuid import UUID


class IdempotencyRegistry:
    def __init__(self):
        self._orders = {}

    def exists(self, client_order_id: str) -> bool:
        return client_order_id in self._orders

    def register(self, client_order_id: str, order_id: UUID) -> None:
        self._orders[client_order_id] = order_id

    def get(self, client_order_id: str):
        return self._orders.get(client_order_id)