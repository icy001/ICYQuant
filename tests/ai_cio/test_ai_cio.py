"""Tests for AI Chief Investment Officer Engine."""

import pytest

from services.ai_cio import (
    AICIOService,
    AssetAllocationEngine,
    CapitalDeploymentEngine,
    CIOMemory,
    CIORiskCommittee,
    CIOStrategyPlanner,
    GlobalMarketAssessment,
    OpportunityRankingEngine,
    PortfolioConstructionEngine,
    RiskBudgetEngine,
)


def test_allocation():
    engine = AssetAllocationEngine()
    result = engine.allocate(["stock", "bond"])
    assert len(result) == 2


def test_allocation_equal_weight():
    engine = AssetAllocationEngine()
    result = engine.allocate(["stock", "bond", "commodity"])
    assert result["stock"] == 1 / 3
    assert result["bond"] == 1 / 3
    assert result["commodity"] == 1 / 3


def test_cio_strategy_planner():
    planner = CIOStrategyPlanner()
    result = planner.create_strategy("growth", "moderate")
    assert result["objective"] == "growth"
    assert result["risk"] == "moderate"


def test_global_market_assessment():
    assessment = GlobalMarketAssessment()
    result = assessment.analyze({"macro": "expansion"})
    assert result["regime"] == "growth"


def test_risk_budget_engine():
    engine = RiskBudgetEngine()
    result = engine.calculate({"stock": 0.6, "bond": 0.4})
    assert result["risk_limit"] == 0.2


def test_opportunity_ranking_engine():
    engine = OpportunityRankingEngine()
    result = engine.rank(["robotics", "ai_semiconductor", "cloud"])
    assert result == ["ai_semiconductor", "cloud", "robotics"]


def test_portfolio_construction_engine():
    engine = PortfolioConstructionEngine()
    allocation = {"stock": 0.6, "bond": 0.4}
    result = engine.construct(allocation)
    assert result == allocation


def test_capital_deployment_engine():
    engine = CapitalDeploymentEngine()
    result = engine.deploy({"stock": 0.6, "bond": 0.4})
    assert result["status"] == "approved"


def test_cio_risk_committee():
    committee = CIORiskCommittee()
    result = committee.review({"stock": 0.6, "bond": 0.4})
    assert result["approved"] is True


def test_cio_memory():
    memory = CIOMemory()
    memory.save({"date": "2025-06", "allocation": {"stock": 0.6}})
    memory.save({"date": "2025-07", "allocation": {"stock": 0.5}})
    assert len(memory.history) == 2
    assert memory.history[0]["allocation"]["stock"] == 0.6


def test_ai_cio_service():
    allocator = AssetAllocationEngine()
    service = AICIOService(allocator)
    result = service.allocate(["stock", "bond", "commodity"])
    assert len(result) == 3
    assert sum(result.values()) == pytest.approx(1.0)


def test_full_cio_workflow():
    """End-to-end: strategy → assessment → allocation → deployment → memory."""
    # 1. Define CIO strategy
    planner = CIOStrategyPlanner()
    strategy = planner.create_strategy("growth", "moderate")
    assert strategy["objective"] == "growth"

    # 2. Assess global market
    assessment = GlobalMarketAssessment()
    regime = assessment.analyze({"macro": "expansion"})
    assert regime["regime"] == "growth"

    # 3. Allocate assets
    allocator = AssetAllocationEngine()
    allocation = allocator.allocate(["equity", "bond", "cash"])
    assert len(allocation) == 3

    # 4. Calculate risk budget
    risk = RiskBudgetEngine()
    budget = risk.calculate(allocation)
    assert budget["risk_limit"] == 0.2

    # 5. Construct portfolio
    portfolio = PortfolioConstructionEngine()
    constructed = portfolio.construct(allocation)
    assert constructed == allocation

    # 6. CIO risk committee review
    committee = CIORiskCommittee()
    review = committee.review(constructed)
    assert review["approved"] is True

    # 7. Deploy capital
    deployment = CapitalDeploymentEngine()
    deploy_result = deployment.deploy(constructed)
    assert deploy_result["status"] == "approved"

    # 8. Save to CIO memory
    memory = CIOMemory()
    memory.save({"strategy": strategy, "allocation": allocation, "status": "deployed"})
    assert len(memory.history) == 1
