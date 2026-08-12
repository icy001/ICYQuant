"""Tests for PortfolioController (Commit 26 Part 1.3, spec sections 13, 21–22, 30–31)."""

from uuid import uuid4

from services.control_plane.portfolio import PortfolioState
from services.control_plane.portfolio.audit import (
    PortfolioControlAuditEventType,
)


def test_default_state_is_active(controller):
    assert controller.state("portfolio_main") is PortfolioState.ACTIVE


def test_active_portfolio_has_full_capability(controller):
    decision = controller.evaluate("portfolio_main")
    assert decision.portfolio_id == "portfolio_main"
    assert decision.current_state is PortfolioState.ACTIVE
    assert decision.allow_new_risk
    assert decision.allow_new_orders
    assert decision.allow_reduce_orders
    assert decision.allow_liquidation
    assert decision.reason == "portfolio_active"


def test_restricted_portfolio_blocks_new_risk(controller):
    controller.set_state("portfolio_main", PortfolioState.RESTRICTED)

    decision = controller.evaluate("portfolio_main")

    assert not decision.allow_new_risk
    assert not decision.allow_new_orders
    assert decision.allow_reduce_orders
    assert decision.allow_liquidation
    assert decision.reason == "portfolio_restricted"


def test_reduce_only_portfolio_blocks_new_risk(controller):
    controller.set_state("portfolio_main", PortfolioState.REDUCE_ONLY)

    decision = controller.evaluate("portfolio_main")

    assert not decision.allow_new_risk
    assert not decision.allow_new_orders
    assert decision.allow_reduce_orders
    assert decision.allow_liquidation
    assert decision.reason == "portfolio_reduce_only"


def test_frozen_portfolio_blocks_new_risk(controller):
    controller.set_state("portfolio_main", PortfolioState.FROZEN)

    decision = controller.evaluate("portfolio_main")

    assert not decision.allow_new_risk
    assert not decision.allow_new_orders
    assert decision.allow_reduce_orders
    assert decision.allow_liquidation
    assert decision.reason == "portfolio_frozen"


def test_liquidating_portfolio_allows_liquidation(controller):
    controller.set_state("portfolio_main", PortfolioState.LIQUIDATING)

    decision = controller.evaluate("portfolio_main")

    assert decision.allow_liquidation
    assert decision.allow_reduce_orders
    assert not decision.allow_new_orders
    assert not decision.allow_new_risk
    assert decision.reason == "portfolio_liquidating"


def test_recovering_portfolio_is_fail_closed(controller):
    """RECOVERING must block everything until explicitly activated."""
    controller.set_state("portfolio_main", PortfolioState.RECOVERING)

    decision = controller.evaluate("portfolio_main")

    assert not decision.allow_new_risk
    assert not decision.allow_new_orders
    assert not decision.allow_reduce_orders
    assert not decision.allow_liquidation
    assert decision.reason == "unknown_portfolio_state"


def test_policy_can_close_reduce_channel(strict_controller):
    strict_controller.set_state("portfolio_main", PortfolioState.FROZEN)

    decision = strict_controller.evaluate("portfolio_main")

    assert not decision.allow_reduce_orders


def test_portfolio_control_isolated(controller):
    """Freezing portfolio A must not affect portfolio B."""
    controller.set_state("portfolio_A", PortfolioState.FROZEN)

    a = controller.evaluate("portfolio_A")
    b = controller.evaluate("portfolio_B")

    assert not a.allow_new_orders
    assert not a.allow_new_risk
    assert b.allow_new_orders
    assert b.allow_new_risk


def test_state_transition_emits_audit_event(controller):
    controller.set_state(
        "portfolio_main",
        PortfolioState.REDUCE_ONLY,
        incident_id=uuid4(),
        control_id=uuid4(),
        actor="risk-operator",
        reason="portfolio exposure over limit",
    )

    records = controller.audit_trail
    assert len(records) == 1
    record = records[0]
    assert record.event_type is (
        PortfolioControlAuditEventType.PORTFOLIO_REDUCE_ONLY
    )
    assert record.portfolio_id == "portfolio_main"
    assert record.previous_state is PortfolioState.ACTIVE
    assert record.new_state is PortfolioState.REDUCE_ONLY
    assert record.actor == "risk-operator"
    assert record.reason == "portfolio exposure over limit"
    assert record.incident_id is not None
    assert record.control_id is not None


def test_audit_event_mapping_for_each_state(controller):
    expected = {
        PortfolioState.ACTIVE: (
            PortfolioControlAuditEventType.PORTFOLIO_ACTIVATED
        ),
        PortfolioState.RESTRICTED: (
            PortfolioControlAuditEventType.PORTFOLIO_RESTRICTED
        ),
        PortfolioState.REDUCE_ONLY: (
            PortfolioControlAuditEventType.PORTFOLIO_REDUCE_ONLY
        ),
        PortfolioState.FROZEN: (
            PortfolioControlAuditEventType.PORTFOLIO_FROZEN
        ),
        PortfolioState.LIQUIDATING: (
            PortfolioControlAuditEventType.PORTFOLIO_LIQUIDATING
        ),
        PortfolioState.RECOVERING: (
            PortfolioControlAuditEventType.PORTFOLIO_RECOVERING
        ),
    }
    # Leave the default ACTIVE state first so every transition below fires.
    controller.set_state("portfolio_main", PortfolioState.FROZEN)

    for state, event_type in expected.items():
        controller.set_state("portfolio_main", state)
        assert controller.audit_trail[-1].event_type is event_type


def test_duplicate_state_change_does_not_emit_audit_event(controller):
    controller.set_state("portfolio_main", PortfolioState.FROZEN)
    controller.set_state("portfolio_main", PortfolioState.FROZEN)

    assert len(controller.audit_trail) == 1


def test_audit_trail_is_immutable_view(controller):
    controller.set_state("portfolio_main", PortfolioState.FROZEN)
    snapshot = controller.audit_trail
    controller.set_state("portfolio_main", PortfolioState.ACTIVE)

    assert len(snapshot) == 1
    assert len(controller.audit_trail) == 2
