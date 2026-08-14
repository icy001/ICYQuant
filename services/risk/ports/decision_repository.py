"""Risk decision repository port (Commit 41 Part 1.2).

The Risk Domain depends on this ``Protocol`` instead of any concrete
storage backend (PostgreSQL / SQLite / Redis / MongoDB / ...); the actual
storage technology is chosen by the infrastructure layer.
"""

from __future__ import annotations

from typing import Protocol

from ..decision.decision_record import RiskDecisionRecord
from ..policy_trace import RiskPolicyTrace


class RiskDecisionRepository(Protocol):
    """Persists and queries immutable risk decision records."""

    def save(self, record: RiskDecisionRecord) -> None:
        """Persist ``record``.

        Must be idempotent per ``request_id``: a request_id that already
        produced a decision cannot silently produce a second one.  When
        ``record.request_id`` already maps to a different ``decision_id``
        the implementation must raise ``ValueError``.
        """
        ...

    def get_by_decision_id(self, decision_id: str) -> RiskDecisionRecord | None:
        """Return the record for ``decision_id``, or ``None``."""
        ...

    def get_by_request_id(self, request_id: str) -> RiskDecisionRecord | None:
        """Return the single record for ``request_id``, or ``None``."""
        ...

    def get_policy_trace(self, decision_id: str) -> RiskPolicyTrace | None:
        """Return the immutable policy trace for ``decision_id``.

        The trace answers "why was this trade approved / rejected?" and is
        the backbone of the Risk Dashboard.  Returns ``None`` when no record
        exists for ``decision_id``.
        """
        ...
