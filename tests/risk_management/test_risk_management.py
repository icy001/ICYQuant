from services.risk_management import *


def test_risk_monitor():
    agent = RiskMonitoringAgent()
    result = agent.monitor("portfolio")
    assert result["risk"] == "portfolio"


def test_risk_monitoring_agent():
    agent = RiskMonitoringAgent()
    result = agent.monitor({"positions": 15, "exposure": 1.2, "var": 0.025})
    assert result == {"risk": {"positions": 15, "exposure": 1.2, "var": 0.025}}


def test_dynamic_risk_limit():
    engine = DynamicRiskLimitEngine()
    result = engine.calculate(0.25)
    assert result == {"limit": 0.25}


def test_risk_prediction():
    engine = RiskPredictionEngine()
    result = engine.predict({"volatility_forecast": 0.18, "var_forecast": 0.03})
    assert result == {"prediction": {"volatility_forecast": 0.18, "var_forecast": 0.03}}


def test_var_engine():
    engine = VaREngine()
    result = engine.calculate({"value_at_risk_95": 0.025})
    assert result == {"var": {"value_at_risk_95": 0.025}}


def test_cvar_engine():
    engine = CVaREngine()
    result = engine.calculate({"conditional_var_95": 0.04})
    assert result == {"cvar": {"conditional_var_95": 0.04}}


def test_scenario_analysis():
    engine = ScenarioAnalysisEngine()
    result = engine.simulate("interest_rate_hike_300bps")
    assert result == {"scenario": "interest_rate_hike_300bps"}


def test_risk_intervention():
    agent = RiskInterventionAgent()
    result = agent.execute("reduce_leverage_50pct")
    assert result == {"action": "reduce_leverage_50pct"}


def test_risk_attribution():
    engine = RiskAttributionEngine()
    result = engine.analyze("AAPL_position_contributes_30pct_risk")
    assert result == {"source": "AAPL_position_contributes_30pct_risk"}


def test_risk_alert():
    engine = RiskAlertEngine()
    result = engine.alert({"var": 0.02, "status": "ok"})
    assert result == {"level": "NORMAL"}


def test_risk_memory():
    memory = RiskMemory()
    assert memory.history == []
    memory.save({"event": "var_breach", "level": "WARNING", "value": 0.035})
    memory.save({"event": "intervention", "action": "reduce_position", "reduction": 0.20})
    assert len(memory.history) == 2
    assert memory.history[0]["event"] == "var_breach"
    assert memory.history[1]["action"] == "reduce_position"


def test_risk_management_service():
    monitor = RiskMonitoringAgent()
    service = RiskManagementService(monitor=monitor)
    result = service.check("daily_risk_report")
    assert result == {"risk": "daily_risk_report"}


def test_full_risk_management_workflow():
    """End-to-end autonomous risk management workflow."""
    # 1. Monitor portfolio risk
    monitor = RiskMonitoringAgent()
    risk_state = monitor.monitor({"var": 0.022, "cvar": 0.035, "exposure": 1.5})
    assert risk_state["risk"]["var"] == 0.022

    # 2. Calculate dynamic risk limits
    limits = DynamicRiskLimitEngine()
    limit = limits.calculate(0.30)
    assert limit["limit"] == 0.30

    # 3. Predict future risk
    prediction = RiskPredictionEngine()
    forecast = prediction.predict({"predicted_var": 0.028, "confidence": 0.95})
    assert forecast["prediction"]["predicted_var"] == 0.028

    # 4. Calculate VaR
    var_engine = VaREngine()
    var_result = var_engine.calculate({"historical_var_95": 0.02})
    assert var_result["var"]["historical_var_95"] == 0.02

    # 5. Calculate CVaR
    cvar_engine = CVaREngine()
    cvar_result = cvar_engine.calculate({"expected_shortfall_95": 0.04})
    assert cvar_result["cvar"]["expected_shortfall_95"] == 0.04

    # 6. Run scenario analysis
    scenario = ScenarioAnalysisEngine()
    impact = scenario.simulate("tech_sector_crash_40pct")
    assert impact["scenario"] == "tech_sector_crash_40pct"

    # 7. Execute intervention
    intervention = RiskInterventionAgent()
    action = intervention.execute("cut_tech_exposure_by_30pct")
    assert action["action"] == "cut_tech_exposure_by_30pct"

    # 8. Attribute risk
    attribution = RiskAttributionEngine()
    source = attribution.analyze("NVDA_position_drives_25pct_var")
    assert source["source"] == "NVDA_position_drives_25pct_var"

    # 9. Trigger alert
    alert = RiskAlertEngine()
    status = alert.alert({"var": 0.035, "limit": 0.03})
    assert status["level"] == "NORMAL"

    # 10. Save risk memory
    memory = RiskMemory()
    memory.save({"timestamp": "2024-03-15", "risk_event": "var_approaching_limit"})
    memory.save({"timestamp": "2024-03-15", "decision": "reduced_leverage"})
    assert len(memory.history) == 2

    # 11. Risk management service
    service = RiskManagementService(monitor=monitor)
    daily_risk = service.check("end_of_day_portfolio")
    assert daily_risk["risk"] == "end_of_day_portfolio"
