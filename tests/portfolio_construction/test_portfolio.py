from services.portfolio_construction import *


def test_portfolio_allocation():
    agent = AssetAllocationAgent()
    result = agent.allocate("equity")
    assert result["allocation"] == "equity"


def test_asset_allocation():
    agent = AssetAllocationAgent()
    result = agent.allocate({"equity": 0.60, "bond": 0.20, "cash": 0.10, "alternative": 0.10})
    assert result == {"allocation": {"equity": 0.60, "bond": 0.20, "cash": 0.10, "alternative": 0.10}}


def test_strategy_allocation():
    engine = StrategyAllocationEngine()
    result = engine.allocate({"momentum": 0.40, "value": 0.30, "arbitrage": 0.30})
    assert result == {"weights": {"momentum": 0.40, "value": 0.30, "arbitrage": 0.30}}


def test_risk_budget():
    engine = RiskBudgetEngine()
    result = engine.calculate({"volatility_budget": 0.15, "var_limit": 0.02})
    assert result == {"risk_budget": {"volatility_budget": 0.15, "var_limit": 0.02}}


def test_position_sizing():
    ai = PositionSizingAI()
    result = ai.size({"signal": 0.8, "confidence": 0.9})
    assert result == {"position": {"signal": 0.8, "confidence": 0.9}}


def test_portfolio_optimization():
    engine = PortfolioOptimizationEngine()
    result = engine.optimize({"weights": [0.4, 0.3, 0.3], "sharpe": 1.5})
    assert result == {"optimized": {"weights": [0.4, 0.3, 0.3], "sharpe": 1.5}}


def test_exposure_management():
    engine = ExposureManagementEngine()
    result = engine.check({"tech": 0.35, "finance": 0.25, "health": 0.15})
    assert result == {"exposure": {"tech": 0.35, "finance": 0.25, "health": 0.15}}


def test_portfolio_rebalance():
    engine = PortfolioRebalanceEngine()
    result = engine.rebalance({"before": {"AAPL": 0.12}, "after": {"AAPL": 0.10}})
    assert result == {"portfolio": {"before": {"AAPL": 0.12}, "after": {"AAPL": 0.10}}}


def test_portfolio_stress():
    tester = PortfolioStressTester()
    result = tester.simulate("market_crash_2008")
    assert result == {"scenario": "market_crash_2008"}


def test_portfolio_performance():
    analyzer = PortfolioPerformanceAnalyzer()
    result = analyzer.analyze({"return": 0.18, "sharpe": 2.1, "max_dd": 0.09})
    assert result == {"performance": {"return": 0.18, "sharpe": 2.1, "max_dd": 0.09}}


def test_portfolio_memory():
    memory = PortfolioMemory()
    assert memory.history == []
    memory.save({"date": "2024-01-15", "action": "allocation_set", "weights": {"eq": 0.6, "bd": 0.4}})
    memory.save({"date": "2024-02-01", "action": "rebalanced", "reason": "weight_drift"})
    assert len(memory.history) == 2
    assert memory.history[0]["date"] == "2024-01-15"
    assert memory.history[1]["reason"] == "weight_drift"


def test_portfolio_construction_service():
    allocator = AssetAllocationAgent()
    service = PortfolioConstructionService(allocator=allocator)
    result = service.build("balanced_portfolio")
    assert result == {"allocation": "balanced_portfolio"}


def test_full_portfolio_construction_workflow():
    """End-to-end autonomous portfolio construction workflow."""
    # 1. Asset allocation
    allocator = AssetAllocationAgent()
    allocation = allocator.allocate({"equity": 0.50, "bond": 0.25, "cash": 0.15, "alt": 0.10})
    assert allocation["allocation"]["equity"] == 0.50

    # 2. Strategy allocation
    strategy_alloc = StrategyAllocationEngine()
    weights = strategy_alloc.allocate({"momentum": 0.40, "value": 0.35, "macro": 0.25})
    assert weights["weights"]["momentum"] == 0.40

    # 3. Risk budget
    risk = RiskBudgetEngine()
    budget = risk.calculate({"volatility": 0.12, "var_95": 0.02, "max_drawdown": 0.15})
    assert budget["risk_budget"]["volatility"] == 0.12

    # 4. Position sizing
    sizer = PositionSizingAI()
    position = sizer.size({"signal_strength": 0.75, "target_weight": 0.05})
    assert position["position"]["signal_strength"] == 0.75

    # 5. Portfolio optimization
    optimizer = PortfolioOptimizationEngine()
    opt = optimizer.optimize({"method": "max_sharpe", "result": [0.35, 0.30, 0.20, 0.15]})
    assert opt["optimized"]["method"] == "max_sharpe"

    # 6. Exposure check
    exposure = ExposureManagementEngine()
    exp = exposure.check({"sector_tech": 0.30, "factor_momentum": 0.25})
    assert exp["exposure"]["sector_tech"] == 0.30

    # 7. Rebalance
    rebalance = PortfolioRebalanceEngine()
    rebal = rebalance.rebalance({"current": {"NVDA": 0.08}, "target": {"NVDA": 0.05}})
    assert rebal["portfolio"]["current"]["NVDA"] == 0.08

    # 8. Stress test
    stress = PortfolioStressTester()
    scenario = stress.simulate("rate_hike_200bps")
    assert scenario["scenario"] == "rate_hike_200bps"

    # 9. Performance analysis
    perf = PortfolioPerformanceAnalyzer()
    analysis = perf.analyze({"ytd_return": 0.12, "sharpe": 1.8, "calmar": 2.5})
    assert analysis["performance"]["ytd_return"] == 0.12

    # 10. Portfolio memory
    memory = PortfolioMemory()
    memory.save({"cycle": "monthly", "action": "constructed", "date": "2024-Q1"})
    memory.save({"cycle": "monthly", "action": "rebalanced", "drift": 0.03})
    assert len(memory.history) == 2

    # 11. Portfolio construction service
    service = PortfolioConstructionService(allocator=allocator)
    portfolio = service.build("aggressive_growth")
    assert portfolio["allocation"] == "aggressive_growth"
