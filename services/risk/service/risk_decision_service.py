"""
Risk decision orchestration service (Commit 41 Part 1.1 / 1.2 / 1.5).

The service owns the orchestration of the risk decision pipeline:

    RiskDecisionContext
        -> RiskPolicyEvaluator
        -> RiskDecision
        -> RiskDecisionRecord (persisted)
        -> RiskDecisionTrace (built)
        -> RiskDecisionAudit (recorded, idempotent)
        -> RiskDecisionEvent (APPROVED / REJECTED)

It does NOT mutate positions, cash, orders or execution state; it only
reads a snapshot, evaluates policies, persists the immutable audit record,
records the decision trace (Commit 41 Part 1.5) and publishes the resulting
decision event through the ``RiskEventPublisher`` port.

Boundaries (Commit 41 Part 1.5):

- The decision itself never performs the audit: ``evaluate`` builds the
  trace from the *already-produced* decision and delegates recording to
  ``RiskDecisionAudit``.
- The audit never modifies the decision: ``RiskDecisionAudit.record`` is a
  pure idempotent store keyed by ``decision_id``.
- The audit is optional for backwards compatibility: when no ``audit`` is
  injected the service behaves exactly as in Part 1.1/1.2.

Persistence happens BEFORE event publication: a risk decision is a highly
audit-sensitive result, and the system must never be left in a
"event published, record missing" state.  Atomicity between the two is
deferred to a future transactional outbox.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable
from uuid import uuid4

from ..audit.risk_decision_audit import RiskDecisionAudit
from ..context.decision_context import RiskDecisionContext
from ..decision.risk_decision import RiskDecision
from ..evaluator.policy_evaluator import RiskPolicyEvaluator
from ..ports.decision_repository import RiskDecisionRepository
from ..ports.event_publisher import RiskEventPublisher

if TYPE_CHECKING:
    from ..application.risk_decision_trace_builder import (
        RiskDecisionTraceBuilder,
    )

DecisionIdFactory = Callable[[], str]


class RiskDecisionService:
    """Orchestrates snapshot -> context -> policies -> decision -> record -> event.

    The service is idempotent per ``(request_id, snapshot)``: re-evaluating
    the same request against the same risk snapshot returns the previously
    formed decision and does NOT persist or publish anything twice.  A
    ``request_id`` may only ever produce one valid decision.
    """

    def __init__(
        self,
        evaluator: RiskPolicyEvaluator,
        event_publisher: RiskEventPublisher,
        repository: RiskDecisionRepository,
        *,
        decision_id_factory: DecisionIdFactory | None = None,
        now_provider: Callable[[], datetime] | None = None,
        audit: RiskDecisionAudit | None = None,
        trace_builder: RiskDecisionTraceBuilder | None = None,
    ) -> None:
        self._evaluator = evaluator
        self._event_publisher = event_publisher
        self._repository = repository
        self._decision_id_factory = decision_id_factory or (
            lambda: uuid4().hex
        )
        self._now_provider = now_provider or (
            lambda: datetime.now(timezone.utc)
        )
        self._audit = audit
        if trace_builder is not None:
            self._trace_builder = trace_builder
        else:
            # Late import keeps the application/domain packages importable
            # on their own and avoids a module-level import cycle.
            from ..application.risk_decision_trace_builder import (
                RiskDecisionTraceBuilder,
            )

            self._trace_builder = RiskDecisionTraceBuilder()
        self._decisions: dict[
            tuple[str, RiskDecisionContext],
            RiskDecision,
        ] = {}

    def evaluate(
        self,
        context: RiskDecisionContext,
        *,
        request_id: str | None = None,
    ) -> RiskDecision:
        """Evaluate ``context``, persist the record and publish the event.

        When ``request_id`` is not supplied it defaults to the signal id of
        ``context``, so every decision carries a stable request identity.

        Raises:
            ValueError: when ``request_id`` already produced a decision
                (idempotency violation) or a record with a different
                ``decision_id`` is persisted.
            Exception: propagated from the evaluator, the repository or the
                event publisher.  A publisher failure is never masked: the
                service does not cache nor return a decision whose event was
                not published.
        """
        request_id = request_id or context.signal_id

        key = (request_id, context)
        cached = self._decisions.get(key)
        if cached is not None:
            return cached

        existing = self._repository.get_by_request_id(request_id)
        if existing is not None:
            raise ValueError("risk decision request already exists")

        decision = self._evaluator.evaluate(context)
        decision_id = self._decision_id_factory()
        created_at = self._now_provider()

        record = decision.to_record(
            context,
            decision_id=decision_id,
            request_id=request_id,
            created_at=created_at,
        )
        self._repository.save(record)

        # Commit 41 Part 1.5: build the immutable decision trace from the
        # decision that was actually produced and record it in the audit.
        # The audit is idempotent per ``decision_id`` and never recomputes
        # Risk, so the audited decision can never diverge from the decision
        # that was persisted and published.
        if self._audit is not None:
            trace = self._trace_builder.build(
                decision_id=decision_id,
                request_id=request_id,
                context=context,
                decision=decision,
                created_at=created_at,
            )
            self._audit.record(trace)

        event = decision.to_event(
            context,
            decision_id=decision_id,
            request_id=request_id,
            timestamp=created_at,
        )
        self._event_publisher.publish(event)

        # Cache only after persistence and publication have succeeded.
        self._decisions[key] = decision
        return decision
