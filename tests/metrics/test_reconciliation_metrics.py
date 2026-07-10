from services.metrics import (
    ReconciliationMetrics,
)


def test_reconciliation_metrics():
    metrics = ReconciliationMetrics()

    metrics.record_failure()

    metrics.record_repair()

    metrics.set_pending(
        5
    )

    assert (
        metrics.failures.get()
        ==
        1
    )

    assert (
        metrics.repairs.get()
        ==
        1
    )

    assert (
        metrics.pending.get()
        ==
        5
    )