"""Tests for StrategyController (Commit 26 Part 1.3, spec sections 6–8, 30–31)."""

from uuid import uuid4

from services.control_plane.strategy import StrategyState
from services.control_plane.strategy.audit import (
    StrategyControlAuditEventType,
)


def test_default_state_is_running(controller):
    assert controller.state("alpha_nvda") is StrategyState.RUNNING


def test_running_strategy_has_full_capability(controller):
    decision = controller.evaluate("alpha_nvda")
    assert decision.strategy_id == "alpha_nvda"
    assert decision.current_state is StrategyState.RUNNING
    assert decision.allow_signal_generation
    assert decision.allow_new_orders
    assert decision.allow_reduce_orders
    assert decision.reason == "strategy_running"
    assert decision.allow_any_orders


def test_paused_strategy_blocks_new_orders(controller):
    controller.set_state("alpha_nvda", StrategyState.PAUSED)

    decision = controller.evaluate("alpha_nvda")

    assert not decision.allow_signal_generation
    assert not decision.allow_new_orders
    assert decision.allow_reduce_orders
    assert decision.current_state is StrategyState.PAUSED
    assert decision.reason == "strategy_paused"


def test_draining_strategy_allows_reduction(controller):
    controller.set_state("alpha_nvda", StrategyState.DRAINING)

    decision = controller.evaluate("alpha_nvda")

    assert not decision.allow_signal_generation
    assert not decision.allow_new_orders
    assert decision.allow_reduce_orders
    assert decision.reason == "strategy_draining"


def test_disabled_strategy_blocks_signal_and_orders(controller):
    controller.set_state("alpha_nvda", StrategyState.DISABLED)

    decision = controller.evaluate("alpha_nvda")

    assert not decision.allow_signal_generation
    assert not decision.allow_new_orders
    assert decision.allow_reduce_orders
    assert decision.reason == "strategy_disabled"


def test_disabled_strategy_can_allow_signal_via_policy(strict_controller):
    strict_controller.set_state("alpha_nvda", StrategyState.DISABLED)

    decision = strict_controller.evaluate("alpha_nvda")

    assert decision.allow_signal_generation
    assert not decision.allow_new_orders
    assert not decision.allow_reduce_orders


def test_policy_can_close_reduce_channel(strict_controller):
    strict_controller.set_state("alpha_nvda", StrategyState.PAUSED)

    decision = strict_controller.evaluate("alpha_nvda")

    assert not decision.allow_reduce_orders


def test_recovering_strategy_is_fail_closed(controller):
    """RECOVERING must block everything until explicitly resumed."""
    controller.set_state("alpha_nvda", StrategyState.RECOVERING)

    decision = controller.evaluate("alpha_nvda")

    assert not decision.allow_signal_generation
    assert not decision.allow_new_orders
    assert not decision.allow_reduce_orders
    assert decision.reason == "unknown_strategy_state"


def test_set_state_overwrites_previous(controller):
    controller.set_state("alpha_nvda", StrategyState.PAUSED)
    controller.set_state("alpha_nvda", StrategyState.RUNNING)

    assert controller.state("alpha_nvda") is StrategyState.RUNNING


def test_strategy_control_isolated(controller):
    """Pausing alpha_nvda must not affect alpha_spy."""
    controller.set_state("alpha_nvda", StrategyState.PAUSED)

    a = controller.evaluate("alpha_nvda")
    b = controller.evaluate("alpha_spy")

    assert not a.allow_new_orders
    assert not a.allow_signal_generation
    assert b.allow_new_orders
    assert b.allow_signal_generation


def test_state_transition_emits_audit_event(controller):
    controller.set_state(
        "alpha_nvda",
        StrategyState.DRAINING,
        incident_id=uuid4(),
        control_id=uuid4(),
        actor="risk-operator",
        reason="strategy anomaly detected",
    )

    records = controller.audit_trail
    assert len(records) == 1
    record = records[0]
    assert record.event_type is (
        StrategyControlAuditEventType.STRATEGY_DRAINING
    )
    assert record.strategy_id == "alpha_nvda"
    assert record.previous_state is StrategyState.RUNNING
    assert record.new_state is StrategyState.DRAINING
    assert record.actor == "risk-operator"
    assert record.reason == "strategy anomaly detected"
    assert record.incident_id is not None
    assert record.control_id is not None


def test_audit_event_mapping_for_each_state(controller):
    expected = {
        StrategyState.RUNNING: (
            StrategyControlAuditEventType.STRATEGY_RESUMED
        ),
        StrategyState.PAUSED: (
            StrategyControlAuditEventType.STRATEGY_PAUSED
        ),
        StrategyState.DRAINING: (
            StrategyControlAuditEventType.STRATEGY_DRAINING
        ),
        StrategyState.DISABLED: (
            StrategyControlAuditEventType.STRATEGY_DISABLED
        ),
        StrategyState.RECOVERING: (
            StrategyControlAuditEventType.STRATEGY_RECOVERING
        ),
    }
    # Leave the default RUNNING state first so every transition below fires.
    controller.set_state("alpha_nvda", StrategyState.DISABLED)

    for state, event_type in expected.items():
        controller.set_state("alpha_nvda", state)
        assert controller.audit_trail[-1].event_type is event_type


def test_duplicate_state_change_does_not_emit_audit_event(controller):
    controller.set_state("alpha_nvda", StrategyState.PAUSED)
    controller.set_state("alpha_nvda", StrategyState.PAUSED)

    assert len(controller.audit_trail) == 1


def test_audit_trail_is_immutable_view(controller):
    controller.set_state("alpha_nvda", StrategyState.PAUSED)
    snapshot = controller.audit_trail
    controller.set_state("alpha_nvda", StrategyState.RUNNING)

    assert len(snapshot) == 1
    assert len(controller.audit_trail) == 2
