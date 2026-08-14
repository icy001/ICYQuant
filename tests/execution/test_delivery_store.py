import pytest

from services.execution.domain.delivery import (
    DeliveryAttempt,
    DeliveryStatus,
)
from services.execution.infrastructure.memory_delivery_store import (
    InMemoryDeliveryStore,
)


def build_attempt(
    consumer_id="position-service",
    stream_id="exec-001",
    sequence=1,
    attempt=1,
    status=DeliveryStatus.PENDING,
    error=None,
):
    return DeliveryAttempt(
        consumer_id=consumer_id,
        stream_id=stream_id,
        sequence=sequence,
        attempt=attempt,
        status=status,
        error=error,
    )


def test_save_and_latest():

    store = InMemoryDeliveryStore()

    store.save(
        build_attempt(
            attempt=1,
            status=DeliveryStatus.PROCESSING,
        )
    )

    store.save(
        build_attempt(
            attempt=2,
            status=DeliveryStatus.RETRYING,
            error="database timeout",
        )
    )

    latest = store.latest(
        "position-service",
        "exec-001",
        1,
    )

    assert latest is not None

    assert latest.attempt == 2

    assert (
        latest.status
        == DeliveryStatus.RETRYING
    )

    assert latest.error == (
        "database timeout"
    )


def test_latest_missing_returns_none():

    store = InMemoryDeliveryStore()

    assert (
        store.latest(
            "position-service",
            "exec-001",
            1,
        )
        is None
    )


def test_latest_is_isolated_per_key():

    store = InMemoryDeliveryStore()

    store.save(build_attempt())

    assert (
        store.latest(
            "ledger-service",
            "exec-001",
            1,
        )
        is None
    )

    assert (
        store.latest(
            "position-service",
            "exec-002",
            1,
        )
        is None
    )

    assert (
        store.latest(
            "position-service",
            "exec-001",
            2,
        )
        is None
    )


def test_save_rejects_invalid_attempt():

    store = InMemoryDeliveryStore()

    with pytest.raises(ValueError):
        store.save(
            build_attempt(
                consumer_id=""
            )
        )

    with pytest.raises(ValueError):
        store.save(
            build_attempt(
                stream_id=""
            )
        )

    with pytest.raises(ValueError):
        store.save(
            build_attempt(
                sequence=0
            )
        )

    with pytest.raises(ValueError):
        store.save(
            build_attempt(
                attempt=0
            )
        )
