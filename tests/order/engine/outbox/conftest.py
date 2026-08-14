"""Shared fixtures for outbox tests (Commit 33 Part 1.5)."""

from __future__ import annotations

from datetime import datetime

import pytest

from services.order.domain.events import OrderCreated
from services.order.engine.events import envelope_from_event
from services.order.engine.outbox.dispatcher import (
    InMemoryOutboxPublisher,
    OutboxDispatcher,
)
from services.order.engine.outbox.model import OutboxMessage
from services.order.engine.outbox.recovery import OutboxRecovery
from services.order.engine.outbox.repository import InMemoryOutboxRepository
from services.order.engine.outbox.retry import RetryPolicy
from services.order.engine.outbox.service import OutboxService

TS = datetime(2026, 8, 13, 9, 30, 0)


@pytest.fixture
def repository() -> InMemoryOutboxRepository:
    return InMemoryOutboxRepository()


@pytest.fixture
def publisher() -> InMemoryOutboxPublisher:
    return InMemoryOutboxPublisher()


@pytest.fixture
def retry_policy() -> RetryPolicy:
    return RetryPolicy(max_attempts=5)


@pytest.fixture
def service(repository: InMemoryOutboxRepository) -> OutboxService:
    return OutboxService(repository)


@pytest.fixture
def dispatcher(
    repository: InMemoryOutboxRepository,
    publisher: InMemoryOutboxPublisher,
    retry_policy: RetryPolicy,
) -> OutboxDispatcher:
    return OutboxDispatcher(repository, publisher, retry_policy)


@pytest.fixture
def recovery(
    repository: InMemoryOutboxRepository,
    retry_policy: RetryPolicy,
) -> OutboxRecovery:
    return OutboxRecovery(repository, retry_policy)


@pytest.fixture
def make_envelope():
    def _make_envelope(cls=OrderCreated, sequence=1, **overrides):
        payload = overrides.pop("payload", None)
        defaults = dict(
            event_id=f"EVT-ORD-{sequence:06d}",
            aggregate_id="ORD-20260813-000001",
            aggregate_type="ORDER",
            order_id="ORD-20260813-000001",
            order_request_id="OR-20260813-000001",
            correlation_id="CORR-001",
            causation_id=None,
            occurred_at=TS,
            sequence=sequence,
            payload_version=1,
        )
        defaults.update(overrides)
        event = cls(**defaults)
        return envelope_from_event(event, payload=payload)

    return _make_envelope


@pytest.fixture
def make_message():
    def _make_message(**overrides):
        defaults = dict(
            message_id="EVT-ORD-000001",
            aggregate_id="ORD-20260813-000001",
            aggregate_type="ORDER",
            aggregate_version=1,
            event_id="EVT-ORD-000001",
            event_type="ORDER_CREATED",
            correlation_id="CORR-001",
            causation_id=None,
            payload={},
            occurred_at=TS,
            created_at=TS,
        )
        defaults.update(overrides)
        return OutboxMessage(**defaults)

    return _make_message
