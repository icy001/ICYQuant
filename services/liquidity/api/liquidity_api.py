"""Liquidity & Market Impact REST API.

FastAPI router for liquidity analysis endpoints.

Endpoints:
    GET    /api/v1/liquidity/{symbol}      Get liquidity score & depth
    POST   /api/v1/liquidity/impact        Estimate market impact
    POST   /api/v1/liquidity/capacity      Analyze strategy capacity
    GET    /api/v1/liquidity/imbalance/{symbol}  Get bid/ask imbalance
    POST   /api/v1/liquidity/evaluate      Full liquidity evaluation
    POST   /api/v1/liquidity/compare       Compare execution algorithms
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..models import Side, OrderBook, PriceLevel
from ..orderbook import OrderBookManager
from ..scoring import LiquidityScorer
from ..impact import MarketImpactEngine
from ..capacity import CapacityAnalyzer
from ..estimator import ImbalanceEstimator
from ..service import LiquidityService


# =============================================================================
# Pydantic Request Models
# =============================================================================


class BookLevel(BaseModel):
    """A single price level in request format."""

    price: float = Field(..., gt=0, description="Price")
    volume: float = Field(..., gt=0, description="Volume at this price")


class BookSnapshot(BaseModel):
    """Order book snapshot for requests."""

    symbol: str = Field(..., description="Trading symbol")
    bids: List[BookLevel] = Field(..., description="Bid levels (highest first)")
    asks: List[BookLevel] = Field(..., description="Ask levels (lowest first)")
    last_price: float = Field(0.0, description="Last traded price")
    daily_volume: float = Field(0.0, description="Current day volume")
    adv: float = Field(0.0, description="Average daily volume")


class ImpactRequest(BaseModel):
    """Market impact estimation request."""

    symbol: str = Field(..., description="Trading symbol")
    quantity: float = Field(..., gt=0, description="Order quantity")
    side: str = Field("BUY", description="BUY or SELL")
    volatility: float = Field(0.25, ge=0, description="Annualized volatility")
    bids: List[BookLevel] = Field(default_factory=list, description="Bid levels")
    asks: List[BookLevel] = Field(default_factory=list, description="Ask levels")
    last_price: float = Field(0.0, description="Last traded price")
    adv: float = Field(0.0, description="Average daily volume")


class CapacityRequest(BaseModel):
    """Strategy capacity analysis request."""

    symbol: str = Field(..., description="Trading symbol")
    strategy_id: str = Field("", description="Strategy identifier")
    price: float = Field(0.0, description="Current price")
    current_daily_notional: float = Field(0.0, description="Current daily notional")
    current_position: float = Field(0.0, description="Current position shares")
    bids: List[BookLevel] = Field(default_factory=list, description="Bid levels")
    asks: List[BookLevel] = Field(default_factory=list, description="Ask levels")
    adv: float = Field(0.0, description="Average daily volume")


# =============================================================================
# Singleton instances
# =============================================================================

book_manager = OrderBookManager()
scorer = LiquidityScorer()
impact_engine = MarketImpactEngine()
capacity_analyzer = CapacityAnalyzer()
imbalance_estimator = ImbalanceEstimator()
liquidity_service = LiquidityService()

router = APIRouter(prefix="/api/v1/liquidity", tags=["Liquidity"])


# =============================================================================
# Helpers
# =============================================================================


def _build_book_from_snapshot(snap: BookSnapshot) -> OrderBook:
    bids = [(b.price, b.volume) for b in snap.bids]
    asks = [(a.price, a.volume) for a in snap.asks]
    return book_manager.build_book(
        symbol=snap.symbol,
        bids=bids,
        asks=asks,
        last_price=snap.last_price,
        daily_volume=snap.daily_volume,
        adv=snap.adv,
    )


def _build_book_from_params(
    symbol: str,
    bids: List[BookLevel],
    asks: List[BookLevel],
    last_price: float = 0.0,
    adv: float = 0.0,
) -> OrderBook:
    return book_manager.build_book(
        symbol=symbol,
        bids=[(b.price, b.volume) for b in bids],
        asks=[(a.price, a.volume) for a in asks],
        last_price=last_price,
        adv=adv,
    )


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/{symbol}", summary="Get liquidity score for a symbol")
async def get_liquidity(
    symbol: str,
    bid_price: float = Query(0.0, description="Best bid price"),
    bid_volume: float = Query(0.0, description="Best bid volume"),
    ask_price: float = Query(0.0, description="Best ask price"),
    ask_volume: float = Query(0.0, description="Best ask volume"),
    last_price: float = Query(0.0, description="Last traded price"),
    daily_volume: float = Query(0.0, description="Current day volume"),
    adv: float = Query(0.0, description="Average daily volume"),
    order_quantity: float = Query(0.0, description="Reference order size"),
):
    """Get liquidity score and analysis for a symbol.

    Uses L1 (top-of-book) data if provided, otherwise returns
    the cached order book if available.

    Example:
        GET /api/v1/liquidity/NVDA?bid_price=150.0&bid_volume=5000&ask_price=150.02&ask_volume=3000
    """
    # Build book from query params or use cached
    if bid_price > 0 and ask_price > 0:
        book = book_manager.build_book_l1(
            symbol=symbol,
            bid_price=bid_price,
            bid_volume=bid_volume,
            ask_price=ask_price,
            ask_volume=ask_volume,
            last_price=last_price,
            daily_volume=daily_volume,
            adv=adv,
        )
    else:
        book = book_manager.get_book(symbol)
        if book is None:
            raise HTTPException(
                status_code=404,
                detail=f"No order book data for {symbol}. Provide bid/ask prices.",
            )

    # Compute metrics
    score = scorer.score(book, order_quantity=order_quantity)
    depth = liquidity_service.analyze_depth(book, order_quantity)
    imbalance = imbalance_estimator.analyze(book)

    return {
        "symbol": book.symbol,
        "score": score.to_dict(),
        "spread": round(book.spread, 4),
        "spread_bps": round(book.spread_bps, 2),
        "depth": depth.to_dict(),
        "imbalance": imbalance.to_dict(),
        "book_summary": {
            "best_bid": book.best_bid.price if book.best_bid else None,
            "best_ask": book.best_ask.price if book.best_ask else None,
            "mid_price": round(book.mid_price, 4),
            "total_bid_volume": round(book.total_bid_volume, 2),
            "total_ask_volume": round(book.total_ask_volume, 2),
        },
    }


@router.post("/impact", summary="Estimate market impact")
async def estimate_impact(request: ImpactRequest):
    """Estimate the market impact of an order.

    Example request:
        {
            "symbol": "NVDA",
            "quantity": 100000,
            "side": "BUY",
            "bids": [{"price": 150.0, "volume": 5000}],
            "asks": [{"price": 150.02, "volume": 3000}],
            "adv": 5000000
        }
    """
    book = _build_book_from_params(
        symbol=request.symbol,
        bids=request.bids,
        asks=request.asks,
        last_price=request.last_price,
        adv=request.adv,
    )

    try:
        side = Side(request.side.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid side: {request.side}")

    estimate = impact_engine.estimate(
        book=book,
        quantity=request.quantity,
        side=side,
        volatility=request.volatility,
    )

    return {
        "symbol": book.symbol,
        "expected_impact": f"{estimate.total_impact_pct:.3%}",
        "impact_bps": round(estimate.total_impact_bps, 2),
        "total_cost_bps": round(estimate.total_cost_bps, 2),
        "recommended_algorithm": estimate.recommended_algorithm,
        "recommended_slices": estimate.recommended_slices,
        "confidence": estimate.confidence,
        "details": estimate.to_dict(),
    }


@router.post("/capacity", summary="Analyze strategy capacity")
async def analyze_capacity(request: CapacityRequest):
    """Analyze strategy capacity limits.

    Example request:
        {
            "symbol": "NVDA",
            "strategy_id": "AI_Momentum",
            "price": 150.0,
            "current_daily_notional": 5000000,
            "adv": 5000000
        }
    """
    book = _build_book_from_params(
        symbol=request.symbol,
        bids=request.bids,
        asks=request.asks,
        adv=request.adv,
    )

    estimate = capacity_analyzer.analyze(
        book=book,
        strategy_id=request.strategy_id or request.symbol,
        price=request.price,
        current_daily_notional=request.current_daily_notional,
        current_position=request.current_position,
    )

    return estimate.to_dict()


@router.get("/imbalance/{symbol}", summary="Get bid/ask imbalance")
async def get_imbalance(
    symbol: str,
    bid_volume: float = Query(0.0, description="Total bid volume"),
    ask_volume: float = Query(0.0, description="Total ask volume"),
):
    """Get bid/ask imbalance analysis for a symbol.

    Example:
        GET /api/v1/liquidity/imbalance/NVDA?bid_volume=50000&ask_volume=10000
    """
    if bid_volume > 0 or ask_volume > 0:
        # Quick analysis from volume snapshot
        book = OrderBook(
            symbol=symbol.upper(),
            bids=[PriceLevel(price=100.0, volume=bid_volume)],
            asks=[PriceLevel(price=100.01, volume=ask_volume)],
        )
    else:
        book = book_manager.get_book(symbol)
        if book is None:
            raise HTTPException(
                status_code=404,
                detail=f"No data for {symbol}. Provide bid_volume and ask_volume.",
            )

    analysis = imbalance_estimator.analyze(book)
    return analysis.to_dict()


@router.post("/evaluate", summary="Full liquidity evaluation")
async def evaluate_liquidity(request: ImpactRequest):
    """Run the full liquidity evaluation pipeline.

    Returns score, impact, capacity, imbalance, and execution recommendation.

    Example request:
        {
            "symbol": "NVDA",
            "quantity": 50000,
            "side": "BUY",
            "bids": [{"price": 150.0, "volume": 2000}],
            "asks": [{"price": 150.02, "volume": 3000}],
            "adv": 5000000
        }
    """
    book = _build_book_from_params(
        symbol=request.symbol,
        bids=request.bids,
        asks=request.asks,
        last_price=request.last_price,
        adv=request.adv,
    )

    try:
        side = Side(request.side.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid side: {request.side}")

    result = liquidity_service.evaluate(
        book=book,
        quantity=request.quantity,
        side=side,
        volatility=request.volatility,
    )

    return result


@router.post("/compare", summary="Compare execution algorithms")
async def compare_algorithms(request: ImpactRequest):
    """Compare market impact across different execution algorithms.

    Example request:
        {
            "symbol": "NVDA",
            "quantity": 100000,
            "side": "BUY",
            "adv": 5000000
        }
    """
    book = _build_book_from_params(
        symbol=request.symbol,
        bids=request.bids,
        asks=request.asks,
        last_price=request.last_price,
        adv=request.adv,
    )

    try:
        side = Side(request.side.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid side: {request.side}")

    comparison = impact_engine.compare_algorithms(
        book=book,
        quantity=request.quantity,
        side=side,
        volatility=request.volatility,
    )

    return comparison
