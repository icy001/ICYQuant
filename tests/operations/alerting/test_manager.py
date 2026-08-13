"""
Tests for AlertManager (Commit 27 Part 1.3, spec sections 18-26).

覆盖：Firing / Dedup / Resolve / Duration / Suppression /
Storm Protection / Flapping / Alert Lifecycle。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.operations import (
    Alert,
    AlertDeduplicator,
    AlertFingerprint,
    AlertManager,
    AlertRule,
    AlertRuleEvaluator,
    AlertRouter,
    AlertSeverity,
    AlertState,
    AlertStormProtector,
    ConditionEvaluator,
    FlappingDetector,
    ServiceDependency,
)


class _FakeClock:
    def __init__(self) -> None:
        self._now = datetime(2026, 8, 13, 0, 0, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += timedelta(seconds=seconds)


def _rule(rule_id: str = "latency-high", **overrides) -> AlertRule:
    fields = dict(
        rule_id=rule_id,
        name=rule_id,
        metric_name="latency_ms",
        severity=AlertSeverity.WARNING,
        threshold=100,
        operator=">",
    )
    fields.update(overrides)
    return AlertRule(**fields)


def _manager(clock=None, **overrides) -> AlertManager:
    fields = dict(
        evaluator=AlertRuleEvaluator(ConditionEvaluator()),
        deduplicator=AlertDeduplicator(),
        router=AlertRouter(),
        clock=clock,
    )
    fields.update(overrides)
    return AlertManager(**fields)


def test_evaluate_fires_new_alert():
    manager = _manager()

    fingerprint = manager.evaluate(
        _rule(),
        value=200,
    )

    assert fingerprint is not None
    assert manager.deduplicator.is_duplicate(fingerprint)


def test_evaluate_duplicate_returns_none():
    manager = _manager()

    rule = _rule()

    first = manager.evaluate(rule, value=200)

    second = manager.evaluate(rule, value=200)

    assert first is not None
    assert second is None


def test_evaluate_resolve_then_refire():
    """spec section 15: 条件恢复 -> Resolve，再异常 -> 新 Alert。"""
    manager = _manager()

    rule = _rule()

    first = manager.evaluate(rule, value=200)

    assert manager.evaluate(rule, value=50) is None

    assert not manager.deduplicator.is_duplicate(first)

    second = manager.evaluate(rule, value=200)

    assert second == first
    assert manager.deduplicator.is_duplicate(second)


def test_disabled_rule_does_not_fire():
    manager = _manager()

    assert manager.evaluate(
        _rule(enabled=False),
        value=200,
    ) is None


def test_duration_requires_sustained_condition():
    """spec section 24: latency > 100 持续 30 秒才触发。"""
    clock = _FakeClock()
    manager = _manager(clock=clock)

    rule = _rule(duration_seconds=30)

    assert manager.evaluate(rule, value=200) is None

    assert manager.evaluate(rule, value=200) is None

    clock.advance(30)

    assert manager.evaluate(rule, value=200) is not None


def test_duration_window_cleared_when_condition_recovers():
    clock = _FakeClock()
    manager = _manager(clock=clock)

    rule = _rule(duration_seconds=30)

    assert manager.evaluate(rule, value=200) is None

    manager.evaluate(rule, value=50)

    clock.advance(30)

    # 条件恢复后需要重新持续 30 秒
    assert manager.evaluate(rule, value=200) is None

    clock.advance(30)

    assert manager.evaluate(rule, value=200) is not None


def test_suppression_blocks_downstream_alert():
    """spec section 22: event-bus UNHEALTHY 抑制 risk 的告警。"""
    manager = _manager()

    manager.register_dependency(
        ServiceDependency(
            source_service="risk",
            target_service="event-bus",
            required=True,
        )
    )

    manager.mark_unhealthy("event-bus")

    rule = _rule(
        rule_id="service-unavailable",
        threshold=0,
    )

    fingerprint = AlertFingerprint.build(
        "service-unavailable",
        "risk",
        {},
    )

    assert manager.evaluate(
        rule,
        value=1.0,
        service_id="risk",
    ) is None

    assert manager.is_suppressed(fingerprint) == "event-bus"


def test_suppression_released_when_upstream_healthy():
    manager = _manager()

    manager.register_dependency(
        ServiceDependency(
            source_service="risk",
            target_service="event-bus",
            required=True,
        )
    )

    manager.mark_unhealthy("event-bus")

    rule = _rule(
        rule_id="service-unavailable",
        threshold=0,
    )

    fingerprint = AlertFingerprint.build(
        "service-unavailable",
        "risk",
        {},
    )

    assert manager.evaluate(rule, value=1.0, service_id="risk") is None

    manager.mark_healthy("event-bus")

    assert manager.evaluate(rule, value=1.0, service_id="risk") == fingerprint

    assert manager.is_suppressed(fingerprint) is None


def test_suppression_requires_matching_dependency():
    """无依赖关系的服务不健康不抑制本服务告警。"""
    manager = _manager()

    manager.register_dependency(
        ServiceDependency(
            source_service="risk",
            target_service="event-bus",
            required=True,
        )
    )

    manager.mark_unhealthy("ledger")

    assert manager.evaluate(
        _rule(),
        value=200,
        service_id="risk",
    ) is not None


def test_storm_suppression_mode_blocks_new_alerts():
    """spec section 23: 超过窗口上限后进入 SUPPRESSION MODE。"""
    clock = _FakeClock()
    protector = AlertStormProtector(
        max_alerts_per_window=3,
        window_seconds=60.0,
        clock=clock,
    )
    manager = _manager(clock=clock, storm_protector=protector)

    first = manager.evaluate(_rule(rule_id="rule-1"), value=200)
    second = manager.evaluate(_rule(rule_id="rule-2"), value=200)
    third = manager.evaluate(_rule(rule_id="rule-3"), value=200)

    # 第 4 个触发 Storm Detection
    fourth = manager.evaluate(_rule(rule_id="rule-4"), value=200)

    assert first and second and third and fourth

    assert manager.storm_protector.storm_detected

    assert manager.storm_protector.suppression_mode

    # SUPPRESSION MODE 下新告警被抑制
    assert manager.evaluate(
        _rule(rule_id="rule-5"),
        value=200,
    ) is None


def test_flapping_detection_escalates_severity():
    """spec section 26: 反复 FIRING/RESOLVED 触发 Flapping 并提升 severity。"""
    clock = _FakeClock()
    flapping = FlappingDetector(
        max_resolves_per_window=2,
        window_seconds=60.0,
        clock=clock,
    )
    manager = _manager(clock=clock, flapping_detector=flapping)

    rule = _rule()

    fingerprint = None

    for _ in range(4):
        fingerprint = manager.evaluate(rule, value=200)
        manager.evaluate(rule, value=50)

    assert manager.is_flapping(fingerprint)

    assert manager.escalated_severity(
        fingerprint,
        AlertSeverity.WARNING,
    ) == AlertSeverity.ERROR


def test_alert_lifecycle():
    """spec section 19: FIRING -> ACKNOWLEDGED -> RESOLVED；可 SUPPRESSED。"""
    clock = _FakeClock()
    manager = _manager(clock=clock)

    alert = Alert(
        alert_id="ALT-000001",
        rule_id="execution-latency-high",
        severity=AlertSeverity.WARNING,
        state=AlertState.FIRING,
        title="Execution latency high",
        message="latency > 100",
        service_id="execution",
        labels={},
        fired_at=clock(),
    )

    manager.track(alert)

    acknowledged = manager.acknowledge("ALT-000001")
    assert acknowledged.state is AlertState.ACKNOWLEDGED

    resolved = manager.resolve_alert("ALT-000001")
    assert resolved.state is AlertState.RESOLVED
    assert resolved.resolved_at is not None

    # 已 RESOLVED 不能再 acknowledge
    assert manager.acknowledge("ALT-000001") is None

    # SUPPRESSED 分支
    suppressed = Alert(
        alert_id="ALT-000002",
        rule_id="venue-disconnected",
        severity=AlertSeverity.ERROR,
        state=AlertState.FIRING,
        title="Venue disconnected",
        message="heartbeat failure",
        service_id="venue-gateway",
        labels={"venue": "NASDAQ"},
        fired_at=clock(),
    )
    manager.track(suppressed)

    assert manager.suppress_alert(
        "ALT-000002"
    ).state is AlertState.SUPPRESSED

    assert manager.get("ALT-000002") is not None

    assert len(manager.all_alerts()) == 2
