from services.execution.application.delivery_metrics_registry import (
    DeliveryMetricsRegistry,
)
from services.execution.domain.delivery_metrics import (
    DeliveryMetrics,
)


def test_metrics_start_at_zero():

    metrics = DeliveryMetrics()

    assert metrics.delivered == 0
    assert metrics.failed == 0
    assert metrics.retried == 0
    assert metrics.dead_lettered == 0
    assert metrics.recovered == 0


def test_record_success_and_failure():

    metrics = DeliveryMetrics()

    metrics.record_success()
    metrics.record_success()
    metrics.record_failure()

    assert metrics.delivered == 2
    assert metrics.failed == 1
    assert metrics.retried == 0
    assert metrics.dead_lettered == 0
    assert metrics.recovered == 0


def test_record_all_counters():

    metrics = DeliveryMetrics()

    metrics.record_success()
    metrics.record_failure()
    metrics.record_retry()
    metrics.record_dead_letter()
    metrics.record_recovery()

    assert metrics.delivered == 1
    assert metrics.failed == 1
    assert metrics.retried == 1
    assert metrics.dead_lettered == 1
    assert metrics.recovered == 1


def test_registry_get_creates_on_demand():

    registry = DeliveryMetricsRegistry()

    metrics = registry.get(
        "position-service"
    )

    assert isinstance(
        metrics,
        DeliveryMetrics,
    )

    assert (
        registry.get("position-service")
        is metrics
    )


def test_registry_is_isolated_per_consumer():

    registry = DeliveryMetricsRegistry()

    position = registry.get(
        "position-service"
    )

    ledger = registry.get(
        "ledger-service"
    )

    position.record_success()
    position.record_success()
    ledger.record_dead_letter()

    assert position.delivered == 2
    assert ledger.delivered == 0

    assert ledger.dead_lettered == 1
    assert position.dead_lettered == 0
