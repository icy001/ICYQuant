"""
Risk decision audit (Commit 41 Part 1.5).

The audit is a pure recording layer: it stores the *already-produced* final
decision trace and never recomputes Risk.  Recomputing Risk inside the audit
would open a second, divergent calculation path between the audited data and
the decision that was actually executed.

    Risk Engine
        |
        | decision
        v
    Decision Trace
        |
        v
    Audit

``RiskDecisionAudit`` is idempotent per ``decision_id``: the same decision
(Event retry, Consumer retry, Service restart, Event replay) is recorded once
and duplicate records are ignored.
"""

from __future__ import annotations

from threading import RLock

from ..domain.risk_decision_trace import RiskDecisionTrace


class RiskDecisionAudit:
    """Idempotent in-memory record of final risk decision traces.

    Thread-safe: ``record`` / ``get`` / ``list_all`` / ``count`` are guarded
    by a re-entrant lock so concurrent consumers cannot corrupt the index or
    produce duplicate entries.
    """

    def __init__(self) -> None:
        self._traces: dict[str, RiskDecisionTrace] = {}
        self._lock = RLock()

    def record(self, trace: RiskDecisionTrace) -> None:
        """Record ``trace``, ignoring duplicates for the same ``decision_id``.

        The audit never modifies the trace: first write wins, exactly like a
        store keyed by ``decision_id``.
        """
        with self._lock:
            self._traces.setdefault(trace.decision_id, trace)

    def get(self, decision_id: str) -> RiskDecisionTrace | None:
        """Return the recorded trace for ``decision_id`` or ``None``."""
        with self._lock:
            return self._traces.get(decision_id)

    def list_all(self) -> tuple[RiskDecisionTrace, ...]:
        """Return every recorded trace in insertion order."""
        with self._lock:
            return tuple(self._traces.values())

    def count(self) -> int:
        """Return the number of unique decisions recorded."""
        with self._lock:
            return len(self._traces)


__all__ = [
    "RiskDecisionAudit",
]
