"""Order request service boundary (Commit 32 Part 1.5).

Compiles the order request engine into a single application boundary:

.. code-block:: text

    AuthorizedExecutionContext
            |
            v
    OrderRequestService
        |  create / validate / normalize / submit / accept / reject / handoff
        +-- OrderRequestFactory
        +-- OrderRequestValidator
        +-- OrderRequestNormalizer
        +-- OrderRequestLifecycle
        +-- OrderRequestRepository
        +-- EventFactory -> Outbox -> Publisher -> EventBus

Business code must not reach past this service: it is the only entry point to
the order request aggregate, so validation, normalization, lifecycle,
persistence and idempotency stay under one roof.

Reliability contract
====================

- **Idempotent create** -- ``create()`` is keyed by ``idempotency_key``: a
  second call with the same authorized context returns the already-persisted
  request (same ``order_request_id``) instead of minting a new one.
- **Idempotent transitions** -- repeating ``submit``/``accept``/... on the
  target state is a no-op and emits no duplicate event.
- **Persist-then-transition** -- the repository is updated first; only on
  success does the in-memory state change and a domain event get emitted.
  If the repository is unavailable the service fails closed
  (:class:`OrderRequestPersistenceError`) and nothing is mis-marked.
- **State == persisted state** -- ``repository`` state always equals the
  in-memory lifecycle state, so reconciliation never sees a conflict.
- **Events are append-only** -- state and event are one atomic fact: the
  aggregate is persisted and the outbox record written before the event bus
  propagates anything (transactional outbox, at-least-once).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Union

from services.order.request.errors import OrderRequestValidationError
from services.order.request.event_factory import OrderRequestEventFactory
from services.order.request.event_publisher import (
    EventBusUnavailable,
    OrderRequestEventPublisher,
    OrderRequestOutbox,
)
from services.order.request.event_types import OrderRequestEventType
from services.order.request.events import OrderRequestEvent
from services.order.request.factory import (
    OrderRequestFactory,
    authorization_idempotency_key,
)
from services.order.request.lifecycle import (
    OrderRequestLifecycle,
    OrderRequestStateTransition,
)
from services.order.request.model import OrderRequest
from services.order.request.normalization import (
    NormalizedOrderRequest,
    OrderRequestNormalizer,
)
from services.order.request.repository import (
    InMemoryOrderRequestRepository,
    OrderRequestRepository,
    OrderRequestSnapshot,
)
from services.order.request.state import OrderRequestState
from services.order.request.validation import OrderRequestValidator

#: Anything that identifies an aggregate: an id, a request or a snapshot.
RequestHandle = Union[str, OrderRequest, OrderRequestSnapshot]


class OrderRequestService:
    """Application boundary for the order request aggregate.

    The service is the only way to create and mutate an order request.  It
    owns the lifecycle state machine, guarantees persistence and emits domain
    events.  It never re-runs risk / authorization and never skips validation.
    """

    def __init__(
        self,
        *,
        request_factory: Optional[OrderRequestFactory] = None,
        validator: Optional[OrderRequestValidator] = None,
        normalizer: Optional[OrderRequestNormalizer] = None,
        lifecycle: Optional[OrderRequestLifecycle] = None,
        event_factory: Optional[OrderRequestEventFactory] = None,
        publisher: Optional[OrderRequestEventPublisher] = None,
        outbox: Optional[OrderRequestOutbox] = None,
        repository: Optional[OrderRequestRepository] = None,
    ) -> None:
        self.request_factory = (
            request_factory if request_factory is not None else OrderRequestFactory()
        )
        self.validator = validator if validator is not None else OrderRequestValidator()
        self.normalizer = (
            normalizer if normalizer is not None else OrderRequestNormalizer()
        )
        self.lifecycle = lifecycle if lifecycle is not None else OrderRequestLifecycle()
        self.event_factory = (
            event_factory if event_factory is not None else OrderRequestEventFactory()
        )
        self.publisher = (
            publisher if publisher is not None else OrderRequestEventPublisher()
        )
        self.outbox = outbox if outbox is not None else OrderRequestOutbox()
        self.repository = (
            repository if repository is not None else InMemoryOrderRequestRepository()
        )

        #: In-memory aggregate cache; the repository is the source of truth.
        self._requests: Dict[str, OrderRequestSnapshot] = {}
        self._sequences: Dict[str, int] = {}
        self._last_event_ids: Dict[str, Optional[str]] = {}
        self._events: Dict[str, List[OrderRequestEvent]] = {}
        self._events_by_id: Dict[str, OrderRequestEvent] = {}
        self._history: Dict[str, List[OrderRequestStateTransition]] = {}

    # ------------------------------------------------------------------ #
    # Lifecycle operations
    # ------------------------------------------------------------------ #

    def create(
        self,
        context,
        *,
        order_type: str,
        time_in_force: str,
        limit_price: Optional[float],
        created_at: float,
    ) -> OrderRequestSnapshot:
        """Create an order request from an authorized execution context.

        Idempotent by ``idempotency_key``: creating the same authorization
        twice returns the already-persisted request (same ``order_request_id``)
        and emits no second ``ORDER_REQUEST_CREATED`` event.

        ``create()`` does *not* mean the order was submitted; it only means the
        request exists.  The request starts in ``CREATED`` and is persisted
        before the aggregate becomes visible, so a repository failure fails
        closed.
        """
        idempotency_key = authorization_idempotency_key(
            context.strategy_id,
            context.session_id,
            context.intent_id,
        )
        existing = self.repository.find_by_idempotency_key(idempotency_key)
        if existing is not None:
            self._register(existing)
            return existing

        request = self.request_factory.create(
            context,
            order_type=order_type,
            time_in_force=time_in_force,
            limit_price=limit_price,
            created_at=created_at,
        )
        # Fail-closed: persist before the aggregate is visible or any event is
        # emitted.  A repository failure leaves nothing registered.
        self.repository.save(request, state=OrderRequestState.CREATED)
        snapshot = OrderRequestSnapshot.from_request(
            request,
            state=OrderRequestState.CREATED,
        )
        self._register(snapshot)
        self._emit(
            snapshot,
            OrderRequestEventType.ORDER_REQUEST_CREATED,
            timestamp=created_at,
        )
        return snapshot

    def validate(
        self,
        request: RequestHandle,
        *,
        timestamp: Optional[float] = None,
        approved_quantity: Optional[float] = None,
    ) -> None:
        """Run structural validation and move ``CREATED -> VALIDATED``.

        Accepts a request id, an :class:`OrderRequest` or an
        :class:`OrderRequestSnapshot`.

        Raises:
            OrderRequestValidationError: when the request is illegal.
            InvalidStateTransition: when the state does not allow the move.
        """
        resolved = self._resolve(request)
        result = self.validator.validate(resolved, approved_quantity=approved_quantity)
        if not result.valid:
            raise OrderRequestValidationError(result.errors)
        self._advance(
            resolved.order_request_id,
            OrderRequestState.VALIDATED,
            OrderRequestEventType.ORDER_REQUEST_VALIDATED,
            timestamp=timestamp if timestamp is not None else resolved.created_at,
        )

    def normalize(
        self,
        request: RequestHandle,
        *,
        timestamp: Optional[float] = None,
        approved_quantity: Optional[float] = None,
    ) -> NormalizedOrderRequest:
        """Validate + canonicalize and move ``VALIDATED -> NORMALIZED``.

        Returns the canonical :class:`NormalizedOrderRequest`.  Normalization
        never changes trading semantics: ``BUY 100 NVDA`` cannot become
        ``SELL 1000 AMD``.
        """
        resolved = self._resolve(request)
        normalized = self.normalizer.normalize(
            resolved,
            approved_quantity=approved_quantity,
        )
        self._advance(
            resolved.order_request_id,
            OrderRequestState.NORMALIZED,
            OrderRequestEventType.ORDER_REQUEST_NORMALIZED,
            timestamp=timestamp if timestamp is not None else resolved.created_at,
        )
        return normalized

    def submit(self, request_id: RequestHandle, *, timestamp: float) -> OrderRequestSnapshot:
        """Move ``NORMALIZED -> SUBMITTED`` (the submit boundary).

        The request is ready to hand to the downstream order engine, but no OMS
        order exists yet.  Idempotent: re-submitting a ``SUBMITTED`` request is
        a no-op.
        """
        resolved_id = self._resolve_id(request_id)
        self._advance(
            resolved_id,
            OrderRequestState.SUBMITTED,
            OrderRequestEventType.ORDER_REQUEST_SUBMITTED,
            timestamp=timestamp,
        )
        return self._get(resolved_id)

    def accept(self, request_id: RequestHandle, *, timestamp: float) -> OrderRequestSnapshot:
        """Move ``SUBMITTED -> ACCEPTED`` once the venue has accepted.

        Acceptance means the downstream engine accepted the request — not that
        the order filled.
        """
        resolved_id = self._resolve_id(request_id)
        self._advance(
            resolved_id,
            OrderRequestState.ACCEPTED,
            OrderRequestEventType.ORDER_REQUEST_ACCEPTED,
            timestamp=timestamp,
        )
        return self._get(resolved_id)

    def handoff(self, request_id: RequestHandle, *, timestamp: float) -> OrderRequestSnapshot:
        """Move ``ACCEPTED -> HANDOFF`` (final normal lifecycle step).

        Control transfers to the order engine / OMS; the request lifecycle is
        complete.
        """
        resolved_id = self._resolve_id(request_id)
        self._advance(
            resolved_id,
            OrderRequestState.HANDOFF,
            OrderRequestEventType.ORDER_REQUEST_HANDOFF,
            timestamp=timestamp,
        )
        return self._get(resolved_id)

    def reject(
        self,
        request_id: RequestHandle,
        *,
        timestamp: float,
        reason: str,
    ) -> OrderRequestSnapshot:
        """Reject the request; the ``REJECTED`` payload must carry ``reason``."""
        if not reason:
            raise ValueError("reject reason is required")
        resolved_id = self._resolve_id(request_id)
        self._advance(
            resolved_id,
            OrderRequestState.REJECTED,
            OrderRequestEventType.ORDER_REQUEST_REJECTED,
            timestamp=timestamp,
            reason=reason,
        )
        return self._get(resolved_id)

    def cancel(
        self,
        request_id: RequestHandle,
        *,
        timestamp: float,
        reason: Optional[str] = None,
    ) -> OrderRequestSnapshot:
        """Cancel the request (cancellation after handoff belongs to the OMS)."""
        resolved_id = self._resolve_id(request_id)
        self._advance(
            resolved_id,
            OrderRequestState.CANCELLED,
            OrderRequestEventType.ORDER_REQUEST_CANCELLED,
            timestamp=timestamp,
            reason=reason,
        )
        return self._get(resolved_id)

    def expire(
        self,
        request_id: RequestHandle,
        *,
        timestamp: float,
        reason: Optional[str] = None,
    ) -> OrderRequestSnapshot:
        """Expire the request (e.g. time-in-force window elapsed)."""
        resolved_id = self._resolve_id(request_id)
        self._advance(
            resolved_id,
            OrderRequestState.EXPIRED,
            OrderRequestEventType.ORDER_REQUEST_EXPIRED,
            timestamp=timestamp,
            reason=reason,
        )
        return self._get(resolved_id)

    # ------------------------------------------------------------------ #
    # Read models
    # ------------------------------------------------------------------ #

    def get(self, request_id: str) -> OrderRequestSnapshot:
        """Return the persisted snapshot (request data + current state)."""
        return self._get(request_id)

    def get_state(self, request_id: str) -> OrderRequestState:
        """Return the current aggregate state."""
        return self._get(request_id).state

    def get_events(self, request_id: str) -> Tuple[OrderRequestEvent, ...]:
        """Return the append-only event log for the aggregate (sequence order)."""
        self._get(request_id)
        return tuple(self._events.get(request_id, ()))

    def get_history(self, request_id: str) -> Tuple[OrderRequestStateTransition, ...]:
        """Return the append-only state transition history."""
        self._get(request_id)
        return tuple(self._history.get(request_id, ()))

    # ------------------------------------------------------------------ #
    # Outbox relay
    # ------------------------------------------------------------------ #

    def publish_pending(self) -> int:
        """Retry publishing every PENDING outbox record.

        Returns the number of records successfully published.  Records whose
        bus is still unavailable remain ``PENDING`` and can be retried again.
        """
        published = 0
        for record in self.outbox.get_pending():
            event = self._events_by_id.get(record.event_id)
            if event is None:
                continue
            try:
                self.publisher.publish(event)
            except EventBusUnavailable:
                continue
            self.outbox.mark_published(event.event_id, published_at=event.timestamp)
            published += 1
        return published

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _get(self, request_id: str) -> OrderRequestSnapshot:
        request = self._requests.get(request_id)
        if request is not None:
            return request
        # Cache miss: hydrate from the repository (the source of truth).
        snapshot = self.repository.get(request_id)
        if snapshot is None:
            raise KeyError(f"unknown order request: {request_id}")
        self._register(snapshot)
        return snapshot

    def _register(self, snapshot: OrderRequestSnapshot) -> None:
        request_id = snapshot.order_request_id
        self._requests[request_id] = snapshot
        # Only initialize bookkeeping that is not already present, so hydration
        # never clobbers an existing append-only log.
        self._sequences.setdefault(request_id, 0)
        self._last_event_ids.setdefault(request_id, None)
        self._events.setdefault(request_id, [])
        self._history.setdefault(request_id, [])

    def _advance(
        self,
        request_id: str,
        target_state: OrderRequestState,
        event_type: OrderRequestEventType,
        *,
        timestamp: float,
        reason: Optional[str] = None,
    ) -> OrderRequestStateTransition:
        request = self._get(request_id)
        current_state = request.state
        transition = self.lifecycle.transition(
            request_id=request_id,
            current_state=current_state,
            target_state=target_state,
            correlation_id=request.correlation_id,
            timestamp=timestamp,
            reason=reason,
        )
        if target_state == current_state:
            # Idempotent no-op: nothing persists, no duplicate event.
            return transition
        # Fail-closed, persist-then-transition: the repository must accept the
        # new state before the in-memory aggregate changes or an event is
        # emitted.  A repository failure leaves state and event log untouched.
        self.repository.update_state(request_id, target_state)
        updated = request.with_state(target_state)
        self._requests[request_id] = updated
        self._history.setdefault(request_id, []).append(transition)
        self._emit(updated, event_type, timestamp=timestamp, reason=reason)
        return transition

    def _emit(
        self,
        request: OrderRequestSnapshot,
        event_type: OrderRequestEventType,
        *,
        timestamp: float,
        reason: Optional[str] = None,
    ) -> OrderRequestEvent:
        request_id = request.order_request_id
        sequence = self._sequences[request_id] + 1
        event = self.event_factory.create(
            request,
            event_type,
            sequence=sequence,
            causation_id=self._last_event_ids[request_id],
            timestamp=timestamp,
            reason=reason,
        )
        self._sequences[request_id] = sequence
        self._last_event_ids[request_id] = event.event_id
        self._events.setdefault(request_id, []).append(event)
        self._events_by_id[event.event_id] = event
        self.outbox.append(event)
        self._dispatch(event)
        return event

    def _dispatch(self, event: OrderRequestEvent) -> None:
        try:
            self.publisher.publish(event)
        except EventBusUnavailable:
            # Bus is down: the outbox record stays PENDING and is retried by
            # publish_pending() after recovery.  The event itself is already
            # persisted (append-only) and never lost.
            return
        self.outbox.mark_published(event.event_id, published_at=event.timestamp)

    @staticmethod
    def _resolve_id(handle: RequestHandle) -> str:
        if isinstance(handle, str):
            return handle
        return handle.order_request_id

    def _resolve(self, handle: RequestHandle) -> OrderRequest:
        if isinstance(handle, str):
            return self._get(handle).to_request()
        if isinstance(handle, OrderRequestSnapshot):
            return handle.to_request()
        return handle


__all__ = [
    "OrderRequestService",
]
