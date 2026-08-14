"""Order request lifecycle and state machine.

The lifecycle is the formal state contract of an order request: every
transition is validated against the fixed transition table, history is
append-only (:class:`OrderRequestStateTransition` records are immutable and
never rewritten), and terminal states lock the request forever.

The lifecycle only moves states - it never re-runs risk / authorization and
never skips intermediate states.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Optional, Sequence

from services.order.request.state import OrderRequestState


class InvalidStateTransition(ValueError):
    """Raised when a transition violates the order request state machine.

    Inherits from :class:`ValueError` to keep the generic caller contract.
    """


@dataclass(frozen=True)
class OrderRequestStateTransition:
    """Immutable record of one state transition (append-only history entry)."""

    request_id: str
    from_state: OrderRequestState
    to_state: OrderRequestState
    reason: Optional[str]
    correlation_id: str
    timestamp: float


class OrderRequestLifecycle:
    """Fixed state machine for order requests (Commit 32 Part 1.3).

    A same-state transition is an idempotent no-op, never an error; skipping
    intermediate states (e.g. ``CREATED -> ACCEPTED``) is always rejected and
    any transition out of a terminal state raises
    :class:`InvalidStateTransition`.
    """

    TRANSITIONS: Dict[OrderRequestState, FrozenSet[OrderRequestState]] = {
        OrderRequestState.CREATED: frozenset(
            {
                OrderRequestState.VALIDATED,
                OrderRequestState.CANCELLED,
                OrderRequestState.EXPIRED,
            }
        ),
        OrderRequestState.VALIDATED: frozenset(
            {
                OrderRequestState.NORMALIZED,
                OrderRequestState.CANCELLED,
                OrderRequestState.EXPIRED,
            }
        ),
        OrderRequestState.NORMALIZED: frozenset(
            {
                OrderRequestState.SUBMITTED,
                OrderRequestState.CANCELLED,
                OrderRequestState.EXPIRED,
            }
        ),
        OrderRequestState.SUBMITTED: frozenset(
            {
                OrderRequestState.ACCEPTED,
                OrderRequestState.REJECTED,
                OrderRequestState.CANCELLED,
                OrderRequestState.EXPIRED,
            }
        ),
        OrderRequestState.ACCEPTED: frozenset({OrderRequestState.HANDOFF}),
        OrderRequestState.REJECTED: frozenset(),
        OrderRequestState.CANCELLED: frozenset(),
        OrderRequestState.EXPIRED: frozenset(),
        OrderRequestState.HANDOFF: frozenset(),
    }

    TERMINAL_STATES: FrozenSet[OrderRequestState] = frozenset(
        {
            OrderRequestState.REJECTED,
            OrderRequestState.CANCELLED,
            OrderRequestState.EXPIRED,
            OrderRequestState.HANDOFF,
        }
    )

    def can_transition(
        self,
        current_state: OrderRequestState,
        target_state: OrderRequestState,
    ) -> bool:
        """Whether ``current_state -> target_state`` is a legal transition."""
        return target_state in self.TRANSITIONS.get(current_state, frozenset())

    def transition(
        self,
        request_id: str,
        current_state: OrderRequestState,
        target_state: OrderRequestState,
        *,
        correlation_id: str,
        timestamp: float,
        reason: Optional[str] = None,
    ) -> OrderRequestStateTransition:
        """Apply one transition and return its append-only record.

        Same-state transitions are idempotent no-ops; skipping intermediate
        states or moving out of a terminal state raises
        :class:`InvalidStateTransition`.
        """
        if current_state == target_state:
            if current_state in self.TERMINAL_STATES:
                raise InvalidStateTransition(
                    f"{request_id}: terminal state "
                    f"{current_state.value} cannot transition to "
                    f"{target_state.value}"
                )
            return OrderRequestStateTransition(
                request_id=request_id,
                from_state=current_state,
                to_state=target_state,
                reason=reason,
                correlation_id=correlation_id,
                timestamp=timestamp,
            )

        if not self.can_transition(current_state, target_state):
            raise InvalidStateTransition(
                f"{request_id}: {current_state.value} -> "
                f"{target_state.value} is not a legal transition"
            )

        return OrderRequestStateTransition(
            request_id=request_id,
            from_state=current_state,
            to_state=target_state,
            reason=reason,
            correlation_id=correlation_id,
            timestamp=timestamp,
        )

    def is_valid_path(self, states: Sequence[OrderRequestState]) -> bool:
        """Whether the full state sequence is a legal path.

        Equal adjacent states (idempotent no-ops) are accepted.
        """
        for current, following in zip(states, states[1:]):
            if current != following and not self.can_transition(current, following):
                return False
        return True
