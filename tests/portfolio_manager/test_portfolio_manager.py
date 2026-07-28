"""Tests for AI Portfolio Manager Agent."""

import pytest
from services.portfolio_manager import (
    PortfolioState,
    PortfolioProposal,
    AllocationEngine,
    StrategySelector,
    Strategy,
    RebalanceEngine,
    RebalanceOrder,
    RebalanceResult,
    PerformanceAttribution,
    AttributionResult,
    InvestmentCommittee,
    CommitteeReview,
    CommitteeResult,
    PortfolioMemory,
    AllocationRecord,
    PortfolioManagerService,
)


# ====================================================================
# Portfolio State & Proposal
# ====================================================================

class TestPortfolioState:
    def test_create(self):
        ps = PortfolioState(
            portfolio_id="P1",
            objective="growth",
            risk_level="medium",
        )
        assert ps.portfolio_id == "P1"
        assert ps.objective == "growth"
        assert ps.risk_level == "medium"

    def test_total_exposure(self):
        ps = PortfolioState(
            portfolio_id="P1",
            objective="growth",
            risk_level="medium",
            cash=0.10,
        )
        assert abs(ps.total_exposure() - 0.9) < 1e-9

    def test_is_valid(self):
        ps = PortfolioState(
            portfolio_id="P1",
            objective="growth",
            risk_level="medium",
            holdings={"A": 0.2, "B": 0.2},
            max_single_position=0.3,
        )
        assert ps.is_valid() is True

    def test_is_valid_position_too_large(self):
        ps = PortfolioState(
            portfolio_id="P1",
            objective="growth",
            risk_level="medium",
            holdings={"A": 0.5},
            max_single_position=0.3,
        )
        assert ps.is_valid() is False

    def test_to_dict(self):
        ps = PortfolioState(
            portfolio_id="P1",
            objective="growth",
            risk_level="medium",
            holdings={"NVDA": 0.25},
            cash=0.1,
        )
        d = ps.to_dict()
        assert d["portfolio_id"] == "P1"
        assert d["holdings"]["NVDA"] == 0.25


class TestPortfolioProposal:
    def test_create(self):
        pp = PortfolioProposal(
            portfolio_id="P1",
            proposal_id="PROP-001",
            description="Rebalance NVDA",
        )
        assert pp.status == "draft"

    def test_to_dict(self):
        pp = PortfolioProposal(
            portfolio_id="P1",
            proposal_id="PROP-001",
            description="Test",
            proposed_weights={"A": 0.3},
            rationale="momentum signal",
        )
        d = pp.to_dict()
        assert d["portfolio_id"] == "P1"
        assert d["rationale"] == "momentum signal"


# ====================================================================
# Allocation Engine
# ====================================================================

class TestAllocationEngine:
    def test_allocate_equal(self):
        engine = AllocationEngine(max_single_position=1.0)
        result = engine.allocate(["NVDA", "MSFT"])
        assert abs(result["NVDA"] - 0.475) < 1e-9
        assert abs(result["MSFT"] - 0.475) < 1e-9

    def test_allocate_empty(self):
        engine = AllocationEngine()
        result = engine.allocate([])
        assert result == {}

    def test_allocate_cash_reserve(self):
        engine = AllocationEngine(max_single_position=1.0, cash_reserve=0.10)
        result = engine.allocate(["NVDA", "MSFT"])
        w_total = sum(result.values())
        assert abs(w_total - 0.9) < 1e-9

    def test_allocate_max_single_position(self):
        engine = AllocationEngine(max_single_position=0.3, cash_reserve=0.0)
        result = engine.allocate(["A", "B"])
        for w in result.values():
            assert w <= 0.3

    def test_allocate_alpha_weight(self):
        engine = AllocationEngine()
        result = engine.allocate(
            ["NVDA", "MSFT", "TSLA"],
            method="alpha",
            alpha_scores={"NVDA": 0.9, "MSFT": 0.5, "TSLA": 0.1},
        )
        assert result["NVDA"] > result["TSLA"]

    def test_allocate_alpha_zero_scores(self):
        engine = AllocationEngine(max_single_position=1.0)
        result = engine.allocate(
            ["A", "B"],
            method="alpha",
            alpha_scores={},
        )
        assert abs(result["A"] - 0.475) < 1e-9

    def test_allocate_risk_parity(self):
        engine = AllocationEngine()
        result = engine.allocate(
            ["A", "B"],
            method="risk_parity",
            risk_scores={"A": 0.8, "B": 0.2},
        )
        # B should get more weight (lower risk)
        assert result["B"] > result["A"]

    def test_optimize(self):
        engine = AllocationEngine(max_single_position=1.0)
        result = engine.optimize(
            assets=["NVDA", "TSLA"],
            alpha_scores={"NVDA": 0.9, "TSLA": 0.3},
            risk_scores={"NVDA": 0.3, "TSLA": 0.8},
            alpha_weight=0.5,
        )
        assert len(result) == 2
        # Total invested should be (1.0 - cash_reserve) since no capping
        assert abs(sum(result.values()) - (1.0 - engine.cash_reserve)) < 1e-9


# ====================================================================
# Strategy Selector
# ====================================================================

class TestStrategySelector:
    def test_select_basic(self):
        selector = StrategySelector()
        strategies = [
            Strategy(name="Momentum", category="momentum", sharpe=1.5, returns=0.2, max_drawdown=0.1, ic=0.3),
            Strategy(name="Value", category="value", sharpe=0.8, returns=0.12, max_drawdown=0.15, ic=0.2),
            Strategy(name="ML", category="ml", sharpe=2.0, returns=0.3, max_drawdown=0.08, ic=0.4),
        ]
        selected = selector.select(strategies)
        assert len(selected) >= 1

    def test_select_filters_by_sharpe(self):
        selector = StrategySelector(min_sharpe=1.0)
        strategies = [
            Strategy(name="Good", category="momentum", sharpe=1.5, max_drawdown=0.1),
            Strategy(name="Bad", category="value", sharpe=0.1, max_drawdown=0.1),
        ]
        selected = selector.select(strategies)
        names = [s.name for s in selected]
        assert "Good" in names
        assert "Bad" not in names

    def test_select_filters_by_drawdown(self):
        selector = StrategySelector(max_drawdown_limit=0.15)
        strategies = [
            Strategy(name="OK", category="momentum", sharpe=1.0, max_drawdown=0.1),
            Strategy(name="Bad", category="value", sharpe=1.0, max_drawdown=0.5),
        ]
        selected = selector.select(strategies)
        names = [s.name for s in selected]
        assert "OK" in names

    def test_select_inactive_filtered(self):
        selector = StrategySelector()
        strategies = [
            Strategy(name="Active", category="momentum", sharpe=1.0, active=True),
            Strategy(name="Inactive", category="value", sharpe=1.0, active=False),
        ]
        selected = selector.select(strategies)
        names = [s.name for s in selected]
        assert "Inactive" not in names

    def test_select_max_strategies(self):
        selector = StrategySelector(max_strategies=2)
        strategies = [
            Strategy(name=s, category=f"cat{i}", sharpe=1.0 + i * 0.1)
            for i, s in enumerate(["A", "B", "C", "D"])
        ]
        selected = selector.select(strategies)
        assert len(selected) <= 2

    def test_select_simple(self):
        selector = StrategySelector()
        result = selector.select_simple(["NVDA", "MSFT"])
        assert result == "NVDA"

    def test_select_simple_empty(self):
        selector = StrategySelector()
        assert selector.select_simple([]) == ""

    def test_allocate_capital(self):
        selector = StrategySelector()
        strategies = [
            Strategy(name="A", category="m", sharpe=2.0),
            Strategy(name="B", category="v", sharpe=1.0),
        ]
        alloc = selector.allocate_capital(strategies, 1000000)
        assert "A" in alloc
        assert "B" in alloc
        assert alloc["A"] > alloc["B"]

    def test_strategy_score(self):
        s = Strategy(name="S1", category="momentum", sharpe=1.5, returns=0.2, max_drawdown=0.1, ic=0.3, capacity=0.5)
        score = s.score()
        assert score > 0

    def test_strategy_to_dict(self):
        s = Strategy(name="S1", category="momentum")
        d = s.to_dict()
        assert d["name"] == "S1"


# ====================================================================
# Rebalance Engine
# ====================================================================

class TestRebalanceEngine:
    def test_rebalance_basic(self):
        engine = RebalanceEngine()
        current = {"NVDA": 0.3, "MSFT": 0.7}
        target = {"NVDA": 0.5, "MSFT": 0.5}
        result = engine.rebalance(current, target)
        assert result.status == "rebalanced"
        assert len(result.orders) == 2

    def test_rebalance_no_action(self):
        engine = RebalanceEngine(drift_threshold=0.03)
        current = {"A": 0.5, "B": 0.5}
        target = {"A": 0.505, "B": 0.495}
        result = engine.rebalance(current, target)
        assert result.status == "no_action"

    def test_rebalance_force(self):
        engine = RebalanceEngine(drift_threshold=0.05)
        current = {"A": 0.5, "B": 0.5}
        target = {"A": 0.51, "B": 0.49}
        result = engine.rebalance(current, target, force=True)
        trades = [o for o in result.orders if o.action != "hold"]
        assert len(trades) > 0

    def test_rebalance_new_symbol(self):
        engine = RebalanceEngine(turnover_limit=1.0)
        current = {"A": 1.0}
        target = {"A": 0.6, "B": 0.4}
        result = engine.rebalance(current, target)
        assert result.status == "rebalanced"
        buy_b = [o for o in result.orders if o.symbol == "B" and o.action == "buy"]
        assert len(buy_b) == 1

    def test_rebalance_turnover_limit(self):
        engine = RebalanceEngine(turnover_limit=0.05, drift_threshold=0.0)
        current = {"A": 0.9, "B": 0.1}
        target = {"A": 0.1, "B": 0.9}
        result = engine.rebalance(current, target)
        assert result.status == "skipped"

    def test_should_rebalance_drift(self):
        engine = RebalanceEngine(drift_threshold=0.03)
        current = {"A": 0.5}
        target = {"A": 0.6}
        assert engine.should_rebalance(current, target) is True

    def test_should_rebalance_no_drift(self):
        engine = RebalanceEngine(drift_threshold=0.10)
        current = {"A": 0.5}
        target = {"A": 0.52}
        assert engine.should_rebalance(current, target) is False

    def test_should_rebalance_triggers(self):
        engine = RebalanceEngine()
        assert engine.should_rebalance({"A": 0.5}, {"A": 0.5}, signal_change=True) is True
        assert engine.should_rebalance({"A": 0.5}, {"A": 0.5}, risk_increase=True) is True
        assert engine.should_rebalance({"A": 0.5}, {"A": 0.5}, regime_change=True) is True

    def test_rebalance_order_to_dict(self):
        o = RebalanceOrder(symbol="A", action="buy", current_weight=0.3, target_weight=0.5, delta=0.2)
        d = o.to_dict()
        assert d["action"] == "buy"

    def test_rebalance_result_to_dict(self):
        r = RebalanceResult(status="rebalanced", turnover=0.1, message="ok")
        d = r.to_dict()
        assert d["status"] == "rebalanced"


# ====================================================================
# Performance Attribution
# ====================================================================

class TestPerformanceAttribution:
    def test_analyze_basic(self):
        pa = PerformanceAttribution()
        result = pa.analyze(
            total_return=0.15,
            market_return=0.05,
            stock_contributions={"A": 0.06, "B": 0.02},
            factor_contributions={"momentum": 0.03},
            sector_contributions={"tech": 0.01},
        )
        assert abs(result.total_return - 0.15) < 1e-9
        assert abs(result.market_beta - 0.05) < 1e-9
        assert abs(result.stock_selection - 0.08) < 1e-9
        assert abs(result.factor_exposure - 0.03) < 1e-9

    def test_analyze_simple(self):
        pa = PerformanceAttribution()
        result = pa.analyze_simple(0.15)
        assert abs(result["total_return"] - 0.15) < 1e-9
        assert "market_beta" in result
        assert "stock_selection" in result

    def test_contribution_summary(self):
        pa = PerformanceAttribution()
        result = pa.analyze(
            total_return=0.15,
            market_return=0.02,
            stock_contributions={"A": 0.08},
            factor_contributions={"mom": 0.05},
        )
        summary = pa.contribution_summary(result)
        assert "Market Beta" in summary
        assert "Stock Selection" in summary

    def test_compare(self):
        pa = PerformanceAttribution()
        r1 = pa.analyze(total_return=0.15, period="Q1")
        r2 = pa.analyze(total_return=0.10, period="Q2")
        cmp = pa.compare(r1, r2)
        assert cmp["current_period"] == "Q1"
        assert abs(cmp["return_change"] - 0.05) < 1e-9

    def test_to_dict(self):
        ar = AttributionResult(
            period="Q1",
            total_return=0.15,
            stock_selection=0.08,
            market_beta=0.05,
        )
        d = ar.to_dict()
        assert d["period"] == "Q1"


# ====================================================================
# Investment Committee
# ====================================================================

class TestInvestmentCommittee:
    def test_approve_simple(self):
        committee = InvestmentCommittee()
        result = committee.approve(True)
        assert result["approved"] is True

    def test_approve_portfolio_proposal(self):
        committee = InvestmentCommittee(auto_approve_threshold=50)
        proposal = PortfolioProposal(
            portfolio_id="P1",
            proposal_id="P001",
            description="Rebalance",
            rationale="Strong momentum signal on NVDA",
            risk_score=30,
            expected_impact={"NVDA": 0.5},
        )
        result = committee.approve(proposal)
        assert result["approved"] is True

    def test_approve_high_risk_proposal(self):
        committee = InvestmentCommittee(auto_approve_threshold=70)
        proposal = PortfolioProposal(
            portfolio_id="P1",
            proposal_id="P002",
            description="Risky move",
            risk_score=90,
        )
        result = committee.approve(proposal)
        assert result["approved"] is False

    def test_approve_dict(self):
        committee = InvestmentCommittee(auto_approve_threshold=50)
        result = committee.approve({
            "portfolio_id": "P1",
            "description": "test",
            "rationale": "good reason",
        })
        assert "approved" in result

    def test_run_workflow(self):
        committee = InvestmentCommittee(auto_approve_threshold=50)
        proposal = PortfolioProposal(
            portfolio_id="P1",
            proposal_id="P003",
            description="Add NVDA",
            rationale="Strong alpha signal with positive momentum and volume confirmation",
            risk_score=20,
            expected_impact={"NVDA": 0.6},
        )
        result = committee.run_workflow(proposal)
        assert result.proposal_id == "P003"
        assert len(result.reviews) == 3
        assert result.approved is True

    def test_workflow_updates_proposal_status(self):
        committee = InvestmentCommittee(auto_approve_threshold=50)
        proposal = PortfolioProposal(
            portfolio_id="P1",
            proposal_id="P004",
            description="Test",
            rationale="Good signal with strong evidence",
            risk_score=10,
        )
        committee.run_workflow(proposal)
        assert proposal.status == "approved"

    def test_committee_review_to_dict(self):
        cr = CommitteeReview(step="research", reviewer="AI", decision="approved")
        d = cr.to_dict()
        assert d["step"] == "research"

    def test_committee_result_to_dict(self):
        cr = CommitteeResult(proposal_id="P1", approved=True, final_score=85)
        d = cr.to_dict()
        assert d["proposal_id"] == "P1"
        assert d["approved"] is True


# ====================================================================
# Portfolio Memory
# ====================================================================

class TestPortfolioMemory:
    def test_save_and_history(self):
        mem = PortfolioMemory()
        record = AllocationRecord(portfolio_id="P1", weights={"A": 0.5})
        mem.save(record)
        assert len(mem.history()) == 1

    def test_by_portfolio(self):
        mem = PortfolioMemory()
        mem.save(AllocationRecord(portfolio_id="P1"))
        mem.save(AllocationRecord(portfolio_id="P2"))
        assert len(mem.by_portfolio("P1")) == 1

    def test_by_regime(self):
        mem = PortfolioMemory()
        mem.save(AllocationRecord(portfolio_id="P1", market_regime="bull"))
        mem.save(AllocationRecord(portfolio_id="P2", market_regime="bear"))
        assert len(mem.by_regime("bull")) == 1

    def test_recent(self):
        mem = PortfolioMemory()
        for i in range(5):
            mem.save(AllocationRecord(portfolio_id=f"P{i}"))
        assert len(mem.recent(3)) == 3

    def test_performance_summary(self):
        mem = PortfolioMemory()
        mem.save(AllocationRecord(portfolio_id="P1", returns_since=0.05))
        mem.save(AllocationRecord(portfolio_id="P2", returns_since=0.10))
        summary = mem.performance_summary()
        assert summary["total_records"] == 2
        assert summary["avg_return"] > 0

    def test_performance_summary_empty(self):
        mem = PortfolioMemory()
        summary = mem.performance_summary()
        assert summary["total_records"] == 0

    def test_clear(self):
        mem = PortfolioMemory()
        mem.save(AllocationRecord(portfolio_id="P1"))
        mem.clear()
        assert len(mem.history()) == 0

    def test_to_dict(self):
        record = AllocationRecord(
            portfolio_id="P1",
            weights={"A": 0.5},
            decision_reason="momentum",
            market_regime="bull",
        )
        d = record.to_dict()
        assert d["portfolio_id"] == "P1"
        assert d["weights"]["A"] == 0.5


# ====================================================================
# Portfolio Manager Service
# ====================================================================

class TestPortfolioManagerService:
    def test_build_portfolio(self):
        service = PortfolioManagerService()
        weights = service.build_portfolio(
            portfolio_id="P1",
            assets=["NVDA", "MSFT"],
            objective="growth",
        )
        assert "NVDA" in weights
        assert "MSFT" in weights

    def test_allocate_delegation(self):
        service = PortfolioManagerService()
        result = service.allocate(["NVDA", "MSFT"], method="equal")
        assert len(result) == 2

    def test_optimize_allocation(self):
        service = PortfolioManagerService()
        result = service.optimize_allocation(
            assets=["NVDA", "TSLA"],
            alpha_scores={"NVDA": 0.9, "TSLA": 0.3},
            risk_scores={"NVDA": 0.3, "TSLA": 0.8},
        )
        assert len(result) == 2
        assert result["NVDA"] > result["TSLA"]

    def test_select_strategies(self):
        service = PortfolioManagerService()
        strategies = [
            Strategy(name="M1", category="momentum", sharpe=1.5, max_drawdown=0.1),
            Strategy(name="V1", category="value", sharpe=0.8, max_drawdown=0.15),
        ]
        selected = service.select_strategies(strategies)
        assert len(selected) >= 1

    def test_allocate_strategy_capital(self):
        service = PortfolioManagerService()
        strategies = [
            Strategy(name="A", category="m", sharpe=2.0),
            Strategy(name="B", category="v", sharpe=1.0),
        ]
        alloc = service.allocate_strategy_capital(strategies, 1000000)
        assert alloc["A"] > alloc["B"]

    def test_rebalance(self):
        service = PortfolioManagerService()
        result = service.rebalance(
            current_weights={"A": 0.3, "B": 0.7},
            target_weights={"A": 0.5, "B": 0.5},
        )
        assert result.status == "rebalanced"

    def test_should_rebalance(self):
        service = PortfolioManagerService()
        assert service.should_rebalance(
            {"A": 0.5}, {"A": 0.5}, signal_change=True,
        ) is True

    def test_attribute_performance(self):
        service = PortfolioManagerService()
        result = service.attribute_performance(
            total_return=0.15,
            market_return=0.05,
            stock_contributions={"A": 0.08},
            factor_contributions={"mom": 0.02},
        )
        assert abs(result.total_return - 0.15) < 1e-9

    def test_submit_proposal(self):
        service = PortfolioManagerService()
        result = service.submit_proposal(
            portfolio_id="P1",
            description="Rebalance NVDA",
            current_weights={"NVDA": 0.3},
            proposed_weights={"NVDA": 0.25},
            rationale="Good momentum signal with volume confirmation",
            risk_score=20,
        )
        assert result.approved is True

    def test_approve_proposal_legacy(self):
        service = PortfolioManagerService()
        result = service.approve_proposal({"description": "test"})
        assert "approved" in result

    def test_record_allocation(self):
        service = PortfolioManagerService()
        record = service.record_allocation(
            portfolio_id="P1",
            weights={"A": 0.5},
            decision_reason="momentum signal",
        )
        assert record.portfolio_id == "P1"
        assert len(service.memory_history()) == 1

    def test_memory_summary(self):
        service = PortfolioManagerService()
        service.record_allocation("P1", {"A": 0.5}, returns_since=0.05)
        summary = service.memory_summary()
        assert summary["total_records"] == 1
