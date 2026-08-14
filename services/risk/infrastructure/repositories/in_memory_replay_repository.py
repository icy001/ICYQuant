"""
In-memory risk decision replay repository (Commit 41 Part 1.4).

Simple append-only store used for tests and single-process deployments.
Insertion order is preserved so ``list_by_decision_id`` returns replays in
the order they were created.
"""

from __future__ import annotations

from ...replay_record import RiskDecisionReplayRecord


class InMemoryRiskDecisionReplayRepository:
    """Thread-unsafe, in-memory implementation of the replay repository."""

    def __init__(self) -> None:
        self._records: dict[str, RiskDecisionReplayRecord] = {}

    def save(self, record: RiskDecisionReplayRecord) -> None:
        """Persist a replay record (append-only, keyed by ``replay_id``)."""
        self._records[record.replay_id] = record

    def get_by_replay_id(
        self,
        replay_id: str,
    ) -> RiskDecisionReplayRecord | None:
        return self._records.get(replay_id)

    def list_by_decision_id(
        self,
        decision_id: str,
    ) -> tuple[RiskDecisionReplayRecord, ...]:
        return tuple(
            record
            for record in self._records.values()
            if record.decision_id == decision_id
        )


__all__ = [
    "InMemoryRiskDecisionReplayRepository",
]
