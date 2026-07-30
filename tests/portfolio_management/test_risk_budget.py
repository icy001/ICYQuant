"""Tests for Risk Budget Manager."""

import pytest
from services.portfolio_management.risk_budget import (
    RiskBudgetManager, RiskBudget, RiskBudgetType, RiskLimit, LimitStatus,
    RiskBucket, BudgetUtilization,
)


class TestRiskBudgetManager:
    """Test risk budget management."""

    @pytest.fixture
    def manager(self):
        return RiskBudgetManager()

    def test_create_budget(self, manager):
        budget = manager.create_budget("port-1", "Main Risk Budget", 0.15)
        assert budget.portfolio_id == "port-1"
        assert budget.total_risk_budget == 0.15
        assert budget.name == "Main Risk Budget"

    def test_add_bucket_with_defaults(self, manager):
        budget = manager.create_budget("port-1", "Main Budget", 0.15)
        bucket = manager.add_bucket(budget.budget_id, "Equity Bucket", "strat-1", 0.10)
        assert bucket is not None
        assert bucket.total_budget == 0.10

        manager.add_default_limits(bucket)
        assert len(bucket.limits) >= 5

    def test_limit_status(self):
        limit = RiskLimit(
            name="Max Drawdown",
            budget_type=RiskBudgetType.DRAWDOWN,
            hard_limit=20.0,
            soft_limit=15.0,
            current_value=5.0,
        )
        assert limit.status == LimitStatus.OK

        limit.current_value = 17.0
        assert limit.status == LimitStatus.WARNING

        limit.current_value = 22.0
        assert limit.status == LimitStatus.BREACHED

        limit.current_value = 30.0
        assert limit.status == LimitStatus.CRITICAL

    def test_utilization_pct(self):
        limit = RiskLimit(
            name="VaR",
            budget_type=RiskBudgetType.VAR,
            hard_limit=2.0,
            current_value=1.5,
        )
        assert limit.utilization_pct == 75.0
        assert limit.headroom == 0.5

    def test_check_portfolio_risk(self, manager):
        budget = manager.create_budget("port-1", "Main", 0.15)
        bucket = manager.add_bucket(budget.budget_id, "Equity", "strat-1", 0.10)
        manager.add_default_limits(bucket)

        # All OK — values within limits (limits are in % units)
        metrics = {
            "volatility": 15.0,
            "var_95": 0.5,
            "max_drawdown": 10.0,
            "leverage": 1.2,
            "tracking_error": 2.0,
        }
        results = manager.check_portfolio_risk("port-1", metrics)
        breaches = results.get("breaches", [])
        assert len(breaches) == 0

        # Breach: high volatility (30% > 25% hard limit)
        metrics["volatility"] = 30.0
        results = manager.check_portfolio_risk("port-1", metrics)
        breaches = results.get("breaches", [])
        assert len(breaches) > 0

    def test_get_buckets_for_portfolio(self, manager):
        budget = manager.create_budget("port-1", "Main", 0.15)
        manager.add_bucket(budget.budget_id, "Equity", "strat-1", 0.08)
        manager.add_bucket(budget.budget_id, "CTA", "strat-2", 0.07)

        budgets = manager.get_budgets_for_portfolio("port-1")
        assert len(budgets) == 1
        assert len(budgets[0].buckets) == 2

    def test_get_summary(self, manager):
        budget = manager.create_budget("port-1", "Main", 0.15)
        bucket = manager.add_bucket(budget.budget_id, "Equity", "strat-1", 0.10)
        manager.add_default_limits(bucket)

        summary = manager.get_summary()
        assert summary["total_budgets"] == 1
        assert summary["total_limits"] > 0

    def test_bucket_breaches_and_warnings(self):
        bucket = RiskBucket(name="Test", owner_id="p1")
        bucket.limits = [
            RiskLimit(name="OK Limit", budget_type=RiskBudgetType.VOLATILITY, hard_limit=20, current_value=5),
            RiskLimit(name="Warning Limit", budget_type=RiskBudgetType.VAR, hard_limit=2, current_value=1.8),
            RiskLimit(name="Breached Limit", budget_type=RiskBudgetType.DRAWDOWN, hard_limit=20, current_value=22),
        ]

        breaches = bucket.get_breaches()
        assert len(breaches) == 1
        assert breaches[0].name == "Breached Limit"

        warnings = bucket.get_warnings()
        assert len(warnings) == 1
        assert warnings[0].name == "Warning Limit"

        all_status = bucket.check_all()
        assert all_status["OK Limit"] == LimitStatus.OK
        assert all_status["Warning Limit"] == LimitStatus.WARNING
        assert all_status["Breached Limit"] == LimitStatus.BREACHED
