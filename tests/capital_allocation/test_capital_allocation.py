from services.capital_allocation import *


# ========== 1. Capital Deployment Agent ==========

def test_capital_deployment():
    agent = CapitalDeploymentAgent()
    result = agent.deploy("NVDA")
    assert result["capital_plan"] == "NVDA"


def test_deployment_with_decision():
    agent = CapitalDeploymentAgent()
    data = {
        "decision": {
            "symbol": "NVDA",
            "decision": "STRONG_BUY",
            "conviction_score": 88.0,
            "position_size_pct": 0.08,
            "risk_controls": ["Hard stop-loss at 5%", "Scale in over 3 tranches"],
        },
    }
    result = agent.deploy(data)
    plan = result["capital_plan"]
    assert plan["symbol"] == "NVDA"
    assert plan["total_allocation"] > 0
    assert len(plan["phases"]) == 3
    assert plan["method"] in ("STAGED", "VWAP", "TWAP", "ADAPTIVE", "SINGLE")


def test_deployment_with_capital_plan():
    agent = CapitalDeploymentAgent()
    plan = CapitalPlan(
        plan_id="CAP_0001",
        symbol="AAPL",
        total_allocation=0.05,
        current_deployed=0.0,
        remaining=0.05,
        method=DeploymentMethod.VWAP,
        urgency=DeploymentUrgency.WITHIN_DAY,
    )
    result = agent.deploy(plan)
    assert result["capital_plan"]["plan_id"] == "CAP_0001"


def test_deployment_sell_reject():
    agent = CapitalDeploymentAgent()
    for decision_type in ("SELL", "REJECT"):
        result = agent.deploy({
            "decision": {"symbol": "BAD", "decision": decision_type, "conviction_score": 15}
        })
        assert result["capital_plan"]["total_allocation"] == 0.0


# ========== 2. Capital Allocation Optimizer ==========

def test_allocation_optimizer():
    optimizer = CapitalAllocationOptimizer()
    result = optimizer.optimize("portfolio")
    assert result["allocation"] == "portfolio"


def test_optimizer_with_positions():
    optimizer = CapitalAllocationOptimizer()
    data = {
        "positions": [
            {"symbol": "NVDA", "weight": 0.40, "conviction": 85, "risk": 0.20, "expected_return": 0.25},
            {"symbol": "AAPL", "weight": 0.30, "conviction": 65, "risk": 0.12, "expected_return": 0.12},
            {"symbol": "MSFT", "weight": 0.20, "conviction": 70, "risk": 0.15, "expected_return": 0.15},
            {"symbol": "CASH", "weight": 0.10, "conviction": 50, "risk": 0.01, "expected_return": 0.03},
        ],
        "total_capital": 1000000.0,
        "objective": "MAX_SHARPE",
    }
    result = optimizer.optimize(data)
    alloc = result["allocation"]
    assert len(alloc["weights"]) == 4
    assert alloc["objective"] == "MAX_SHARPE"
    assert alloc["cash_reserve"] > 0
    assert alloc["expected_risk"] > 0


def test_optimizer_max_return():
    optimizer = CapitalAllocationOptimizer()
    data = {
        "positions": [
            {"symbol": "NVDA", "weight": 0.50, "conviction": 90, "expected_return": 0.30},
            {"symbol": "BOND", "weight": 0.50, "conviction": 40, "expected_return": 0.05},
        ],
        "total_capital": 500000.0,
        "objective": "MAX_RETURN",
    }
    result = optimizer.optimize(data)
    assert result["allocation"]["objective"] == "MAX_RETURN"


# ========== 3. Opportunity Ranking Engine ==========

def test_opportunity_ranking():
    engine = OpportunityRankingEngine()
    result = engine.rank("NVDA")
    assert result["ranking"] == "NVDA"


def test_ranking_with_list():
    engine = OpportunityRankingEngine()
    opportunities = [
        {"symbol": "NVDA", "alpha_potential": 85, "risk_reward": 80, "conviction": 88, "liquidity": 90},
        {"symbol": "AAPL", "alpha_potential": 70, "risk_reward": 75, "conviction": 72, "liquidity": 95},
        {"symbol": "TSLA", "alpha_potential": 60, "risk_reward": 45, "conviction": 55, "liquidity": 80},
        {"symbol": "PENNY", "alpha_potential": 30, "risk_reward": 20, "conviction": 25, "liquidity": 15},
    ]
    result = engine.rank(opportunities)
    ranking = result["ranking"]
    assert len(ranking["opportunities"]) == 4
    # First should be highest composite
    assert ranking["opportunities"][0]["rank"] == "TIER_1"
    assert ranking["opportunities"][-1]["rank"] == "REJECT"
    assert ranking["actionable_count"] > 0


def test_ranking_get_top():
    engine = OpportunityRankingEngine()
    engine.rank([
        {"symbol": "A", "alpha_potential": 90},
        {"symbol": "B", "alpha_potential": 80},
        {"symbol": "C", "alpha_potential": 70},
        {"symbol": "D", "alpha_potential": 60},
    ])
    top = engine.get_top_opportunities(2)
    assert len(top) == 2
    assert top[0].symbol == "A"


# ========== 4. Capital Rotation Engine ==========

def test_capital_rotation():
    engine = CapitalRotationEngine()
    result = engine.rotate("portfolio")
    assert result["rotation"] == "portfolio"


def test_rotation_with_positions():
    engine = CapitalRotationEngine()
    positions = [
        {"symbol": "NVDA", "current_weight": 0.40, "target_weight": 0.45, "momentum": 0.15, "thesis_strength": 0.8},
        {"symbol": "INTC", "current_weight": 0.15, "target_weight": 0.10, "momentum": -0.10, "thesis_strength": 0.3},
    ]
    result = engine.rotate(positions)
    rotation = result["rotation"]
    assert len(rotation["moves"]) == 2
    assert rotation["total_turnover"] > 0
    assert rotation["capital_freed"] > 0
    assert rotation["capital_required"] > 0


def test_rotation_no_change():
    engine = CapitalRotationEngine()
    positions = [
        {"symbol": "NVDA", "current_weight": 0.40, "target_weight": 0.40, "momentum": 0.05, "thesis_strength": 0.6},
    ]
    result = engine.rotate(positions)
    assert len(result["rotation"]["moves"]) == 0


# ========== 5. Dynamic Exposure Control ==========

def test_exposure_control():
    engine = DynamicExposureControl()
    result = engine.adjust(0.6)
    assert result["exposure"] == 0.6


def test_exposure_bull_market():
    engine = DynamicExposureControl()
    result = engine.adjust({
        "current_exposure": 0.60,
        "market_regime": "BULL",
        "volatility": 0.12,
        "risk_level": "LOW",
        "conviction": 80,
        "liquidity": "NORMAL",
    })
    exp = result["exposure"]
    assert exp["target_exposure"] > exp["current_exposure"]


def test_exposure_crisis_market():
    engine = DynamicExposureControl()
    result = engine.adjust({
        "current_exposure": 0.60,
        "market_regime": "CRISIS",
        "volatility": 0.35,
        "risk_level": "HIGH",
        "conviction": 30,
        "liquidity": "LOW",
    })
    exp = result["exposure"]
    assert exp["target_exposure"] < exp["current_exposure"]
    assert exp["level"] in ("DEFENSIVE", "LIQUIDATION")


# ========== 6. Cash Management AI ==========

def test_cash_management():
    engine = CashManagementAI()
    result = engine.manage(100000)
    assert result["cash"] == 100000


def test_cash_with_data():
    engine = CashManagementAI()
    result = engine.manage({
        "total_cash": 200000.0,
        "total_aum": 1000000.0,
        "market_regime": "NORMAL",
        "volatility": 0.15,
        "conviction": 65,
    })
    cash = result["cash"]
    assert cash["total_cash"] == 200000.0
    assert cash["cash_ratio"] == 0.2
    assert len(cash["reserves"]) == 4
    assert cash["deployable"] > 0


def test_cash_crisis_regime():
    engine = CashManagementAI()
    result = engine.manage({
        "total_cash": 200000.0,
        "total_aum": 1000000.0,
        "market_regime": "CRISIS",
        "volatility": 0.35,
        "conviction": 30,
    })
    cash = result["cash"]
    # Crisis should increase emergency reserve
    emergency = next(r for r in cash["reserves"] if r["tier"] == "EMERGENCY")
    assert emergency["percentage"] > 3.0


# ========== 7. Liquidity Optimization Engine ==========

def test_liquidity_engine():
    engine = LiquidityOptimizationEngine()
    result = engine.analyze("market")
    assert result["liquidity"] == "market"


def test_liquidity_with_positions():
    engine = LiquidityOptimizationEngine()
    positions = [
        {"symbol": "NVDA", "avg_daily_volume": 50000000.0, "bid_ask_spread": 0.001, "market_depth": 5000000.0},
        {"symbol": "SMALL", "avg_daily_volume": 50000.0, "bid_ask_spread": 0.025, "market_depth": 5000.0},
    ]
    result = engine.analyze(positions)
    liq = result["liquidity"]
    assert len(liq["profiles"]) == 2
    assert liq["profiles"][0]["level"] == "HIGH"
    assert liq["profiles"][1]["level"] in ("LOW", "ILLIQUID")
    assert liq["portfolio_liquidity_score"] > 0
    assert len(liq["recommendations"]) > 0


# ========== 8. Capital Efficiency Analyzer ==========

def test_efficiency_analyzer():
    engine = CapitalEfficiencyAnalyzer()
    result = engine.analyze("capital")
    assert result["efficiency"] == "capital"


def test_efficiency_with_data():
    engine = CapitalEfficiencyAnalyzer()
    result = engine.analyze({
        "total_capital": 1000000.0,
        "deployed_capital": 850000.0,
        "return_on_capital": 0.15,
        "risk": 0.12,
        "turnover_ratio": 0.8,
    })
    eff = result["efficiency"]
    assert eff["total_capital"] == 1000000.0
    assert eff["metrics"]["capital_utilization"] == 0.85
    assert eff["metrics"]["return_on_capital"] == 0.15
    assert eff["rating"] in ("EXCELLENT", "GOOD", "ADEQUATE", "POOR", "INEFFICIENT")


def test_efficiency_low_utilization():
    engine = CapitalEfficiencyAnalyzer()
    result = engine.analyze({
        "total_capital": 1000000.0,
        "deployed_capital": 400000.0,
        "return_on_capital": 0.03,
        "risk": 0.05,
    })
    eff = result["efficiency"]
    assert eff["metrics"]["capital_utilization"] == 0.4
    # Low utilization should trigger recommendations
    assert len(eff["recommendations"]) > 0


# ========== 9. Capital Stress Tester ==========

def test_stress_tester():
    engine = CapitalStressTester()
    result = engine.simulate("crash")
    assert result["scenario"] == "crash"


def test_stress_with_data():
    engine = CapitalStressTester()
    result = engine.simulate({
        "total_capital": 1000000.0,
        "current_exposure": 0.60,
        "leverage": 1.0,
        "cash_ratio": 0.10,
        "concentration": 0.30,
    })
    report = result["scenario"]
    assert len(report["results"]) == 5  # 5 scenarios
    assert 0 <= report["worst_case_loss"] <= 1.0
    assert 0 <= report["survival_score"] <= 100
    assert len(report["critical_vulnerabilities"]) >= 0
    assert "summary" in report


def test_stress_high_leverage():
    engine = CapitalStressTester()
    result = engine.simulate({
        "total_capital": 1000000.0,
        "current_exposure": 0.80,
        "leverage": 2.0,
        "cash_ratio": 0.03,
        "concentration": 0.50,
    })
    report = result["scenario"]
    # High leverage should produce critical vulnerabilities
    assert report["survival_score"] < 50
    assert len(report["critical_vulnerabilities"]) > 0


# ========== 10. Capital Memory ==========

def test_capital_memory():
    memory = CapitalMemory()
    assert memory.history == []
    memory.save({"allocation": "NVDA 40%", "result": "profitable"})
    memory.save({"allocation": "TSLA 20%", "result": "loss"})
    assert len(memory.history) == 2
    assert memory.history[0]["allocation"] == "NVDA 40%"


def test_memory_with_entry():
    memory = CapitalMemory()
    entry = CapitalMemoryEntry(
        entry_id="M001",
        symbol="NVDA",
        event=CapitalEvent.DEPLOYMENT,
        amount=400000.0,
        allocation_before=0.0,
        allocation_after=0.40,
        outcome=CapitalOutcome.SUCCESS,
        result="Deployed at optimal entry, stock up 25%",
        lesson="Staged deployment at high conviction works well",
        return_impact=0.10,
    )
    memory.save(entry)
    assert len(memory.history) == 1
    assert len(memory.lessons) == 1
    assert memory.get_success_rate() == 1.0
    assert memory.get_total_capital_deployed() == 400000.0


def test_memory_patterns():
    memory = CapitalMemory()
    for i in range(5):
        entry = CapitalMemoryEntry(
            entry_id=f"M{i:03d}",
            symbol=f"ASSET_{i}",
            event=CapitalEvent.DEPLOYMENT,
            amount=100000.0 * (i + 1),
            allocation_before=0.0,
            allocation_after=0.10 * (i + 1),
            outcome=CapitalOutcome.SUCCESS if i < 4 else CapitalOutcome.FAILURE,
            result=f"Result {i}",
            lesson=f"Lesson {i}",
            return_impact=0.05 * (i + 1) if i < 4 else -0.03,
        )
        memory.save(entry)

    assert len(memory.history) == 5
    assert memory.get_success_rate() == 0.8

    patterns = memory.get_best_patterns(min_samples=3)
    assert len(patterns) > 0


# ========== 11. Capital Allocation Service ==========

def test_capital_allocation_service():
    agent = CapitalDeploymentAgent()
    service = CapitalAllocationService(agent=agent)
    result = service.allocate("NVDA")
    assert result["capital_plan"] == "NVDA"


def test_service_with_decision():
    agent = CapitalDeploymentAgent()
    service = CapitalAllocationService(agent=agent)
    result = service.allocate({
        "decision": {"symbol": "NVDA", "decision": "BUY", "conviction_score": 75, "position_size_pct": 0.05},
    })
    assert result["capital_plan"]["symbol"] == "NVDA"


# ========== 12. Full Workflow ==========

def test_full_capital_allocation_workflow():
    """End-to-end autonomous capital allocation workflow."""

    # 1. Capital Deployment
    agent = CapitalDeploymentAgent()
    capital_plan = agent.deploy({
        "decision": {
            "symbol": "NVDA",
            "decision": "STRONG_BUY",
            "conviction_score": 88.0,
            "position_size_pct": 0.08,
            "risk_controls": ["Hard stop-loss at 5%", "Scale in over 3 tranches"],
        },
    })
    assert capital_plan["capital_plan"]["symbol"] == "NVDA"
    assert len(capital_plan["capital_plan"]["phases"]) == 3

    # 2. Allocation Optimization
    optimizer = CapitalAllocationOptimizer()
    allocation = optimizer.optimize({
        "positions": [
            {"symbol": "NVDA", "weight": 0.40, "conviction": 88, "risk": 0.20, "expected_return": 0.25},
            {"symbol": "AAPL", "weight": 0.30, "conviction": 72, "risk": 0.12, "expected_return": 0.12},
            {"symbol": "MSFT", "weight": 0.20, "conviction": 70, "risk": 0.15, "expected_return": 0.15},
            {"symbol": "CASH", "weight": 0.10, "conviction": 50, "risk": 0.01, "expected_return": 0.03},
        ],
        "total_capital": 1000000.0,
        "objective": "MAX_SHARPE",
    })
    assert len(allocation["allocation"]["weights"]) == 4
    assert allocation["allocation"]["sharpe_ratio"] > 0

    # 3. Opportunity Ranking
    ranking_engine = OpportunityRankingEngine()
    ranking = ranking_engine.rank([
        {"symbol": "NVDA", "alpha_potential": 88, "risk_reward": 85, "conviction": 88, "liquidity": 90},
        {"symbol": "AAPL", "alpha_potential": 75, "risk_reward": 78, "conviction": 72, "liquidity": 95},
        {"symbol": "PENNY", "alpha_potential": 25, "risk_reward": 15, "conviction": 20, "liquidity": 10},
    ])
    assert ranking["ranking"]["actionable_count"] == 2

    # 4. Capital Rotation
    rotation_engine = CapitalRotationEngine()
    rotation = rotation_engine.rotate([
        {"symbol": "NVDA", "current_weight": 0.35, "target_weight": 0.40, "momentum": 0.12},
        {"symbol": "INTC", "current_weight": 0.10, "target_weight": 0.05, "momentum": -0.15},
    ])
    assert rotation["rotation"]["total_turnover"] > 0

    # 5. Exposure Control
    exposure_control = DynamicExposureControl()
    exposure = exposure_control.adjust({
        "current_exposure": 0.60,
        "market_regime": "BULL",
        "volatility": 0.12,
        "risk_level": "LOW",
        "conviction": 80,
    })
    assert exposure["exposure"]["target_exposure"] > 0.60

    # 6. Cash Management
    cash_mgr = CashManagementAI()
    cash = cash_mgr.manage({
        "total_cash": 200000.0,
        "total_aum": 1000000.0,
        "market_regime": "NORMAL",
    })
    assert cash["cash"]["deployable"] > 0

    # 7. Liquidity Analysis
    liquidity_engine = LiquidityOptimizationEngine()
    liquidity = liquidity_engine.analyze([
        {"symbol": "NVDA", "avg_daily_volume": 50000000.0, "bid_ask_spread": 0.001},
    ])
    assert liquidity["liquidity"]["portfolio_liquidity_score"] > 0

    # 8. Efficiency Analysis
    efficiency_engine = CapitalEfficiencyAnalyzer()
    efficiency = efficiency_engine.analyze({
        "total_capital": 1000000.0,
        "deployed_capital": 850000.0,
        "return_on_capital": 0.15,
    })
    assert efficiency["efficiency"]["rating"] in ("EXCELLENT", "GOOD", "ADEQUATE")

    # 9. Stress Testing
    stress_tester = CapitalStressTester()
    stress = stress_tester.simulate({
        "total_capital": 1000000.0,
        "current_exposure": 0.60,
        "leverage": 1.0,
        "cash_ratio": 0.10,
        "concentration": 0.30,
    })
    assert len(stress["scenario"]["results"]) == 5

    # 10. Memory
    memory = CapitalMemory()
    memory.save(CapitalMemoryEntry(
        entry_id="M001", symbol="NVDA",
        event=CapitalEvent.DEPLOYMENT, amount=400000.0,
        allocation_before=0.0, allocation_after=0.40,
        outcome=CapitalOutcome.SUCCESS,
        result="Capital deployed successfully",
        lesson="Staged deployment works",
        return_impact=0.10,
    ))
    assert len(memory.history) == 1

    # 11. Service orchestrator
    service = CapitalAllocationService(agent=agent)
    result = service.allocate({
        "decision": {"symbol": "NVDA", "decision": "BUY", "conviction_score": 75}
    })
    assert result is not None
