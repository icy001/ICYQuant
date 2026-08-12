"""Unit tests: PolicyCondition, CompositeCondition and operators."""

from __future__ import annotations

from services.control_plane.domain.component_state import ComponentState
from services.control_plane.policy.policy_condition import (
    CompositeCondition,
    ConditionConnective,
    ConditionOperator,
    PolicyCondition,
    and_,
    condition,
    evaluate_condition,
    not_,
    or_,
)
from services.control_plane.policy.policy_context import (
    MarketDataFreshness,
    PolicyContext,
)


def _ctx(**kwargs) -> PolicyContext:
    return PolicyContext(**kwargs)


class TestPolicyCondition:
    def test_equals_matches_enum_value(self):
        ctx = _ctx(risk_health=ComponentState.UNHEALTHY)
        c = condition("risk_health", "equals", "UNHEALTHY")
        assert c.evaluate(ctx) is True

    def test_equals_accepts_enum_directly(self):
        ctx = _ctx(risk_health=ComponentState.UNHEALTHY)
        c = condition("risk_health", "equals", ComponentState.UNHEALTHY)
        assert c.evaluate(ctx) is True

    def test_not_equals(self):
        ctx = _ctx(risk_health=ComponentState.HEALTHY)
        c = condition("risk_health", "not_equals", "UNHEALTHY")
        assert c.evaluate(ctx) is True

    def test_greater_than(self):
        ctx = _ctx(market_data_stale_seconds=45.0)
        c = condition("market_data_stale_seconds", "greater_than", 10.0)
        assert c.evaluate(ctx) is True

    def test_greater_than_false(self):
        ctx = _ctx(market_data_stale_seconds=5.0)
        c = condition("market_data_stale_seconds", "greater_than", 10.0)
        assert c.evaluate(ctx) is False

    def test_less_than(self):
        ctx = _ctx(market_data_stale_seconds=5.0)
        c = condition("market_data_stale_seconds", "less_than", 10.0)
        assert c.evaluate(ctx) is True

    def test_contains_list(self):
        ctx = _ctx(active_incidents=["MARKET_DATA_STALE", "RISK_DEGRADED"])
        c = condition("active_incidents", "contains", "MARKET_DATA_STALE")
        assert c.evaluate(ctx) is True

    def test_contains_string(self):
        ctx = _ctx(kill_switch_scope="GLOBAL")
        c = condition("kill_switch_scope", "contains", "GLO")
        assert c.evaluate(ctx) is True

    def test_in_operator(self):
        ctx = _ctx(operational_state="NORMAL")
        c = PolicyCondition(
            "operational_state",
            ConditionOperator.IN,
            ["NORMAL", "DEGRADED"],
        )
        assert c.evaluate(ctx) is True

    def test_all_operator(self):
        ctx = _ctx(active_incidents=["A", "B", "C"])
        c = PolicyCondition(
            "active_incidents", ConditionOperator.ALL, ["A", "C"]
        )
        assert c.evaluate(ctx) is True

    def test_all_operator_missing_one(self):
        ctx = _ctx(active_incidents=["A", "B"])
        c = PolicyCondition(
            "active_incidents", ConditionOperator.ALL, ["A", "C"]
        )
        assert c.evaluate(ctx) is False

    def test_any_operator(self):
        ctx = _ctx(active_incidents=["A"])
        c = PolicyCondition(
            "active_incidents", ConditionOperator.ANY, ["A", "Z"]
        )
        assert c.evaluate(ctx) is True

    def test_unknown_field_resolves_none(self):
        ctx = _ctx()
        c = condition("does_not_exist", "equals", None)
        assert c.evaluate(ctx) is True

    def test_market_data_freshness_equals(self):
        ctx = _ctx(market_data_freshness=MarketDataFreshness.STALE)
        c = condition("market_data_freshness", "equals", "STALE")
        assert c.evaluate(ctx) is True


class TestCompositeCondition:
    def test_and_all_true(self):
        ctx = _ctx(
            risk_health=ComponentState.UNHEALTHY,
            trading_state="TRADING_READY",
        )
        c = and_(
            condition("risk_health", "equals", "UNHEALTHY"),
            condition("trading_state", "equals", "TRADING_READY"),
        )
        assert c.evaluate(ctx) is True

    def test_and_one_false(self):
        ctx = _ctx(
            risk_health=ComponentState.HEALTHY,
            trading_state="TRADING_READY",
        )
        c = and_(
            condition("risk_health", "equals", "UNHEALTHY"),
            condition("trading_state", "equals", "TRADING_READY"),
        )
        assert c.evaluate(ctx) is False

    def test_or_matches(self):
        ctx = _ctx(
            risk_health=ComponentState.HEALTHY,
            position_integrity="UNTRUSTED",
        )
        c = or_(
            condition("risk_health", "equals", "UNHEALTHY"),
            condition("position_integrity", "equals", "UNTRUSTED"),
        )
        assert c.evaluate(ctx) is True

    def test_or_none_match(self):
        ctx = _ctx(
            risk_health=ComponentState.HEALTHY,
            position_integrity="TRUSTED",
        )
        c = or_(
            condition("risk_health", "equals", "UNHEALTHY"),
            condition("position_integrity", "equals", "UNTRUSTED"),
        )
        assert c.evaluate(ctx) is False

    def test_nested_precedence(self):
        # (risk UNHEALTHY OR position UNTRUSTED) AND trading ACTIVE
        ctx = _ctx(
            risk_health=ComponentState.HEALTHY,
            position_integrity="UNTRUSTED",
            trading_state="TRADING_READY",
        )
        c = and_(
            or_(
                condition("risk_health", "equals", "UNHEALTHY"),
                condition("position_integrity", "equals", "UNTRUSTED"),
            ),
            condition("trading_state", "equals", "TRADING_READY"),
        )
        assert c.evaluate(ctx) is True

    def test_nested_precedence_blocked_by_trading(self):
        ctx = _ctx(
            risk_health=ComponentState.UNHEALTHY,
            position_integrity="TRUSTED",
            trading_state="TRADING_HALTED",
        )
        c = and_(
            or_(
                condition("risk_health", "equals", "UNHEALTHY"),
                condition("position_integrity", "equals", "UNTRUSTED"),
            ),
            condition("trading_state", "equals", "TRADING_READY"),
        )
        assert c.evaluate(ctx) is False

    def test_not_negates(self):
        ctx = _ctx(risk_health=ComponentState.HEALTHY)
        c = not_(condition("risk_health", "equals", "UNHEALTHY"))
        assert c.evaluate(ctx) is True

    def test_evaluate_condition_leaf(self):
        ctx = _ctx(risk_health=ComponentState.UNHEALTHY)
        c = condition("risk_health", "equals", "UNHEALTHY")
        assert evaluate_condition(c, ctx) is True


class TestSerialization:
    def test_condition_round_trip(self):
        c = condition("risk_health", "equals", "UNHEALTHY")
        restored = PolicyCondition.from_dict(c.to_dict())
        assert restored == c

    def test_composite_round_trip(self):
        c = and_(
            or_(
                condition("risk_health", "equals", "UNHEALTHY"),
                condition("position_integrity", "equals", "UNTRUSTED"),
            ),
            condition("trading_state", "equals", "TRADING_READY"),
        )
        restored = CompositeCondition.from_dict(c.to_dict())
        ctx = _ctx(
            risk_health=ComponentState.HEALTHY,
            position_integrity="UNTRUSTED",
            trading_state="TRADING_READY",
        )
        assert restored.evaluate(ctx) is True
