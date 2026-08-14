"""Tests for the pre-trade risk checker and risk gate (Commit 37 Part 1.5).

Covers multi-rule aggregation through ``PreTradeRiskChecker`` and the gate
behaviour contract: ALLOW and REDUCE forward the order, REJECT and REVIEW
withhold it (order=None).
"""

from services.risk.application.pre_trade import (
    PreTradeRiskChecker,
    PreTradeRiskContext,
)
from services.risk.application.risk_gate import (
    RiskGate,
    RiskGateResult,
)
from services.risk.domain.decision import (
    RiskDecision,
    RiskDecisionStatus,
)


class _StaticRule:
    """Test rule that always returns a fixed decision."""

    def __init__(self, decision):
        self._decision = decision

    def evaluate(self, context):
        return self._decision


class _SizeRule:
    """Test rule that caps the accepted quantity at ``max_quantity``."""

    def __init__(self, max_quantity):
        self._max_quantity = max_quantity

    def evaluate(self, context):
        quantity = context.order.get("quantity", 0)
        if quantity <= self._max_quantity:
            return RiskDecision.allow(quantity=quantity)
        return RiskDecision.reduce(
            quantity=self._max_quantity,
            reason="max order size",
            rule="max_order_size",
        )


class _PortfolioBlockRule:
    """Test rule that rejects orders for a given portfolio."""

    def __init__(self, blocked_portfolio):
        self._blocked_portfolio = blocked_portfolio

    def evaluate(self, context):
        if context.portfolio == self._blocked_portfolio:
            return RiskDecision.reject(
                reason="portfolio under restriction",
                rule="portfolio_restriction",
            )
        return None


def test_checker_runs_all_rules_and_aggregates():
    checker = PreTradeRiskChecker(
        rules=[
            _StaticRule(RiskDecision.allow(quantity=100)),
            _SizeRule(max_quantity=50),
        ]
    )

    decision = checker.check(
        PreTradeRiskContext(
            order={"quantity": 100},
        )
    )

    assert decision.status == RiskDecisionStatus.REDUCE
    assert decision.accepted_quantity == 50
    assert "max_order_size" in decision.triggered_rules
    assert decision.metadata["decision_count"] == 2


def test_checker_skips_none_decisions():
    checker = PreTradeRiskChecker(
        rules=[
            _PortfolioBlockRule(blocked_portfolio="p-001"),
            _StaticRule(RiskDecision.allow(quantity=10)),
        ]
    )

    decision = checker.check(
        PreTradeRiskContext(
            order={"quantity": 10},
            portfolio="p-002",
        )
    )

    assert decision.allowed
    assert decision.metadata["decision_count"] == 1


def test_gate_allows_order_through():
    gate = RiskGate(
        PreTradeRiskChecker(
            rules=[
                _StaticRule(RiskDecision.allow(quantity=100)),
            ]
        )
    )

    order = {"order_id": "o-001", "quantity": 100}
    result = gate.evaluate(order)

    assert isinstance(result, RiskGateResult)
    assert result.decision.allowed
    assert result.order == order


def test_gate_reduce_forwards_order_with_adjusted_quantity():
    gate = RiskGate(
        PreTradeRiskChecker(
            rules=[
                _SizeRule(max_quantity=40),
            ]
        )
    )

    order = {"order_id": "o-002", "quantity": 100}
    result = gate.evaluate(order)

    assert result.decision.reduced
    assert result.decision.accepted_quantity == 40
    assert result.order == order


def test_gate_rejects_order():
    gate = RiskGate(
        PreTradeRiskChecker(
            rules=[
                _PortfolioBlockRule(blocked_portfolio="p-001"),
            ]
        )
    )

    order = {"order_id": "o-003", "quantity": 10}
    result = gate.evaluate(
        order,
        portfolio="p-001",
    )

    assert result.decision.rejected
    assert result.order is None


def test_gate_review_withholds_order():
    gate = RiskGate(
        PreTradeRiskChecker(
            rules=[
                _StaticRule(
                    RiskDecision.review(
                        reason="manual approval required",
                        rule="approval_required",
                    )
                ),
            ]
        )
    )

    order = {"order_id": "o-004", "quantity": 10}
    result = gate.evaluate(order)

    assert result.decision.requires_review
    assert result.order is None
