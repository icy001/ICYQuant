from datetime import datetime, timedelta, timezone

from services.control_plane.incident.escalation.engine import (
    IncidentEscalationEngine,
)
from services.control_plane.incident.escalation.level import (
    EscalationLevel,
)
from services.control_plane.incident.incident_status import IncidentStatus


def test_incident_escalates_after_timeout(
    incident_factory,
):

    now = datetime.now(timezone.utc)

    incident = incident_factory(
        severity="CRITICAL",
        updated_at=now - timedelta(seconds=120),
    )

    engine = IncidentEscalationEngine()

    decision = engine.evaluate(
        incident,
        now=now,
    )

    assert decision.should_escalate is True
    assert decision.target_level == EscalationLevel.L4


def test_closed_incident_does_not_escalate(
    incident_factory,
):

    now = datetime.now(timezone.utc)

    incident = incident_factory(
        severity="CRITICAL",
        state="CLOSED",
        updated_at=now - timedelta(hours=1),
    )

    engine = IncidentEscalationEngine()

    decision = engine.evaluate(
        incident,
        now=now,
    )

    assert decision.should_escalate is False


def test_within_timeout_does_not_escalate(incident_factory):
    now = datetime.now(timezone.utc)

    incident = incident_factory(
        severity="CRITICAL",
        updated_at=now - timedelta(seconds=10),
    )

    engine = IncidentEscalationEngine()

    decision = engine.evaluate(incident, now=now)

    assert decision.should_escalate is False
    assert decision.reason == "escalation timeout not reached"


def test_max_level_reached_stops_escalation(incident_factory):
    now = datetime.now(timezone.utc)

    incident = incident_factory(
        severity="CRITICAL",
        escalation_level=EscalationLevel.L4,
        updated_at=now - timedelta(hours=2),
    )

    engine = IncidentEscalationEngine()

    decision = engine.evaluate(incident, now=now)

    assert decision.should_escalate is False
    assert decision.target_level is None
    assert decision.reason == "maximum escalation level reached"


def test_execute_applies_level_and_transition(incident_factory):
    now = datetime.now(timezone.utc)

    incident = incident_factory(
        severity="HIGH",
        updated_at=now - timedelta(seconds=1000),
    )

    engine = IncidentEscalationEngine()

    decision = engine.execute(incident, now=now)

    assert decision.should_escalate is True
    assert incident.escalation_level == EscalationLevel.L3
    assert incident.state is IncidentStatus.ESCALATED
    assert len(incident.transitions) == 1
    assert incident.transitions[0].actor == "incident-escalation-engine"


def test_execute_without_escalation_is_noop(incident_factory):
    now = datetime.now(timezone.utc)

    incident = incident_factory(
        severity="CRITICAL",
        state="CLOSED",
        updated_at=now - timedelta(hours=1),
    )

    engine = IncidentEscalationEngine()

    decision = engine.execute(incident, now=now)

    assert decision.should_escalate is False
    # CRITICAL starts at L3 and must not move when the incident is closed
    assert incident.escalation_level == EscalationLevel.L3
    assert incident.state is IncidentStatus.CLOSED
    assert incident.transitions == []
