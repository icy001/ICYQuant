"""Strategy Attribution REST API."""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from pydantic import BaseModel, Field

from services.strategy_attribution import (
    AttributionPeriod,
    StrategyAttributionService,
)


router = APIRouter(
    prefix="/strategy",
    tags=["strategy-attribution"],
)

# Module-level service singleton
_attribution_service = StrategyAttributionService()


def get_attribution_service() -> StrategyAttributionService:
    """Dependency injection for attribution service."""
    return _attribution_service


# ========== Request/Response Models ==========


class AttributionRequest(BaseModel):
    """Request to calculate strategy performance attribution."""

    strategy_id: str = Field(..., description="Strategy identifier")
    period: str = Field(..., description="Time period label, e.g. '2026-Q3'")
    strategy_data: dict = Field(..., description="Strategy performance data")
    period_type: Optional[str] = Field("DAILY", description="Attribution period type")


class MultiStrategyAttributionRequest(BaseModel):
    """Request to calculate multi-strategy portfolio attribution."""

    portfolio_id: str = Field(..., description="Portfolio identifier")
    period: str = Field(..., description="Time period label")
    strategies_data: list[dict] = Field(..., description="List of strategy data dicts")
    period_type: Optional[str] = Field("DAILY", description="Attribution period type")


class AttributionResponse(BaseModel):
    """Attribution response."""

    attribution: dict
    analysis: dict
    summary: dict


class MultiAttributionResponse(BaseModel):
    """Multi-strategy attribution response."""

    attribution: dict
    analysis: dict


class CompareRequest(BaseModel):
    """Request to compare attribution across periods."""

    strategy_id: str = Field(..., description="Strategy identifier")
    period_a: str = Field(..., description="First period")
    period_b: str = Field(..., description="Second period")


# ========== API Endpoints ==========


@router.get(
    "/{strategy_id}/attribution",
    response_model=dict,
    summary="Get strategy performance attribution",
    description="Decompose strategy returns into alpha, beta, factor, sector, execution, and risk components.",
)
def get_attribution(
    strategy_id: str,
    period: str = Query(..., description="Time period, e.g. '2026-Q3'"),
    service: StrategyAttributionService = Depends(get_attribution_service),
):
    """Retrieve attribution history for a strategy in a given period."""
    history = service.get_history(strategy_id)
    for attr in history:
        if attr.get("period") == period:
            return {
                "strategy_id": strategy_id,
                "period": period,
                "performance": {
                    "return": f"{attr['total_return_pct']:.2%}",
                    "alpha": f"{attr['alpha_return_bps'] / 100:.2%}",
                    "beta": f"{attr['beta_return_bps'] / 100:.2%}",
                    "factor": f"{attr['factor_return_bps'] / 100:.2%}",
                },
                "attribution": attr,
            }
    return {"error": "Attribution not found for this strategy and period"}


@router.post(
    "/attribution/calculate",
    response_model=dict,
    summary="Calculate strategy performance attribution",
    description="Full pipeline: calculate decomposition, analyze, and summarize.",
)
def calculate_attribution(
    request: AttributionRequest,
    service: StrategyAttributionService = Depends(get_attribution_service),
):
    """Calculate complete performance attribution."""
    period_type = AttributionPeriod(request.period_type)
    result = service.attribute(
        strategy_id=request.strategy_id,
        period=request.period,
        strategy_data=request.strategy_data,
        period_type=period_type,
    )
    return result


@router.post(
    "/attribution/multi",
    response_model=dict,
    summary="Calculate multi-strategy portfolio attribution",
    description="Attribute returns across multiple strategies in a portfolio.",
)
def calculate_multi_attribution(
    request: MultiStrategyAttributionRequest,
    service: StrategyAttributionService = Depends(get_attribution_service),
):
    """Calculate multi-strategy attribution."""
    period_type = AttributionPeriod(request.period_type)
    result = service.attribute_multi_strategy(
        portfolio_id=request.portfolio_id,
        period=request.period,
        strategies_data=request.strategies_data,
        period_type=period_type,
    )
    return result


@router.post(
    "/attribution/compare",
    response_model=dict,
    summary="Compare attribution across two periods",
    description="Analyze changes in attribution components between periods.",
)
def compare_attribution(
    request: CompareRequest,
    service: StrategyAttributionService = Depends(get_attribution_service),
):
    """Compare attribution across two periods."""
    return service.compare_periods(
        strategy_id=request.strategy_id,
        period_a=request.period_a,
        period_b=request.period_b,
    )


@router.get(
    "/attribution/history/{strategy_id}",
    response_model=list[dict],
    summary="Get attribution history for a strategy",
)
def get_attribution_history(
    strategy_id: str,
    service: StrategyAttributionService = Depends(get_attribution_service),
):
    """Get full attribution history for a strategy."""
    return service.get_history(strategy_id)
