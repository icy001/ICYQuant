"""OrderService — application service orchestrating the OMS.

The OrderService is the single entry point for all OMS operations.
It coordinates:
    - OrderAcceptor (admission → OMS)
    - OrderLifecycleManager (lifecycle transitions)
    - OrderRepository (persistence)
    - ExecutionGateway (submission to execution layer)

Business code MUST use OrderService, never the repository directly.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.oms.domain.order import Order
from services.oms.domain.order_status import OrderStatus
from services.oms.domain.order_lifecycle import OrderLifecycleEvent
from services.oms.errors.order_errors import (
    OrderNotFoundError,
    OrderIdempotencyError,
    ParentQuantityExceededError,
)
from .order_acceptor import OrderAcceptor, AdmissionRequest
from .order_lifecycle_manager import OrderLifecycleManager


class OrderService:
    """Application service for OMS operations.

    Coordinates the acceptor, lifecycle manager, repository, and
    execution gateway. All business code goes through this service.
    """

    def __init__(self,
                 repository: Any,
                 event_store: Any = None,
                 execution_gateway: Any = None,
                 acceptor: Optional[OrderAcceptor] = None,
                 lifecycle_manager: Optional[OrderLifecycleManager] = None,
                 actor: str = "oms-service") -> None:
        self._repo = repository
        self._event_store = event_store
        self._gateway = execution_gateway
        self._acceptor = acceptor or OrderAcceptor()
        self._lifecycle = lifecycle_manager or OrderLifecycleManager()
        self.actor = actor

    # ── Admission ──────────────────────────────────

    def accept_order(self, request: AdmissionRequest) -> Order:
        """Accept an admission request and persist the new order."""
        # Idempotency check via repository
        if request.client_order_id:
            existing = self._repo.find_by_client_order_id(
                request.client_order_id,
            )
            if existing is not None:
                raise OrderIdempotencyError(
                    request.client_order_id,
                    existing_order_id=existing.order_id.order_id,
                )

        order = self._acceptor.accept(request)
        self._repo.save(order)
        self._store_events(order)
        return order

    # ── Lifecycle ──────────────────────────────────

    def create_order(self, order_id: str,
                     expected_version: Optional[int] = None) -> Order:
        """ACCEPTED → CREATED."""
        order = self._get_or_fail(order_id)
        self._lifecycle.create(order, expected_version=expected_version)
        self._repo.update(order)
        self._store_events(order)
        return order

    def route_order(self, order_id: str,
                    expected_version: Optional[int] = None) -> Order:
        """CREATED → ROUTING."""
        order = self._get_or_fail(order_id)
        self._lifecycle.route(order, expected_version=expected_version)
        self._repo.update(order)
        self._store_events(order)
        return order

    def submit_order(self, order_id: str,
                     expected_version: Optional[int] = None) -> Order:
        """ROUTING → WORKING via execution gateway.

        On gateway timeout or unknown status, marks order as unknown
        rather than FAILED. This preserves the invariant that unknown
        execution results must not be treated as failure.
        """
        order = self._get_or_fail(order_id)
        if order.status == OrderStatus.CREATED:
            self._lifecycle.route(order, expected_version=expected_version)

        # Submit to execution gateway
        if self._gateway is not None:
            try:
                result = self._gateway.submit(order)
                # If the gateway reports unknown/timeout, mark unknown
                if hasattr(result, 'status') and \
                        getattr(result.status, 'is_unknown', False):
                    self._lifecycle.mark_unknown(
                        order, expected_version=order.version,
                    )
                    self._repo.update(order)
                    return order
            except Exception:
                # Network error — mark unknown, do NOT fail
                self._lifecycle.mark_unknown(
                    order, expected_version=order.version,
                )
                self._repo.update(order)
                return order

        self._lifecycle.working(order, expected_version=order.version)
        self._repo.update(order)
        self._store_events(order)
        return order

    def apply_fill(self, order_id: str,
                   fill_quantity: float,
                   fill_price: float = 0.0,
                   execution_id: str = "",
                   expected_version: Optional[int] = None) -> Order:
        """Apply an execution fill."""
        order = self._get_or_fail(order_id)
        self._lifecycle.apply_execution(
            order, fill_quantity, fill_price, execution_id,
            expected_version=expected_version,
        )
        self._repo.update(order)
        self._store_events(order)
        return order

    def cancel_order(self, order_id: str,
                     reason: str = "",
                     expected_version: Optional[int] = None) -> Order:
        """Request cancellation of an order."""
        order = self._get_or_fail(order_id)
        self._lifecycle.request_cancel(
            order, reason=reason, expected_version=expected_version,
        )
        self._repo.update(order)
        self._store_events(order)
        return order

    def confirm_cancel(self, order_id: str,
                       reason: str = "",
                       expected_version: Optional[int] = None) -> Order:
        """Confirm cancellation."""
        order = self._get_or_fail(order_id)
        self._lifecycle.confirm_cancel(
            order, reason=reason, expected_version=expected_version,
        )
        self._repo.update(order)
        self._store_events(order)
        return order

    def reject_order(self, order_id: str,
                     reason: str = "",
                     expected_version: Optional[int] = None) -> Order:
        """Reject an order."""
        order = self._get_or_fail(order_id)
        self._lifecycle.reject(
            order, reason=reason, expected_version=expected_version,
        )
        self._repo.update(order)
        self._store_events(order)
        return order

    def expire_order(self, order_id: str,
                     expected_version: Optional[int] = None) -> Order:
        """Expire an order."""
        order = self._get_or_fail(order_id)
        self._lifecycle.expire(order, expected_version=expected_version)
        self._repo.update(order)
        self._store_events(order)
        return order

    # ── Parent / Child ─────────────────────────────

    def create_child_order(self, request: AdmissionRequest,
                           parent_order_id: str,
                           child_quantity: float) -> Order:
        """Create a child order linked to a parent.

        Validates that sum(child quantities) ≤ parent quantity.
        """
        parent = self._get_or_fail(parent_order_id)

        # Fetch existing children
        children = self._repo.find_by_parent_order_id(parent_order_id)
        total_children = sum(c.quantity.original for c in children)
        if total_children + child_quantity > parent.quantity.original:
            raise ParentQuantityExceededError(
                parent_order_id,
                parent_qty=parent.quantity.original,
                child_total=total_children + child_quantity,
            )

        # Set parent/root links
        request.parent_order_id = parent_order_id
        request.root_order_id = parent.order_id.root_order_id or parent_order_id
        request.quantity = child_quantity

        child = self.accept_order(request)
        return child

    # ── Queries ────────────────────────────────────

    def get_order(self, order_id: str) -> Order:
        return self._get_or_fail(order_id)

    def get_order_by_client_id(self, client_order_id: str) -> Optional[Order]:
        return self._repo.find_by_client_order_id(client_order_id)

    def get_active_orders(self) -> List[Order]:
        return [o for o in self._repo.get_all() if o.is_active]

    def get_child_orders(self, parent_order_id: str) -> List[Order]:
        return self._repo.find_by_parent_order_id(parent_order_id)

    def get_lifecycle_events(self, order_id: str) -> List[OrderLifecycleEvent]:
        order = self._get_or_fail(order_id)
        return list(order.lifecycle.events)

    # ── Internal ───────────────────────────────────

    def _get_or_fail(self, order_id: str) -> Order:
        order = self._repo.get(order_id)
        if order is None:
            raise OrderNotFoundError(order_id)
        return order

    def _store_events(self, order: Order) -> None:
        if self._event_store is None:
            return
        for event in order.lifecycle.events:
            self._event_store.append(event)
