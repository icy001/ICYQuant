"""Shared fixtures for event store tests (Commit 34 Part 1.1)."""

from __future__ import annotations

from datetime import datetime

import pytest

from services.event_store.domain.event import StoredEvent
from services.event_store.infrastructure.memory_repository import (
    InMemoryEventStoreRepository,
)

TS = datetime(2026, 8, 13, 9, 30, 0)


@pytest.fixture
def repository() -> InMemoryEventStoreRepository:
    return InMemoryEventStoreRepository()


@pytest.fixture
def make_stored_event():
    def _make(
        event_id="EVT-ORD-000001",
        aggregate_id="ORD-001",
        version=1,
        **overrides,
    ):
        defaults = dict(
            event_id=event_id,
            aggregate_id=aggregate_id,
            aggregate_type="ORDER",
            aggregate_version=version,
            event_type="ORDER_CREATED",
            payload={},
            correlation_id="CORR-001",
            causation_id=None,
            occurred_at=TS,
            stored_at=TS,
        )
        defaults.update(overrides)
        return StoredEvent(**defaults)

    return _make


@pytest.fixture
def make_events(make_stored_event):
    """Build a contiguous batch of events for one aggregate.

    ``versions=(1, 2, 3)`` yields ``(EVT-ORD-000001@v1, EVT-ORD-000002@v2,
    EVT-ORD-000003@v3)`` so the event_id always matches the version.
    """

    def _make(versions=(1,), aggregate_id="ORD-001", **overrides):
        events = []
        for version in versions:
            events.append(
                make_stored_event(
                    event_id=f"EVT-ORD-{version:06d}",
                    aggregate_id=aggregate_id,
                    version=version,
                    **overrides,
                )
            )
        return tuple(events)

    return _make
