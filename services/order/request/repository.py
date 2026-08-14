"""Order request repository boundary (Commit 32 Part 1.5).

The repository persists order request *snapshots*: the immutable request data
plus the current lifecycle state.  A snapshot carries the full authorization
lineage so a request can be recovered and audited independently:

.. code-block:: text

    Order Request
        -> Authorization
        -> Risk Decision
        -> Intent
        -> Signal
        -> Strategy

This module defines the :class:`OrderRequestRepository` interface only; the
in-memory implementation (:class:`InMemoryOrderRequestRepository`) is meant for
tests and single-process deployments.  PostgreSQL / Redis / Event Store
adapters can be added without touching the order request domain.

The repository has no business logic: it only saves, reads and updates state.
It never validates, normalizes or makes trading decisions.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from typing import Dict, Optional

from services.order.request.exceptions import OrderRequestPersistenceError
from services.order.request.model import OrderRequest
from services.order.request.state import OrderRequestState


@dataclass(frozen=True)
class OrderRequestSnapshot:
    """Immutable point-in-time view of an order request and its state.

    This is what the repository stores and what ``OrderRequestService.create``
    returns, so the current state is always visible next to the request data.
    """

    order_request_id: str
    intent_id: str
    authorization_id: str
    certificate_id: str
    decision_id: str
    strategy_id: str
    session_id: str
    signal_id: str
    correlation_id: str
    symbol: str
    side: str
    quantity: float
    order_type: str
    time_in_force: str
    limit_price: Optional[float]
    idempotency_key: str
    created_at: float
    state: OrderRequestState

    @classmethod
    def from_request(
        cls,
        request: OrderRequest,
        *,
        state: OrderRequestState,
    ) -> "OrderRequestSnapshot":
        """Build a snapshot from an immutable request plus its current state."""
        return cls(
            order_request_id=request.order_request_id,
            intent_id=request.intent_id,
            authorization_id=request.authorization_id,
            certificate_id=request.certificate_id,
            decision_id=request.decision_id,
            strategy_id=request.strategy_id,
            session_id=request.session_id,
            signal_id=request.signal_id,
            correlation_id=request.correlation_id,
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            order_type=request.order_type,
            time_in_force=request.time_in_force,
            limit_price=request.limit_price,
            idempotency_key=request.idempotency_key,
            created_at=request.created_at,
            state=state,
        )

    def with_state(self, state: OrderRequestState) -> "OrderRequestSnapshot":
        """A new snapshot with ``state`` (the data itself never changes)."""
        return replace(self, state=state)

    def to_request(self) -> OrderRequest:
        """The pure request data (no state) as an :class:`OrderRequest`."""
        return OrderRequest(
            order_request_id=self.order_request_id,
            intent_id=self.intent_id,
            authorization_id=self.authorization_id,
            certificate_id=self.certificate_id,
            decision_id=self.decision_id,
            strategy_id=self.strategy_id,
            session_id=self.session_id,
            signal_id=self.signal_id,
            correlation_id=self.correlation_id,
            symbol=self.symbol,
            side=self.side,
            quantity=self.quantity,
            order_type=self.order_type,
            time_in_force=self.time_in_force,
            limit_price=self.limit_price,
            created_at=self.created_at,
            idempotency_key=self.idempotency_key,
        )

    def as_dict(self) -> Dict[str, object]:
        """Plain mapping used by persistence adapters (includes state)."""
        return {
            "order_request_id": self.order_request_id,
            "intent_id": self.intent_id,
            "authorization_id": self.authorization_id,
            "certificate_id": self.certificate_id,
            "decision_id": self.decision_id,
            "strategy_id": self.strategy_id,
            "session_id": self.session_id,
            "signal_id": self.signal_id,
            "correlation_id": self.correlation_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "order_type": self.order_type,
            "time_in_force": self.time_in_force,
            "limit_price": self.limit_price,
            "idempotency_key": self.idempotency_key,
            "created_at": self.created_at,
            "state": self.state,
        }


class OrderRequestRepository(ABC):
    """Persistence boundary for order request snapshots."""

    @abstractmethod
    def save(
        self,
        request: OrderRequest,
        *,
        state: OrderRequestState = OrderRequestState.CREATED,
    ) -> None:
        """Persist the request snapshot (create or full overwrite).

        Raises:
            OrderRequestPersistenceError: when the store is unavailable.
        """

    @abstractmethod
    def get(self, order_request_id: str) -> Optional[OrderRequestSnapshot]:
        """Return the snapshot for ``order_request_id`` or ``None``."""

    @abstractmethod
    def update_state(self, order_request_id: str, state: OrderRequestState) -> None:
        """Persist a new aggregate state.

        Raises:
            KeyError: when the aggregate is not stored.
            OrderRequestPersistenceError: when the store is unavailable.
        """

    @abstractmethod
    def find_by_idempotency_key(
        self, idempotency_key: str
    ) -> Optional[OrderRequestSnapshot]:
        """Return the snapshot with ``idempotency_key`` or ``None``."""


class InMemoryOrderRequestRepository(OrderRequestRepository):
    """In-memory repository for tests and single-process deployments."""

    def __init__(self) -> None:
        self._snapshots: Dict[str, OrderRequestSnapshot] = {}
        self._by_idempotency_key: Dict[str, str] = {}
        #: Set to ``True`` to simulate an unavailable store (fail-closed tests).
        self.fail_on_save: bool = False
        self.fail_on_update: bool = False

    def save(
        self,
        request: OrderRequest,
        *,
        state: OrderRequestState = OrderRequestState.CREATED,
    ) -> None:
        if self.fail_on_save:
            raise OrderRequestPersistenceError("order request store unavailable (save)")
        snapshot = OrderRequestSnapshot.from_request(request, state=state)
        self._snapshots[snapshot.order_request_id] = snapshot
        self._by_idempotency_key[snapshot.idempotency_key] = snapshot.order_request_id

    def get(self, order_request_id: str) -> Optional[OrderRequestSnapshot]:
        return self._snapshots.get(order_request_id)

    def update_state(self, order_request_id: str, state: OrderRequestState) -> None:
        snapshot = self._snapshots.get(order_request_id)
        if snapshot is None:
            raise KeyError(f"unknown order request: {order_request_id}")
        if self.fail_on_update:
            raise OrderRequestPersistenceError(
                "order request store unavailable (update_state)"
            )
        self._snapshots[order_request_id] = snapshot.with_state(state)

    def find_by_idempotency_key(
        self, idempotency_key: str
    ) -> Optional[OrderRequestSnapshot]:
        request_id = self._by_idempotency_key.get(idempotency_key)
        if request_id is None:
            return None
        return self._snapshots.get(request_id)

    def __len__(self) -> int:
        return len(self._snapshots)


__all__ = [
    "OrderRequestRepository",
    "OrderRequestSnapshot",
    "InMemoryOrderRequestRepository",
]
