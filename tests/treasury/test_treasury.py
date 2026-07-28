from services.treasury import *


def test_cash_position():
    manager = CashPositionManager()
    result = manager.get_position("fund001")
    assert result["account"] == "fund001"


def test_cash_position_default():
    manager = CashPositionManager()
    result = manager.get_position("fund_alpha")
    assert result == {"account": "fund_alpha", "cash": 0}


def test_liquidity_forecast():
    engine = LiquidityForecastEngine()
    data = {"current_cash": 5_000_000, "predicted_need": 2_000_000}
    result = engine.forecast(data)
    assert result == {"liquidity": data}


def test_funding_allocation():
    engine = FundingAllocationEngine()
    result = engine.allocate(10_000_000, 0.7)
    assert result == 7_000_000


def test_financing_optimization():
    engine = FinancingOptimizationEngine()
    result = engine.optimize(0.045)
    assert result == {"optimized_cost": 0.045}


def test_fx_exposure():
    manager = FXExposureManager()
    result = manager.exposure("USD")
    assert result == {"currency": "USD"}


def test_treasury_risk_monitor():
    monitor = TreasuryRiskMonitor()
    result = monitor.check({"liquidity_ratio": 0.35})
    assert result == {"status": "normal"}


def test_liquidity_stress_test():
    tester = LiquidityStressTester()
    result = tester.simulate("market_crash_30pct")
    assert result == {"scenario": "market_crash_30pct"}


def test_treasury_optimization_agent():
    agent = TreasuryOptimizationAgent()
    state = {"cash_ratio": 0.35, "market_volatility": "high"}
    result = agent.recommend(state)
    assert result == {"recommendation": state}


def test_treasury_report():
    generator = TreasuryReportGenerator()
    data = {"liquidity_status": "healthy", "fx_exposure": "hedged"}
    result = generator.generate(data)
    assert result == {"report": data}


def test_treasury_memory():
    memory = TreasuryMemory()
    assert memory.history == []
    memory.save({"event": "cash_audit", "balance": 10_000_000})
    memory.save({"event": "stress_test", "result": "passed"})
    assert len(memory.history) == 2
    assert memory.history[0]["event"] == "cash_audit"
    assert memory.history[1]["event"] == "stress_test"


def test_treasury_service():
    cash_manager = CashPositionManager()
    service = TreasuryService(cash_manager=cash_manager)
    result = service.position("fund001")
    assert result == {"account": "fund001", "cash": 0}


def test_full_treasury_workflow():
    """End-to-end treasury management workflow."""
    # 1. Check cash position
    cash_mgr = CashPositionManager()
    cash = cash_mgr.get_position("FUND-MACRO-01")
    assert cash["account"] == "FUND-MACRO-01"

    # 2. Forecast liquidity
    liquidity_engine = LiquidityForecastEngine()
    forecast = liquidity_engine.forecast({
        "positions": 50_000_000,
        "margin_requirement": 5_000_000,
        "redemption_requests": 2_000_000,
    })
    assert forecast["liquidity"]["margin_requirement"] == 5_000_000

    # 3. Allocate funding
    allocation = FundingAllocationEngine()
    trading_capital = allocation.allocate(20_000_000, 0.70)
    assert trading_capital == 14_000_000
    reserve = allocation.allocate(20_000_000, 0.20)
    assert reserve == 4_000_000

    # 4. Optimize financing
    financing = FinancingOptimizationEngine()
    opt_result = financing.optimize(0.035)
    assert opt_result["optimized_cost"] == 0.035

    # 5. Check FX exposure
    fx = FXExposureManager()
    usd_exposure = fx.exposure("USD")
    assert usd_exposure["currency"] == "USD"
    eur_exposure = fx.exposure("EUR")
    assert eur_exposure["currency"] == "EUR"

    # 6. Monitor treasury risk
    risk_monitor = TreasuryRiskMonitor()
    risk = risk_monitor.check({"liquidity_ratio": 0.40, "funding_gap": 0})
    assert risk["status"] == "normal"

    # 7. Run stress test
    stress = LiquidityStressTester()
    scenario = stress.simulate("volatility_spike_50pct")
    assert scenario["scenario"] == "volatility_spike_50pct"

    # 8. Get AI recommendation
    agent = TreasuryOptimizationAgent()
    rec = agent.recommend({
        "cash_ratio": 0.28,
        "volatility": "elevated",
        "margin_utilization": 0.65,
    })
    assert rec["recommendation"]["cash_ratio"] == 0.28

    # 9. Generate report
    report_gen = TreasuryReportGenerator()
    report = report_gen.generate({
        "daily_liquidity": "adequate",
        "fx_hedge_ratio": 0.95,
        "stress_test": "passed",
    })
    assert report["report"]["daily_liquidity"] == "adequate"

    # 10. Save to treasury memory
    memory = TreasuryMemory()
    memory.save({"event": "daily_close", "cash_balance": 15_000_000})
    memory.save({"event": "stress_test_completed", "scenario": "volatility_spike"})
    assert len(memory.history) == 2

    # 11. Treasury service
    service = TreasuryService(cash_manager=cash_mgr)
    svc_result = service.position("FUND-MACRO-01")
    assert svc_result["account"] == "FUND-MACRO-01"
