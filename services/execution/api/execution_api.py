"""Execution Optimization API

REST endpoints for execution optimization:
- POST /optimize - Get execution recommendation
- POST /plan - Generate full execution plan
- POST /impact - Estimate market impact
- POST /tca/analyze - Analyze execution costs
- GET /tca/summary - Get TCA summary statistics
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/execution", tags=["execution"])


# =============================================================================
# Request / Response Models
# =============================================================================


class MarketStateRequest(BaseModel):
    """Market conditions for optimization."""

    symbol: str = Field(..., description="Trading symbol")
    bid: float = Field(..., description="Best bid price")
    ask: float = Field(..., description="Best ask price")
    last_price: float = Field(..., description="Last traded price")
    daily_volume: float = Field(default=1_000_000.0, description="Average daily volume")
    current_volume: float = Field(default=0.0, description="Volume traded so far today")
    volatility_20d: float = Field(default=0.20, description="20-day annualized volatility")
    bid_size: float = Field(default=0.0)
    ask_size: float = Field(default=0.0)


class OptimizeRequest(BaseModel):
    """Request to get execution optimization recommendation."""

    symbol: str = Field(..., description="Trading symbol")
    quantity: float = Field(..., gt=0, description="Order quantity")
    side: str = Field(..., description="BUY or SELL")
    urgency: str = Field(default="MEDIUM", description="LOW, MEDIUM, HIGH, or CRITICAL")
    algorithm: str = Field(default="ADAPTIVE", description="TWAP, VWAP, POV, or ADAPTIVE")
    max_duration_minutes: int = Field(default=120, ge=1, le=390)
    max_participation_rate: float = Field(default=0.15, ge=0.01, le=1.0)
    market_state: MarketStateRequest = Field(..., description="Current market conditions")


class ImpactRequest(BaseModel):
    """Request to estimate market impact."""

    symbol: str
    quantity: float = Field(..., gt=0)
    side: str = "BUY"
    daily_volume: float = Field(..., gt=0)
    volatility: float = Field(default=0.20, ge=0)
    spread_bps: float = Field(default=5.0, ge=0)
    num_slices: int = Field(default=1, ge=1)


class TCARequest(BaseModel):
    """Request to perform TCA analysis."""

    order_id: str
    symbol: str
    side: str
    quantity: float = Field(..., gt=0)
    arrival_price: float = Field(..., gt=0)
    execution_price: float = Field(..., gt=0)
    benchmark_vwap: float = 0.0
    benchmark_twap: float = 0.0
    spread_bps: float = 0.0
    commission: float = 0.0
    expected_impact_bps: float = 0.0


class OptimizationResponse(BaseModel):
    """Execution optimization recommendation."""

    symbol: str
    quantity: float
    side: str
    recommended_algorithm: str
    estimated_impact_bps: float
    estimated_impact_pct: str
    recommended_slices: int
    duration_minutes: int
    participation_rate: str
    market_volatility: float
    market_spread_bps: float


class PlanSliceResponse(BaseModel):
    slice_id: str
    quantity: float
    scheduled_time: str
    expected_impact_bps: float


class PlanResponse(BaseModel):
    plan_id: str
    order_id: str
    algorithm: str
    total_quantity: float
    slice_count: int
    expected_impact_bps: float
    expected_slippage_bps: float
    estimated_cost: float
    duration_minutes: int
    slices: List[PlanSliceResponse] = Field(default_factory=list)


class ImpactResponse(BaseModel):
    symbol: str
    order_quantity: float
    participation_rate: str
    temporary_impact_bps: float
    permanent_impact_bps: float
    total_impact_bps: float
    total_impact_amount: float
    expected_impact_pct: str


class TCAResponse(BaseModel):
    order_id: str
    symbol: str
    side: str
    quantity: float
    arrival_price: float
    execution_price: float
    implementation_shortfall_bps: float
    arrival_slippage_bps: float
    vwap_slippage_bps: float
    spread_cost_bps: float
    market_impact_bps: float
    delay_cost_bps: float
    commission_bps: float
    total_cost_bps: float
    total_cost_amount: float
    quality: str


class TCASummaryResponse(BaseModel):
    total_orders: int
    avg_cost_bps: Optional[float] = None
    min_cost_bps: Optional[float] = None
    max_cost_bps: Optional[float] = None
    avg_shortfall_bps: Optional[float] = None
    quality_distribution: Optional[Dict[str, int]] = None
    excellent_rate: Optional[str] = None
    message: Optional[str] = None


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/optimize", response_model=OptimizationResponse)
async def optimize_execution(request: OptimizeRequest):
    """Get an execution recommendation for an order.

    Returns the recommended algorithm, expected impact,
    and execution parameters without creating a full plan.
    """
    from services.execution.optimization import (
        ExecutionOptimizer,
        ExecutionTask,
        MarketState,
        OrderSide,
        OrderUrgency,
        ExecutionAlgorithm,
    )

    side_map = {"BUY": OrderSide.BUY, "SELL": OrderSide.SELL}
    urgency_map = {
        "LOW": OrderUrgency.LOW,
        "MEDIUM": OrderUrgency.MEDIUM,
        "HIGH": OrderUrgency.HIGH,
        "CRITICAL": OrderUrgency.CRITICAL,
    }
    algo_map = {
        "TWAP": ExecutionAlgorithm.TWAP,
        "VWAP": ExecutionAlgorithm.VWAP,
        "POV": ExecutionAlgorithm.POV,
        "ADAPTIVE": ExecutionAlgorithm.ADAPTIVE,
    }

    ms = request.market_state
    market_state = MarketState(
        symbol=ms.symbol,
        bid=ms.bid,
        ask=ms.ask,
        last_price=ms.last_price,
        daily_volume=ms.daily_volume,
        current_volume=ms.current_volume,
        volatility_20d=ms.volatility_20d,
        bid_size=ms.bid_size,
        ask_size=ms.ask_size,
    )

    task = ExecutionTask(
        order_id=f"ORD_{request.symbol}",
        symbol=request.symbol,
        quantity=request.quantity,
        side=side_map.get(request.side, OrderSide.BUY),
        urgency=urgency_map.get(request.urgency, OrderUrgency.MEDIUM),
        algorithm=algo_map.get(request.algorithm, ExecutionAlgorithm.ADAPTIVE),
        max_duration_minutes=request.max_duration_minutes,
        max_participation_rate=request.max_participation_rate,
    )

    optimizer = ExecutionOptimizer()
    try:
        rec = optimizer.get_recommendation(task, market_state)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return OptimizationResponse(**rec)


@router.post("/plan", response_model=PlanResponse)
async def generate_execution_plan(request: OptimizeRequest):
    """Generate a full execution plan with slices.

    Creates a detailed plan including all execution slices,
    timing, and cost estimates.
    """
    from services.execution.optimization import (
        ExecutionOptimizer,
        ExecutionTask,
        MarketState,
        OrderSide,
        OrderUrgency,
        ExecutionAlgorithm,
    )

    side_map = {"BUY": OrderSide.BUY, "SELL": OrderSide.SELL}
    urgency_map = {
        "LOW": OrderUrgency.LOW,
        "MEDIUM": OrderUrgency.MEDIUM,
        "HIGH": OrderUrgency.HIGH,
        "CRITICAL": OrderUrgency.CRITICAL,
    }
    algo_map = {
        "TWAP": ExecutionAlgorithm.TWAP,
        "VWAP": ExecutionAlgorithm.VWAP,
        "POV": ExecutionAlgorithm.POV,
        "ADAPTIVE": ExecutionAlgorithm.ADAPTIVE,
    }

    ms = request.market_state
    market_state = MarketState(
        symbol=ms.symbol,
        bid=ms.bid,
        ask=ms.ask,
        last_price=ms.last_price,
        daily_volume=ms.daily_volume,
        current_volume=ms.current_volume,
        volatility_20d=ms.volatility_20d,
        bid_size=ms.bid_size,
        ask_size=ms.ask_size,
    )

    task = ExecutionTask(
        order_id=f"ORD_{request.symbol}",
        symbol=request.symbol,
        quantity=request.quantity,
        side=side_map.get(request.side, OrderSide.BUY),
        urgency=urgency_map.get(request.urgency, OrderUrgency.MEDIUM),
        algorithm=algo_map.get(request.algorithm, ExecutionAlgorithm.ADAPTIVE),
        max_duration_minutes=request.max_duration_minutes,
        max_participation_rate=request.max_participation_rate,
    )

    optimizer = ExecutionOptimizer()
    try:
        plan = optimizer.optimize(task, market_state)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    slices = [
        PlanSliceResponse(
            slice_id=s.slice_id,
            quantity=s.quantity,
            scheduled_time=s.scheduled_time.isoformat(),
            expected_impact_bps=s.expected_impact_bps,
        )
        for s in plan.slices
    ]

    return PlanResponse(
        plan_id=plan.plan_id,
        order_id=plan.order_id,
        algorithm=plan.algorithm.value,
        total_quantity=plan.total_quantity,
        slice_count=plan.slice_count,
        expected_impact_bps=plan.expected_impact_bps,
        expected_slippage_bps=plan.expected_slippage_bps,
        estimated_cost=plan.estimated_cost,
        duration_minutes=plan.duration_minutes,
        slices=slices,
    )


@router.post("/impact", response_model=ImpactResponse)
async def estimate_impact(request: ImpactRequest):
    """Estimate market impact for an order.

    Returns temporary, permanent, and total impact estimates
    based on order size, daily volume, volatility, and spread.
    """
    from services.execution.optimization import MarketImpactModel, MarketState

    model = MarketImpactModel()
    market_state = MarketState(
        symbol=request.symbol,
        bid=0.0,
        ask=0.0,
        last_price=0.0,
        daily_volume=request.daily_volume,
        volatility_20d=request.volatility,
        spread_bps=request.spread_bps,
    )

    is_buy = request.side.upper() == "BUY"
    impact = model.estimate_sliced(
        symbol=request.symbol,
        total_quantity=request.quantity,
        num_slices=request.num_slices,
        market_state=market_state,
        is_buy=is_buy,
    )

    return ImpactResponse(
        symbol=impact.symbol,
        order_quantity=impact.order_quantity,
        participation_rate=f"{impact.participation_rate:.4%}",
        temporary_impact_bps=impact.temporary_impact_bps,
        permanent_impact_bps=impact.permanent_impact_bps,
        total_impact_bps=impact.total_impact_bps,
        total_impact_amount=impact.total_impact_amount,
        expected_impact_pct=f"{impact.total_impact_bps / 100:.3%}",
    )


@router.post("/tca/analyze", response_model=TCAResponse)
async def analyze_tca(request: TCARequest):
    """Perform Transaction Cost Analysis on an execution.

    Breaks down total execution cost into components:
    implementation shortfall, slippage, spread, impact,
    delay, and commission.
    """
    from services.execution.tca import TCAAnalyzer

    analyzer = TCAAnalyzer()
    try:
        result = analyzer.analyze(
            order_id=request.order_id,
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            arrival_price=request.arrival_price,
            execution_price=request.execution_price,
            benchmark_vwap=request.benchmark_vwap,
            benchmark_twap=request.benchmark_twap,
            spread_bps=request.spread_bps,
            commission=request.commission,
            expected_impact_bps=request.expected_impact_bps,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return TCAResponse(
        order_id=result.order_id,
        symbol=result.symbol,
        side=result.side,
        quantity=result.quantity,
        arrival_price=result.arrival_price,
        execution_price=result.execution_price,
        implementation_shortfall_bps=result.implementation_shortfall_bps,
        arrival_slippage_bps=result.arrival_slippage_bps,
        vwap_slippage_bps=result.vwap_slippage_bps,
        spread_cost_bps=result.spread_cost_bps,
        market_impact_bps=result.market_impact_bps,
        delay_cost_bps=result.delay_cost_bps,
        commission_bps=result.commission_bps,
        total_cost_bps=result.total_cost_bps,
        total_cost_amount=result.total_cost_amount,
        quality=result.quality.value,
    )


@router.get("/tca/summary", response_model=TCASummaryResponse)
async def get_tca_summary():
    """Get aggregate TCA summary statistics.

    Note: Uses an in-memory analyzer; in production,
    this would query a persistent data store.
    """
    from services.execution.tca import TCAAnalyzer

    # In production, this would be a singleton or DB-backed
    analyzer = TCAAnalyzer()
    stats = analyzer.get_summary_stats()
    return TCASummaryResponse(**stats)
