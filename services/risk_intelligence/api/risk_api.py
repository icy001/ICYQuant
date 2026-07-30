from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional

from ...service import RiskIntelligenceService

router = APIRouter(prefix="/api/v1/risk", tags=["risk_intelligence"])

service = RiskIntelligenceService()


class RiskScoreRequest(BaseModel):
    volatility: float = 0.2
    liquidity: float = 0.8
    credit_spread: float = 0.05
    var_95: float = 0.02


class StressTestRequest(BaseModel):
    scenario: str = "market_crash"
    portfolio_value: float = 1000000
    holdings: Optional[Dict[str, float]] = None
    capital_threshold: float = 0.05


class ExposureRequest(BaseModel):
    sector_exposure: Dict[str, float]
    country_exposure: Optional[Dict[str, float]] = None
    currency_exposure: Optional[Dict[str, float]] = None
    asset_exposure: Optional[Dict[str, float]] = None
    strategy_exposure: Optional[Dict[str, float]] = None
    agent_exposure: Optional[Dict[str, float]] = None


class FullAssessmentRequest(BaseModel):
    volatility: float = 0.2
    liquidity: float = 0.8
    credit_spread: float = 0.05
    var_95: float = 0.02
    trend: float = 0.01
    volume_ratio: float = 1.0
    spread: float = 0.0005
    index_decline: float = 0.0
    vix_change: float = 0.0
    volume_surge: float = 1.0
    bid_ask_spread: float = 0.0005
    signal_confidence: float = 0.8


@router.get("/score")
async def get_risk_score(
    volatility: float = 0.2,
    liquidity: float = 0.8,
    credit_spread: float = 0.05,
    var_95: float = 0.02,
):
    result = service.get_risk_score(
        volatility=volatility,
        liquidity=liquidity,
        credit_spread=credit_spread,
        var_95=var_95,
    )
    return {
        "risk_score": result.risk_score,
        "risk_level": result.risk_level,
        "recommendation": result.recommendation,
    }


@router.post("/stress")
async def run_stress_test(request: StressTestRequest):
    result = service.run_stress_test(
        scenario_name=request.scenario,
        portfolio_value=request.portfolio_value,
        holdings=request.holdings,
        capital_threshold=request.capital_threshold,
    )
    return {
        "scenario_name": result.scenario_name,
        "estimated_loss_pct": result.estimated_loss_pct,
        "max_drawdown_pct": result.max_drawdown_pct,
        "capital_impact_pct": result.capital_impact_pct,
        "passed": result.passed,
        "warnings": result.warnings,
    }


@router.get("/exposure")
async def get_exposure(
    sector: str = "technology",
    exposure: float = 0.38,
):
    result = service.get_exposure_report(sector_exposure={sector: exposure})
    return {
        "total_exposure": result.total_exposure,
        "used_risk_budget_pct": result.used_risk_budget_pct,
        "remaining_budget_pct": result.remaining_budget_pct,
        "violations": result.violations,
    }


@router.post("/full-assessment")
async def full_risk_assessment(request: FullAssessmentRequest):
    result = service.full_risk_assessment(
        volatility=request.volatility,
        liquidity=request.liquidity,
        credit_spread=request.credit_spread,
        var_95=request.var_95,
        trend=request.trend,
        volume_ratio=request.volume_ratio,
        spread=request.spread,
        index_decline=request.index_decline,
        vix_change=request.vix_change,
        volume_surge=request.volume_surge,
        bid_ask_spread=request.bid_ask_spread,
        signal_confidence=request.signal_confidence,
    )
    return {
        "emergency_level": result.emergency_level,
        "can_trade": result.can_trade,
        "risk_score": result.risk_prediction.risk_score if result.risk_prediction else None,
        "risk_level": result.risk_prediction.risk_level if result.risk_prediction else None,
        "market_regime": result.market_regime.regime_type if result.market_regime else None,
        "black_swan_level": result.black_swan_event.level if result.black_swan_event else None,
        "position_size_pct": result.position_size.adjusted_pct if result.position_size else None,
        "actions": {
            "cancel_orders": result.actions.cancel_orders,
            "disable_new_orders": result.actions.disable_new_orders,
            "freeze_agents": result.actions.freeze_agents,
            "notify_admin": result.actions.notify_admin,
        },
    }


@router.post("/emergency-stop")
async def emergency_stop():
    result = service.emergency_stop()
    return {
        "emergency_level": result.emergency_level,
        "can_trade": result.can_trade,
        "message": "Emergency stop activated - all trading halted",
    }


@router.post("/resume")
async def resume_trading():
    result = service.resume_trading()
    return {
        "emergency_level": result.emergency_level,
        "can_trade": result.can_trade,
        "message": "Trading resumed - normal operations restored",
    }


@router.get("/stress-scenarios")
async def list_stress_scenarios():
    return {"scenarios": service.list_stress_scenarios()}


@router.get("/scenario-engine-scenarios")
async def list_scenario_scenarios():
    return {"scenarios": service.list_scenario_engine_scenarios()}
