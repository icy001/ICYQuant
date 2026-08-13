"""
Tests for OperationalSnapshotBuilder (Commit 27 Part 1.1,
spec sections 13-15, 21).

聚合规则（spec section 14）：
    unhealthy > 0                -> UNHEALTHY
    stopped   > 0                -> UNHEALTHY
    degraded  > 0                -> DEGRADED
    全部 HEALTHY                 -> HEALTHY
    其他（STARTING/UNKNOWN/空）  -> UNKNOWN
"""

from datetime import datetime, timezone

from services.operations import (
    OperationalSnapshotBuilder,
    ServiceHealth,
    ServiceState,
)


def _health(service_id: str, state: ServiceState) -> ServiceHealth:
    return ServiceHealth(
        service_id=service_id,
        state=state,
        checked_at=datetime.now(timezone.utc),
    )


def test_snapshot_all_healthy():
    builder = OperationalSnapshotBuilder()

    snapshot = builder.build([
        _health("risk", ServiceState.HEALTHY),
        _health("execution", ServiceState.HEALTHY),
        _health("venue", ServiceState.HEALTHY),
    ])

    assert snapshot.overall_state is ServiceState.HEALTHY
    assert snapshot.total_services == 3
    assert snapshot.healthy_services == 3
    assert snapshot.degraded_services == 0
    assert snapshot.unhealthy_services == 0
    assert snapshot.stopped_services == 0


def test_snapshot_detects_degraded_service():
    """spec section 21. Execution 延迟 -> Overall = DEGRADED。"""
    builder = OperationalSnapshotBuilder()

    records = [
        _health("risk", ServiceState.HEALTHY),
        _health("execution", ServiceState.DEGRADED),
    ]

    snapshot = builder.build(records)

    assert snapshot.overall_state == ServiceState.DEGRADED
    assert snapshot.total_services == 2
    assert snapshot.healthy_services == 1
    assert snapshot.degraded_services == 1


def test_snapshot_detects_unhealthy_service():
    """Risk 出问题 -> Overall = UNHEALTHY。"""
    builder = OperationalSnapshotBuilder()

    records = [
        _health("risk", ServiceState.UNHEALTHY),
        _health("execution", ServiceState.HEALTHY),
    ]

    snapshot = builder.build(records)

    assert snapshot.overall_state is ServiceState.UNHEALTHY
    assert snapshot.unhealthy_services == 1
    assert snapshot.healthy_services == 1


def test_snapshot_unhealthy_takes_precedence_over_degraded():
    """UNHEALTHY 优先于 DEGRADED。"""
    builder = OperationalSnapshotBuilder()

    records = [
        _health("risk", ServiceState.UNHEALTHY),
        _health("execution", ServiceState.DEGRADED),
    ]

    snapshot = builder.build(records)

    assert snapshot.overall_state is ServiceState.UNHEALTHY


def test_snapshot_stopped_counts_as_unhealthy():
    builder = OperationalSnapshotBuilder()

    records = [
        _health("risk", ServiceState.HEALTHY),
        _health("venue-gateway", ServiceState.STOPPED),
    ]

    snapshot = builder.build(records)

    assert snapshot.overall_state is ServiceState.UNHEALTHY
    assert snapshot.stopped_services == 1


def test_snapshot_starting_is_unknown():
    """STARTING 不计入任何健康桶 -> Overall = UNKNOWN。"""
    builder = OperationalSnapshotBuilder()

    records = [
        _health("risk", ServiceState.STARTING),
    ]

    snapshot = builder.build(records)

    assert snapshot.overall_state is ServiceState.UNKNOWN
    assert snapshot.total_services == 1
    assert snapshot.healthy_services == 0


def test_snapshot_empty_is_unknown():
    builder = OperationalSnapshotBuilder()

    snapshot = builder.build([])

    assert snapshot.overall_state is ServiceState.UNKNOWN
    assert snapshot.total_services == 0


def test_snapshot_generates_timestamp():
    builder = OperationalSnapshotBuilder()

    snapshot = builder.build([])

    assert snapshot.generated_at is not None


def test_snapshot_accepts_generator_input():
    """build 接受任意可迭代对象（例如生成器）。"""
    builder = OperationalSnapshotBuilder()

    def records():
        yield _health("risk", ServiceState.HEALTHY)
        yield _health("execution", ServiceState.HEALTHY)

    snapshot = builder.build(records())

    assert snapshot.overall_state is ServiceState.HEALTHY
    assert snapshot.total_services == 2
