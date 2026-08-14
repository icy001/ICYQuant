"""Shared fixtures for order domain event tests (Commit 33 Part 1.4)."""

from __future__ import annotations

from datetime import datetime

import pytest

from services.order.domain.events import OrderCreated

TS = datetime(2026, 8, 13, 9, 30, 0)


@pytest.fixture
def make_event():
    def _make_event(cls=OrderCreated, **overrides):
        defaults = dict(
            event_id="EVT-ORD-000001",
            aggregate_id="ORD-20260813-000001",
            aggregate_type="ORDER",
            order_id="ORD-20260813-000001",
            order_request_id="OR-20260813-000001",
            correlation_id="CORR-001",
            causation_id=None,
            occurred_at=TS,
            sequence=1,
            payload_version=1,
        )
        defaults.update(overrides)
        return cls(**defaults)

    return _make_event
