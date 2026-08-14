"""
Tests for the in-memory risk decision replay repository (Commit 41 Part 1.4).

Replay records form an append-only audit trail per decision id:
``list_by_decision_id`` returns every verification (oldest first) without
ever mutating the historical decision record.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.risk.infrastructure.repositories.in_memory_replay_repository import (
    InMemoryRiskDecisionReplayRepository,
)
from services.risk.replay_record import RiskDecisionReplayRecord

FIXED_NOW = datetime(2026, 8, 14, 12, 0, 0, tzinfo=timezone.utc)


def make_record(
    replay_id="REPLAY-001",
    decision_id="DEC-001",
    matched=True,
    status="MATCHED",
    differences=(),
):
    return RiskDecisionReplayRecord(
        replay_id=replay_id,
        decision_id=decision_id,
        original_decision="APPROVED",
        replayed_decision="APPROVED",
        status=status,
        matched=matched,
        differences=differences,
        replayed_at=FIXED_NOW,
    )


def test_save_and_get_by_replay_id():
    repository = InMemoryRiskDecisionReplayRepository()
    record = make_record()

    repository.save(record)

    assert repository.get_by_replay_id("REPLAY-001") == record


def test_get_missing_returns_none():
    repository = InMemoryRiskDecisionReplayRepository()

    assert repository.get_by_replay_id("REPLAY-UNKNOWN") is None


def test_list_by_decision_id_returns_in_order():
    repository = InMemoryRiskDecisionReplayRepository()
    repository.save(make_record("REPLAY-001", "DEC-001"))
    repository.save(make_record("REPLAY-002", "DEC-001", matched=False, status="MISMATCHED"))
    repository.save(make_record("REPLAY-003", "DEC-002"))

    records = repository.list_by_decision_id("DEC-001")

    assert [record.replay_id for record in records] == [
        "REPLAY-001",
        "REPLAY-002",
    ]
    assert records[1].status == "MISMATCHED"
    assert records[1].matched is False


def test_list_by_decision_id_empty_when_unknown():
    repository = InMemoryRiskDecisionReplayRepository()

    assert repository.list_by_decision_id("DEC-UNKNOWN") == ()


def test_save_is_append_only():
    repository = InMemoryRiskDecisionReplayRepository()
    first = make_record()
    second = make_record(replay_id="REPLAY-002", matched=False, status="MISMATCHED")

    repository.save(first)
    repository.save(second)

    assert len(repository.list_by_decision_id("DEC-001")) == 2


def test_record_is_immutable():
    record = make_record()

    with pytest.raises(Exception):
        record.matched = False  # type: ignore[misc]
