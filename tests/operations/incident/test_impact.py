"""Incident impact tests (Commit 27 Part 1.4, spec sections 6, 18-20, 39)."""

from __future__ import annotations

import dataclasses

import pytest

from services.operations import (
    ImpactCalculator,
    IncidentImpact,
    IncidentSeverity,
    assess_severity,
)


def test_impact_tracks_trading_effect():
    # spec section 39
    calculator = ImpactCalculator()

    impact = calculator.calculate(
        affected_services=("risk", "oms"),
        affected_orders=42,
        affected_positions=7,
        trading_blocked=True,
        capital_at_risk=1_250_000,
    )

    assert impact.trading_blocked
    assert impact.affected_orders == 42
    assert impact.affected_positions == 7
    assert impact.capital_at_risk == 1_250_000
    assert impact.affected_services == ("risk", "oms")
    assert impact.affected_venues == ()
    assert impact.affected_strategies == ()


def test_calculator_defaults():

    impact = ImpactCalculator().calculate(
        affected_services=("risk",),
    )

    assert impact.affected_orders == 0
    assert impact.affected_positions == 0
    assert impact.trading_blocked is False
    assert impact.capital_at_risk == 0.0
    assert impact.description == ""


def test_calculator_normalizes_list_input():

    impact = ImpactCalculator().calculate(
        affected_services=["risk", "oms"],
    )

    assert impact.affected_services == ("risk", "oms")
    assert isinstance(impact.affected_services, tuple)


def test_impact_is_frozen():

    impact = ImpactCalculator().calculate(
        affected_services=("risk",),
    )

    with pytest.raises(dataclasses.FrozenInstanceError):

        impact.affected_orders = 1


def test_assess_severity_no_trading_impact_is_minor():

    impact = ImpactCalculator().calculate(
        affected_services=(),
    )

    assert assess_severity(impact) is IncidentSeverity.MINOR


def test_assess_severity_single_service_is_moderate():

    impact = ImpactCalculator().calculate(
        affected_services=("audit",),
    )

    assert assess_severity(impact) is IncidentSeverity.MODERATE


def test_assess_severity_strategy_impacted_is_major():

    impact = IncidentImpact(
        affected_services=("risk",),
        affected_venues=(),
        affected_strategies=(
            "momentum-01",
            "alpha-07",
        ),
        affected_orders=5,
        affected_positions=0,
        trading_blocked=False,
    )

    assert assess_severity(impact) is IncidentSeverity.MAJOR


def test_assess_severity_position_inconsistency_is_critical():

    impact = ImpactCalculator().calculate(
        affected_services=("risk",),
        affected_positions=3,
    )

    assert assess_severity(impact) is IncidentSeverity.CRITICAL


def test_assess_severity_trading_blocked_is_critical():

    impact = ImpactCalculator().calculate(
        affected_services=("risk",),
        trading_blocked=True,
    )

    assert assess_severity(impact) is IncidentSeverity.CRITICAL


def test_assess_severity_global_compromise_is_catastrophic():

    impact = ImpactCalculator().calculate(
        affected_services=("risk",),
        affected_positions=7,
        trading_blocked=True,
        capital_at_risk=1_250_000,
    )

    assert assess_severity(impact) is IncidentSeverity.CATASTROPHIC
