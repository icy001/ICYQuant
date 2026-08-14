"""Execution intent boundary.

The boundary is the ONLY way an approved signal can become an execution
intent.  A strategy can never create an order, reach the OMS or touch a
broker from here - it can only express an intent::

    Approved Signal
        -> Execution Readiness (second gate)
        -> Context Snapshot
        -> Intent Validation
        -> Execution Intent
        -> Persist

If any step fails the intent is REJECTED and no order is ever produced.  The
boundary also protects against duplicate intents: the same signal replayed
twice (e.g. by an event bus retry) resolves to the same intent instead of
creating a second one.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from services.strategy.execution.context import ExecutionContext
from services.strategy.execution.intent import ExecutionIntent, StrategySignal
from services.strategy.execution.result import IntentResult
from services.strategy.execution.session import StrategyExecutionSession
from services.strategy.execution.validator import IntentValidationError, IntentValidator
from services.strategy.readiness.execution_gate import ExecutionReadinessGate


@runtime_checkable
class IntentStore(Protocol):
    """Persists execution intents and answers duplicate queries."""

    def save(self, intent: ExecutionIntent) -> None:  # pragma: no cover
        ...

    def get(self, intent_id: str) -> Optional[ExecutionIntent]:  # pragma: no cover
        ...

    def get_by_fingerprint(  # pragma: no cover
        self, fingerprint: str
    ) -> Optional[ExecutionIntent]:
        ...


class InMemoryIntentStore:
    """Simple in-memory intent store for tests / single-process use."""

    def __init__(self) -> None:
        self._intents: dict[str, ExecutionIntent] = {}
        self._by_fingerprint: dict[str, ExecutionIntent] = {}

    def save(self, intent: ExecutionIntent) -> None:
        self._intents[intent.intent_id] = intent
        self._by_fingerprint[intent.intent_fingerprint] = intent

    def get(self, intent_id: str) -> Optional[ExecutionIntent]:
        return self._intents.get(intent_id)

    def get_by_fingerprint(self, fingerprint: str) -> Optional[ExecutionIntent]:
        return self._by_fingerprint.get(fingerprint)

    def __len__(self) -> int:
        return len(self._intents)


class ExecutionIntentBoundary:
    """Gate between the strategy domain and the execution domain.

    Intent creation requires BOTH the session to be ACTIVE and the freshly
    re-verified execution readiness to be READY::

        ExecutionEligible = Session ACTIVE AND Readiness READY
    """

    def __init__(
        self,
        readiness_gate: ExecutionReadinessGate,
        validator: IntentValidator,
        intent_store: IntentStore,
        session: Optional[StrategyExecutionSession] = None,
    ) -> None:
        self.readiness_gate = readiness_gate
        self.validator = validator
        self.intent_store = intent_store
        self.session = session

    def create_intent(
        self,
        signal: StrategySignal,
        context: ExecutionContext,
        *,
        session: Optional[StrategyExecutionSession] = None,
        execution_policy: str = "MARKET",
        urgency: str = "NORMAL",
        correlation_id: Optional[str] = None,
        now: Optional[float] = None,
    ) -> IntentResult:
        active_session = session or self.session

        # Layer 2: the execution session must be ACTIVE.
        if active_session is not None and not active_session.can_create_intent():
            return self._rejected(signal, "session_not_active")

        # Layer 3: readiness must be re-verified right now - never trust a
        # cached verdict, the previous READY may have a TTL.
        readiness = self.readiness_gate.evaluate(context)
        if not readiness.ready:
            return self._rejected(
                signal,
                "readiness_%s" % readiness.state.lower(),
            )

        try:
            intent = self.validator.validate(
                signal,
                context,
                session_id=active_session.session_id if active_session else "",
                correlation_id=correlation_id,
                execution_policy=execution_policy,
                urgency=urgency,
                now=now,
            )
        except IntentValidationError as exc:
            return self._rejected(signal, str(exc))

        # Duplicate protection: the same signal replayed (e.g. by an event
        # bus retry) must never create a second intent.  The strategy layer
        # provides intent identity; the control plane provides idempotency.
        existing = self.intent_store.get_by_fingerprint(intent.intent_fingerprint)
        if existing is not None:
            return IntentResult(
                intent_id=existing.intent_id,
                strategy_id=existing.strategy_id,
                signal_id=existing.signal_id,
                accepted=True,
                state=existing.state,
                reason="duplicate",
            )

        self.intent_store.save(intent)
        if active_session is not None:
            active_session.register_intent()

        return IntentResult(
            intent_id=intent.intent_id,
            strategy_id=intent.strategy_id,
            signal_id=intent.signal_id,
            accepted=True,
            state=intent.state,
            reason=None,
        )

    def _rejected(self, signal: StrategySignal, reason: str) -> IntentResult:
        return IntentResult(
            intent_id="",
            strategy_id=signal.strategy_id,
            signal_id=signal.signal_id,
            accepted=False,
            state="REJECTED",
            reason=reason,
        )
