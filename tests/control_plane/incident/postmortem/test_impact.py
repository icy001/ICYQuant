"""Incident impact model."""

from __future__ import annotations

from services.control_plane.incident.postmortem.impact import IncidentImpact


def test_impact_holds_counts():
    impact = IncidentImpact(
        affected_accounts=5,
        affected_orders=12,
        affected_positions=8,
        rejected_orders=2,
        cancelled_orders=1,
    )
    assert impact.affected_accounts == 5
    assert impact.affected_orders == 12
    assert impact.affected_positions == 8
    assert impact.rejected_orders == 2
    assert impact.cancelled_orders == 1


def test_impact_defaults():
    impact = IncidentImpact()
    assert impact.estimated_pnl_impact == 0.0
    assert impact.duration_seconds == 0.0
    assert impact.trading_halted is False
    assert impact.affected_strategies is None
    assert impact.affected_services is None


def test_impact_optional_scope():
    impact = IncidentImpact(
        trading_halted=True,
        affected_strategies=["grid-eth-1"],
        affected_services=["execution"],
    )
    assert impact.trading_halted is True
    assert impact.affected_strategies == ["grid-eth-1"]
