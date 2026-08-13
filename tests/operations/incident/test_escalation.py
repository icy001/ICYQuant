"""Incident escalation tests (Commit 27 Part 1.4, spec sections 21-22, 37-38)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.operations import (
    EscalationPolicy,
    Incident,
    IncidentContext,
    IncidentEscalator,
    IncidentImpact,
    IncidentSeverity,
    IncidentState,
    transition,
)


class FakeClock:

    def __init__(self, start):

        self._now = start

    def __call__(self):

        return self._now

    def advance(self, seconds):

        self._now += timedelta(seconds=seconds)


def _incident(
    severity=IncidentSeverity.MAJOR,
    detected_at=None,
):

    detected_at = detected_at or datetime(
        2026, 8, 13, 13, 0, 0,
        tzinfo=timezone.utc,
    )

    return Incident(
        context=IncidentContext(
            incident_id="INC-ESC-0001",
            created_at=detected_at,
            detected_at=detected_at,
            environment="production",
            source_alert_ids=(),
            trace_ids=(),
        ),
        title="Escalation test",
        description="Escalation test incident",
        severity=severity,
        state=IncidentState.DETECTED,
        impact=IncidentImpact(
            affected_services=("risk",),
            affected_venues=(),
            affected_strategies=(),
            affected_orders=0,
            affected_positions=0,
            trading_blocked=False,
        ),
    )


def test_severity_can_only_increase():
    # spec section 37
    escalator = IncidentEscalator()

    result = escalator.escalate(
        IncidentSeverity.MAJOR,
        IncidentSeverity.CRITICAL,
    )

    assert result is IncidentSeverity.CRITICAL


def test_severity_does_not_downgrade():
    # spec section 38
    escalator = IncidentEscalator()

    result = escalator.escalate(
        IncidentSeverity.CRITICAL,
        IncidentSeverity.MAJOR,
    )

    assert result is IncidentSeverity.CRITICAL


def test_escalate_equal_severity_is_noop():

    escalator = IncidentEscalator()

    result = escalator.escalate(
        IncidentSeverity.MINOR,
        IncidentSeverity.MINOR,
    )

    assert result is IncidentSeverity.MINOR


def test_escalate_across_all_levels():

    escalator = IncidentEscalator()

    assert (
        escalator.escalate(
            IncidentSeverity.MINOR,
            IncidentSeverity.CATASTROPHIC,
        )
        is IncidentSeverity.CATASTROPHIC
    )


def test_time_based_escalation_after_duration():
    """spec section 22: MAJOR 持续 5 minutes 没有缓解 -> CRITICAL。"""

    start = datetime(
        2026, 8, 13, 13, 0, 0,
        tzinfo=timezone.utc,
    )

    clock = FakeClock(start)

    escalator = IncidentEscalator()

    incident = _incident(
        IncidentSeverity.MAJOR,
        start,
    )

    policy = EscalationPolicy(
        escalate_to=IncidentSeverity.CRITICAL,
        duration_seconds=300,
    )

    clock.advance(299)
    assert (
        escalator.evaluate(
            incident,
            policies=(policy,),
            now=clock(),
        )
        is IncidentSeverity.MAJOR
    )

    clock.advance(2)
    assert (
        escalator.evaluate(
            incident,
            policies=(policy,),
            now=clock(),
        )
        is IncidentSeverity.CRITICAL
    )


def test_time_based_escalation_stops_after_mitigation():

    start = datetime(
        2026, 8, 13, 13, 0, 0,
        tzinfo=timezone.utc,
    )

    clock = FakeClock(start)

    escalator = IncidentEscalator()

    incident = _incident(
        IncidentSeverity.MAJOR,
        start,
    )

    transition(incident, IncidentState.TRIAGED)
    transition(incident, IncidentState.MITIGATING)

    policy = EscalationPolicy(
        escalate_to=IncidentSeverity.CRITICAL,
        duration_seconds=300,
    )

    clock.advance(600)

    assert (
        escalator.evaluate(
            incident,
            policies=(policy,),
            now=clock(),
        )
        is IncidentSeverity.MAJOR
    )


def test_time_based_escalation_picks_highest_applicable_policy():

    start = datetime(
        2026, 8, 13, 13, 0, 0,
        tzinfo=timezone.utc,
    )

    clock = FakeClock(start)

    escalator = IncidentEscalator()

    incident = _incident(
        IncidentSeverity.MAJOR,
        start,
    )

    policies = (
        EscalationPolicy(
            escalate_to=IncidentSeverity.CRITICAL,
            duration_seconds=300,
        ),
        EscalationPolicy(
            escalate_to=IncidentSeverity.CATASTROPHIC,
            duration_seconds=600,
        ),
    )

    clock.advance(900)

    assert (
        escalator.evaluate(
            incident,
            policies=policies,
            now=clock(),
        )
        is IncidentSeverity.CATASTROPHIC
    )
