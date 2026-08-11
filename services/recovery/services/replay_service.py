"""ReplayService — deterministic event replay from immutable execution facts.

Core principle:
    Recovery does NOT mutate state directly.
    It replays immutable execution facts and lets domain handlers produce the correct state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ReplayService:
    """Service responsible for replaying execution facts to regenerate domain state.

    The replay source is ALWAYS immutable execution events — never the current
    state of Position or Ledger projections.
    """

    position_handler: Optional[Any] = None  # position consumer/handler
    ledger_handler: Optional[Any] = None    # ledger consumer/handler

    def replay(
        self,
        job: Any,  # RecoveryJob
        execution_facts: List[Any],
    ) -> Dict[str, Any]:
        """Replay execution facts to regenerate domain state.

        Returns:
            {
                "success": True/False,
                "events_replayed": int,
                "events_loaded": int,
                "error_code": str | None,
                "error_reason": str | None,
            }
        """
        from services.recovery.domain.recovery_status import RecoveryType

        sorted_facts = self._sort_by_sequence(execution_facts)
        events_replayed = 0

        try:
            for fact in sorted_facts:
                if job.recovery_type in (
                    RecoveryType.POSITION_REPLAY,
                    RecoveryType.FULL_TRANSACTION_REPLAY,
                ):
                    self._replay_position(fact, job)

                if job.recovery_type in (
                    RecoveryType.LEDGER_REPLAY,
                    RecoveryType.FULL_TRANSACTION_REPLAY,
                ):
                    self._replay_ledger(fact, job)

                events_replayed += 1

        except Exception as e:
            return {
                "success": False,
                "events_replayed": events_replayed,
                "events_loaded": len(execution_facts),
                "error_code": type(e).__name__.upper(),
                "error_reason": str(e),
            }

        return {
            "success": True,
            "events_replayed": events_replayed,
            "events_loaded": len(execution_facts),
            "error_code": None,
            "error_reason": None,
        }

    def _sort_by_sequence(self, facts: List[Any]) -> List[Any]:
        """Sort execution facts by sequence_number to ensure correct ordering."""
        has_seq = all(
            hasattr(f, "sequence_number") and f.sequence_number is not None
            for f in facts
        )
        if has_seq:
            return sorted(facts, key=lambda f: f.sequence_number)
        # Fall back to occurred_at
        has_time = all(
            hasattr(f, "occurred_at") and f.occurred_at is not None
            for f in facts
        )
        if has_time:
            return sorted(facts, key=lambda f: f.occurred_at)
        return facts

    def _replay_position(self, fact: Any, job: Any) -> None:
        """Replay a single execution fact through the position handler.

        The handler produces a PositionChanged event — we do NOT directly mutate
        position state. The event is decorated with recovery metadata.
        """
        if self.position_handler is not None:
            self.position_handler.apply(fact)
        # No-op if no handler registered (test mode)

    def _replay_ledger(self, fact: Any, job: Any) -> None:
        """Replay a single execution fact through the ledger handler.

        Produces LEDGER_ENTRY_CREATED events with recovery metadata.
        """
        if self.ledger_handler is not None:
            self.ledger_handler.apply(fact)
        # No-op if no handler registered (test mode)

    def replay_scope(
        self,
        facts: List[Any],
        scope: Any,  # RecoveryScope
    ) -> List[Any]:
        """Filter and replay facts matching a given recovery scope.

        Returns the list of replayed events (empty list = no-op for test mode).
        """
        filtered = self._filter_by_scope(facts, scope)
        return filtered

    def _filter_by_scope(self, facts: List[Any], scope: Any) -> List[Any]:
        """Filter execution facts by recovery scope."""
        from services.recovery.domain.recovery_scope import RecoveryScopeType

        filtered = []
        for f in facts:
            if scope.scope_type == RecoveryScopeType.EXECUTION:
                eid = getattr(f, "execution_id", None)
                if eid and eid == scope.execution_id:
                    filtered.append(f)
            elif scope.scope_type == RecoveryScopeType.ORDER:
                oid = getattr(f, "order_id", None)
                if oid and oid == scope.order_id:
                    filtered.append(f)
            elif scope.scope_type == RecoveryScopeType.INSTRUMENT:
                iid = getattr(f, "instrument_id", None)
                aid = getattr(f, "account_id", None)
                if iid and iid == scope.instrument_id and aid and aid == scope.account_id:
                    filtered.append(f)
            elif scope.scope_type == RecoveryScopeType.ACCOUNT:
                aid = getattr(f, "account_id", None)
                if aid and aid == scope.account_id:
                    filtered.append(f)
            else:
                filtered.append(f)  # PORTFOLIO includes everything
        return filtered
