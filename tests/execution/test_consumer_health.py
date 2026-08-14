from services.execution.application.consumer_health_service import (
    ConsumerHealthService,
)
from services.execution.domain.consumer import (
    ConsumerOffset,
)
from services.execution.domain.consumer_health import (
    ConsumerHealthStatus,
)
from services.execution.infrastructure.memory_consumer_offset_store import (
    InMemoryConsumerOffsetStore,
)


def test_healthy_with_offset():

    offset_store = (
        InMemoryConsumerOffsetStore()
    )

    offset_store.save(
        ConsumerOffset(
            consumer_id="position-service",
            stream_id="exec-001",
            sequence=42,
        )
    )

    service = ConsumerHealthService(
        offset_store=offset_store,
    )

    health = service.healthy(
        "position-service",
        "exec-001",
    )

    assert (
        health.status
        == ConsumerHealthStatus.HEALTHY
    )

    assert (
        health.consumer_id
        == "position-service"
    )

    assert health.last_sequence == 42

    assert health.failed_sequence is None

    assert health.error is None


def test_healthy_without_offset():

    offset_store = (
        InMemoryConsumerOffsetStore()
    )

    service = ConsumerHealthService(
        offset_store=offset_store,
    )

    health = service.healthy(
        "position-service",
        "exec-001",
    )

    assert (
        health.status
        == ConsumerHealthStatus.HEALTHY
    )

    assert health.last_sequence == 0


def test_health_is_isolated_per_consumer():

    offset_store = (
        InMemoryConsumerOffsetStore()
    )

    offset_store.save(
        ConsumerOffset(
            consumer_id="position-service",
            stream_id="exec-001",
            sequence=100,
        )
    )

    service = ConsumerHealthService(
        offset_store=offset_store,
    )

    position = service.healthy(
        "position-service",
        "exec-001",
    )

    audit = service.healthy(
        "audit-service",
        "exec-001",
    )

    assert position.last_sequence == 100

    assert audit.last_sequence == 0
