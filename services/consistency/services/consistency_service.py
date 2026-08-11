"""
ConsistencyService — central orchestrator for cross-domain consistency checks.

Maintains an in-memory registry of execution facts, position snapshots, and
ledger snapshots.  Provides methods to run checks at different scopes
(execution, order, instrument, account).

In production this service would be backed by the event store and projections.
For now it works with in-memory snapshots suitable for testing and the
domain model verification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from ..domain.consistency_check import (
    ConsistencyCheck,
    ExecutionFact,
    LedgerView,
    PositionView,
)
from ..domain.consistency_result import ConsistencyResult
from ..domain.consistency_status import ConsistencyDomainStatus
from ..events.consistency_failed import ConsistencyFailed
from ..events.consistency_restored import ConsistencyRestored
from ..commands.run_consistency_check import RunConsistencyCheck


@dataclass
class _State:
    """Internal mutable state for the ConsistencyService."""

    execution_facts: Dict[str, List[ExecutionFact]] = field(
        default_factory=dict  # key = account:instrument
    )
    position_views: Dict[str, PositionView] = field(
        default_factory=dict  # key = account:instrument
    )
    ledger_views: Dict[str, LedgerView] = field(
        default_factory=dict  # key = account:currency
    )
    check_history: List[ConsistencyCheck] = field(default_factory=list)
    event_log: List[Any] = field(default_factory=list)
    previous_status: Dict[str, ConsistencyDomainStatus] = field(
        default_factory=dict  # key = check_key → last known status
    )


class ConsistencyService:
    """Cross-domain consistency verification orchestrator.

    Usage::

        svc = ConsistencyService(grace_period_ms=5000)
        svc.record_execution(ExecutionFact(...))
        svc.record_position(PositionView(...))
        svc.record_ledger(LedgerView(...))
        result = svc.check_instrument("ACC-001", "NVDA")
    """

    def __init__(
        self,
        grace_period_ms: int = 5000,
        on_event: Optional[Callable[[Any], None]] = None,
    ) -> None:
        self.grace_period_ms = grace_period_ms
        self._on_event = on_event
        self._state = _State()

    # -----------------------------------------------------------------
    #  Snapshot recording
    # -----------------------------------------------------------------

    def record_execution(self, fact: ExecutionFact) -> None:
        """Record an execution fact as reference truth."""
        key = f"{fact.account_id}:{fact.instrument_id}"
        if key not in self._state.execution_facts:
            self._state.execution_facts[key] = []
        self._state.execution_facts[key].append(fact)

    def record_position(self, view: PositionView) -> None:
        """Record a position snapshot."""
        key = f"{view.account_id}:{view.instrument_id}"
        self._state.position_views[key] = view

    def record_ledger(self, view: LedgerView) -> None:
        """Record a ledger snapshot."""
        key = f"{view.account_id}:{view.currency}"
        self._state.ledger_views[key] = view

    # -----------------------------------------------------------------
    #  Scoped checks
    # -----------------------------------------------------------------

    def check_execution(
        self,
        execution_id: str,
        account_id: str,
        instrument_id: str,
    ) -> ConsistencyCheck:
        """Check consistency for a single execution."""
        facts = self._get_facts(account_id, instrument_id)
        filtered = [f for f in facts if f.execution_id == execution_id]
        if not filtered:
            return self._empty_check(account_id, instrument_id)

        pos_view = self._state.position_views.get(
            f"{account_id}:{instrument_id}"
        )
        ledger_view = self._state.ledger_views.get(f"{account_id}:USD")

        return self._run_check(
            account_id,
            instrument_id,
            "execution",
            filtered,
            pos_view,
            ledger_view,
        )

    def check_order(
        self,
        order_id: str,
        account_id: str,
        instrument_id: str,
    ) -> ConsistencyCheck:
        """Check consistency for all fills of an order."""
        facts = self._get_facts(account_id, instrument_id)
        filtered = [f for f in facts if f.order_id == order_id]
        return self._check_with_scope(
            account_id, instrument_id, "order", filtered
        )

    def check_instrument(
        self,
        account_id: str,
        instrument_id: str,
    ) -> ConsistencyCheck:
        """Check consistency for all executions of an instrument."""
        facts = self._get_facts(account_id, instrument_id)
        return self._check_with_scope(
            account_id, instrument_id, "instrument", facts
        )

    def check_account(self, account_id: str) -> List[ConsistencyCheck]:
        """Check consistency across all instruments for an account."""
        prefix = f"{account_id}:"
        instrument_keys = {
            k for k in self._state.execution_facts if k.startswith(prefix)
        }
        results: List[ConsistencyCheck] = []
        for key in instrument_keys:
            instrument_id = key.split(":", 1)[1]
            results.append(self.check_instrument(account_id, instrument_id))
        return results

    # -----------------------------------------------------------------
    #  Status queries
    # -----------------------------------------------------------------

    def get_check_history(self) -> List[ConsistencyCheck]:
        return list(self._state.check_history)

    def get_check(self, check_id: str) -> Optional[ConsistencyCheck]:
        for check in self._state.check_history:
            if check.check_id == check_id:
                return check
        return None

    def get_events(self) -> List[Any]:
        return list(self._state.event_log)

    @property
    def check_count(self) -> int:
        return len(self._state.check_history)

    @property
    def event_count(self) -> int:
        return len(self._state.event_log)

    # -----------------------------------------------------------------
    #  Internal helpers
    # -----------------------------------------------------------------

    def _get_facts(self, account_id: str, instrument_id: str) -> List[ExecutionFact]:
        return self._state.execution_facts.get(
            f"{account_id}:{instrument_id}", []
        )

    def _check_with_scope(
        self,
        account_id: str,
        instrument_id: str,
        scope: str,
        facts: List[ExecutionFact],
    ) -> ConsistencyCheck:
        pos_view = self._state.position_views.get(
            f"{account_id}:{instrument_id}"
        )
        ledger_view = self._state.ledger_views.get(f"{account_id}:USD")
        return self._run_check(
            account_id, instrument_id, scope, facts, pos_view, ledger_view
        )

    def _run_check(
        self,
        account_id: str,
        instrument_id: str,
        scope: str,
        facts: List[ExecutionFact],
        pos_view: Optional[PositionView],
        ledger_view: Optional[LedgerView],
    ) -> ConsistencyCheck:
        cmd = RunConsistencyCheck(
            account_id=account_id,
            instrument_id=instrument_id,
            execution_facts=facts,
            position_view=pos_view,
            ledger_view=ledger_view,
            check_scope=scope,
            grace_period_ms=self.grace_period_ms,
        )
        check = cmd.execute()
        self._state.check_history.append(check)
        self._emit_events(check)
        return check

    def _emit_events(self, check: ConsistencyCheck) -> None:
        check_key = f"{check.account_id}:{check.instrument_id}"
        previous = self._state.previous_status.get(
            check_key, ConsistencyDomainStatus.CONSISTENT
        )

        if check.is_inconsistent:
            for result in check.results:
                if result.is_inconsistent:
                    event = ConsistencyFailed(
                        check_id=check.check_id,
                        account_id=check.account_id,
                        instrument_id=check.instrument_id,
                        domain=result.domain,
                        failure_type=result.failure_type,
                        expected_value=result.expected_value,
                        actual_value=result.actual_value,
                        delta=result.delta,
                        source_execution_id=result.source_execution_id,
                    )
                    self._state.event_log.append(event)
                    if self._on_event:
                        self._on_event(event)

        elif check.is_consistent and previous in (
            ConsistencyDomainStatus.INCONSISTENT,
            ConsistencyDomainStatus.ESCALATED,
        ):
            # Transition from inconsistent → consistent
            event = ConsistencyRestored(
                check_id=check.check_id,
                account_id=check.account_id,
                instrument_id=check.instrument_id,
                domain="CROSS",
            )
            self._state.event_log.append(event)
            if self._on_event:
                self._on_event(event)

        self._state.previous_status[check_key] = check.overall_status

    def _empty_check(self, account_id: str, instrument_id: str) -> ConsistencyCheck:
        cmd = RunConsistencyCheck(
            account_id=account_id,
            instrument_id=instrument_id,
            execution_facts=[],
        )
        return cmd.execute()
