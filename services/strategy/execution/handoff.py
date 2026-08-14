"""Risk handoff - the crossing from the strategy domain into the risk domain.

The strategy domain ends at :class:`RiskHandoff.submit`.  From here on the
risk engine owns the intent: it may approve it (producing an order request),
reject it or modify it.  A strategy can never influence what happens after
the handoff.

Submitting an intent to risk is a guarded crossing::

    CanSubmitToRisk = SessionActive AND ReadinessReady AND IntentValidated
                      AND NotExpired AND NotCancelled

Every clause fails safe - an UNKNOWN session state, an expired readiness
verdict, a stale intent or a non-validated state blocks the handoff.

The handoff is idempotent by ``intent_id``: an event bus retry that resubmits
an already accepted intent receives the SAME risk decision id, so a duplicate
submission can never create a second risk decision (and therefore a doubled
position).  Each accepted handoff emits ``INTENT_RISK_HANDOFF_*`` events for
audit and correlation.
"""

from __future__ import annotations

import itertools
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional

from services.strategy.execution.context import ExecutionContext
from services.strategy.execution.intent import ExecutionIntent, ExecutionIntentState
from services.strategy.execution.lifecycle import IntentLifecycle
from services.strategy.execution.snapshot import IntentSnapshot, snapshot_intent
from services.strategy.readiness.execution_gate import ExecutionReadinessGate

#: Risk handoff event names (spec 30-31).  A strategy that hands an intent to
#: risk emits ``submitted`` (attempted) and then exactly one of ``accepted`` /
#: ``rejected`` / ``duplicate``.
HANDOFF_EVENTS: dict[str, str] = {
    "submitted": "INTENT_RISK_HANDOFF_SUBMITTED",
    "accepted": "INTENT_RISK_HANDOFF_ACCEPTED",
    "rejected": "INTENT_RISK_HANDOFF_REJECTED",
    "duplicate": "INTENT_RISK_HANDOFF_DUPLICATE",
}

#: Reasons that block a handoff, ordered as the gate formula reads.
SESSION_NOT_ACTIVE = "session_not_active"
READINESS_BLOCKED = "readiness_blocked"
INTENT_NOT_VALIDATED = "intent_not_validated"
INTENT_EXPIRED = "intent_expired"
INTENT_CANCELLED = "intent_cancelled"


@dataclass(frozen=True)
class RiskHandoffRequest:
    """The frozen artifact handed to the risk engine.

    Carries an immutable :class:`IntentSnapshot` (so risk decides on exactly
    what the strategy expressed) plus the exact submission time.
    """

    snapshot: IntentSnapshot
    submitted_at: float


@dataclass(frozen=True)
class RiskHandoffResult:
    """Outcome of one risk handoff attempt.

    ``accepted=True`` with a ``decision_id`` means risk took ownership;
    ``reason="duplicate"`` with an already-known decision id means the same
    intent was resubmitted (idempotent replay).  ``accepted=False`` lists the
    exact gate that refused the crossing in ``reason``.
    """

    accepted: bool
    intent_id: str

    decision_id: Optional[str] = None
    state: str = "REJECTED"
    reason: Optional[str] = None


_decision_counter = itertools.count(1)


def new_decision_id(timestamp: Optional[float] = None) -> str:
    """Generate a monotonically increasing risk decision id.

    Example: ``RISK-20260813-000001``.  One decision id is created per
    accepted handoff and is returned unchanged for idempotent replays.
    """
    reference = time.time() if timestamp is None else timestamp
    date_part = datetime.fromtimestamp(reference).strftime("%Y%m%d")
    sequence = next(_decision_counter)
    return f"RISK-{date_part}-{sequence:06d}"


class RiskHandoff:
    """Guarded, idempotent handoff of validated intents to the risk domain.

    ``submit`` re-verifies the frozen :class:`ExecutionContext` snapshot with
    the second-gate :class:`ExecutionReadinessGate` - it never trusts a
    cached verdict.  An optional :class:`IntentLifecycle` is advanced to
    SUBMITTED on acceptance.
    """

    def __init__(
        self,
        readiness_gate: ExecutionReadinessGate,
        *,
        emit: Optional[Callable[[str, dict[str, Any]], None]] = None,
        clock: Optional[float] = None,
    ) -> None:
        self.readiness_gate = readiness_gate
        self._emit = emit
        #: Virtual clock: handoff timestamps default to this reference time
        #: unless a ``now`` is passed explicitly (deterministic tests).
        self._clock = clock if clock is not None else time.time()
        #: intent_id -> decision_id.  This is the idempotency ledger: a
        #: resubmitted intent resolves to the same decision id.
        self._decisions: dict[str, str] = {}
        self.last_request: Optional[RiskHandoffRequest] = None

    @property
    def decisions(self) -> dict[str, str]:
        """Immutable view of the intent_id -> decision_id ledger."""
        return dict(self._decisions)

    def submit(
        self,
        intent: ExecutionIntent,
        context: ExecutionContext,
        *,
        lifecycle: Optional[IntentLifecycle] = None,
        now: Optional[float] = None,
    ) -> RiskHandoffResult:
        """Submit a validated intent to the risk engine (idempotent).

        Returns a :class:`RiskHandoffResult`; raises ``ValueError`` only when
        the intent itself is malformed (e.g. missing id).
        """
        if not intent.intent_id:
            raise ValueError("intent_id is required")
        reference = self._clock if now is None else now

        snapshot = snapshot_intent(intent, captured_at=reference)
        self.last_request = RiskHandoffRequest(
            snapshot=snapshot,
            submitted_at=reference,
        )

        self._emit_event(
            HANDOFF_EVENTS["submitted"],
            intent,
            context,
            reference,
        )

        # Idempotency first: a retried handoff (event bus replay) for an
        # already accepted intent must never create a second risk decision.
        existing = self._decisions.get(intent.intent_id)
        if existing is not None:
            self._emit_event(
                HANDOFF_EVENTS["duplicate"],
                intent,
                context,
                reference,
                decision_id=existing,
                reason="duplicate",
            )
            return RiskHandoffResult(
                accepted=True,
                intent_id=intent.intent_id,
                decision_id=existing,
                state=ExecutionIntentState.SUBMITTED.value,
                reason="duplicate",
            )

        reason = self._gate_reason(intent, context, reference)
        if reason is not None:
            self._emit_event(
                HANDOFF_EVENTS["rejected"],
                intent,
                context,
                reference,
                reason=reason,
            )
            return RiskHandoffResult(
                accepted=False,
                intent_id=intent.intent_id,
                decision_id=None,
                state=ExecutionIntentState.REJECTED.value,
                reason=reason,
            )

        decision_id = new_decision_id(reference)
        self._decisions[intent.intent_id] = decision_id
        if lifecycle is not None:
            lifecycle.transition(ExecutionIntentState.SUBMITTED)

        self._emit_event(
            HANDOFF_EVENTS["accepted"],
            intent,
            context,
            reference,
            decision_id=decision_id,
        )
        return RiskHandoffResult(
            accepted=True,
            intent_id=intent.intent_id,
            decision_id=decision_id,
            state=ExecutionIntentState.SUBMITTED.value,
            reason=None,
        )

    # --- gates ------------------------------------------------------------

    def _gate_reason(
        self,
        intent: ExecutionIntent,
        context: ExecutionContext,
        now: float,
    ) -> Optional[str]:
        """Return the blocking reason or None when the handoff may proceed.

        ``CanSubmitToRisk = SessionActive AND ReadinessReady AND
        IntentValidated AND NotExpired AND NotCancelled`` - every clause
        fails safe.
        """
        if context.session_state != "ACTIVE":
            return SESSION_NOT_ACTIVE
        if not self.readiness_gate.evaluate(context).ready:
            return READINESS_BLOCKED
        if intent.state == ExecutionIntentState.CANCELLED.value:
            return INTENT_CANCELLED
        if intent.state != ExecutionIntentState.VALIDATED.value:
            return INTENT_NOT_VALIDATED
        if intent.expires_at > 0 and now > intent.expires_at:
            return INTENT_EXPIRED
        return None

    # --- events -----------------------------------------------------------

    def _emit_event(
        self,
        event: str,
        intent: ExecutionIntent,
        context: ExecutionContext,
        now: float,
        *,
        decision_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        if self._emit is None:
            return
        payload = {
            "event": event,
            "strategy_id": intent.strategy_id,
            "intent_id": intent.intent_id,
            "session_id": intent.session_id,
            "signal_id": intent.signal_id,
            "correlation_id": intent.correlation_id,
            "symbol": intent.symbol,
            "side": intent.side,
            "target_quantity": intent.target_quantity,
            "execution_policy": intent.execution_policy,
            "urgency": intent.urgency,
            "intent_state": intent.state,
            "readiness_state": context.readiness_state,
            "session_state": context.session_state,
            "timestamp": now,
            "decision_id": decision_id,
            "reason": reason,
        }
        self._emit(event, payload)
