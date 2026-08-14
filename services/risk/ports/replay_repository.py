"""
Risk decision replay repository port (Commit 41 Part 1.4).

Stores the append-only audit trail of replay verifications.  Replay records
are immutable: once a replay has run (and its outcome has been persisted) it
can never be changed, which keeps the verification history trustworthy.
"""

from __future__ import annotations

from typing import Protocol

from ..replay_record import RiskDecisionReplayRecord


class RiskDecisionReplayRepository(Protocol):
    def save(self, record: RiskDecisionReplayRecord) -> None:
        """Persist a replay record.  Replays are append-only."""

    def get_by_replay_id(
        self,
        replay_id: str,
    ) -> RiskDecisionReplayRecord | None:
        """Load a single replay record by its ``replay_id``."""

    def list_by_decision_id(
        self,
        decision_id: str,
    ) -> tuple[RiskDecisionReplayRecord, ...]:
        """Return every replay for ``decision_id``, oldest first."""


__all__ = [
    "RiskDecisionReplayRepository",
]
