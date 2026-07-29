"""Liquidity Service — unified entry point.

Orchestrates the full liquidity analysis pipeline:
1. Order book management
2. Liquidity scoring
3. Market impact estimation
4. Capacity analysis
5. Imbalance detection
6. Execution guidance

Provides a single `evaluate()` method for integration with
the Execution Optimizer and other downstream systems.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .models import (
    CapacityEstimate,
    DepthAnalysis,
    ImbalanceAnalysis,
    LiquidityScore,
    MarketImpactEstimate,
    OrderBook,
    PriceLevel,
    Side,
)
from .orderbook import OrderBookManager
from .depth import DepthAnalyzer
from .scoring import LiquidityScorer
from .impact import MarketImpactEngine
from .capacity import CapacityAnalyzer
from .estimator import ImbalanceEstimator


class LiquidityService:
    """Unified liquidity analysis service.

    Wraps all liquidity sub-components into a single service
    that can be called by the Execution Optimizer for adaptive
    execution decisions.

    Usage:
        service = LiquidityService()
        result = service.evaluate(symbol="NVDA", quantity=50000, side=Side.BUY)
        print(f"Score: {result['score']['grade']}")
        print(f"Algorithm: {result['recommendation']['recommended_algorithm']}")
    """

    def __init__(self) -> None:
        self.book_manager = OrderBookManager()
        self.depth_analyzer = DepthAnalyzer()
        self.scorer = LiquidityScorer()
        self.impact_engine = MarketImpactEngine()
        self.capacity_analyzer = CapacityAnalyzer()
        self.imbalance_estimator = ImbalanceEstimator()

    # -------------------------------------------------------------------------
    # Full Evaluation Pipeline
    # -------------------------------------------------------------------------

    def evaluate(
        self,
        book: OrderBook,
        quantity: float = 0.0,
        side: Side = Side.BUY,
        volatility: float = 0.25,
        strategy_id: str = "",
        price: float = 0.0,
        current_daily_notional: float = 0.0,
        current_position: float = 0.0,
    ) -> Dict[str, Any]:
        """Run the full liquidity evaluation pipeline.

        Args:
            book: Current order book
            quantity: Order quantity to evaluate
            side: BUY or SELL
            volatility: Annualized volatility
            strategy_id: Strategy ID for capacity analysis
            price: Current price (for notional calc)
            current_daily_notional: Current daily notional traded
            current_position: Current position size

        Returns:
            Dict with score, impact, capacity, imbalance, recommendation
        """
        # 1. Liquidity scoring
        score = self.scorer.score(book, order_quantity=quantity, volatility=volatility)

        # 2. Market impact estimate
        impact = self.impact_engine.estimate(
            book=book, quantity=quantity, side=side, volatility=volatility,
        )

        # 3. Capacity analysis
        capacity = self.capacity_analyzer.analyze(
            book=book,
            strategy_id=strategy_id,
            price=price or book.mid_price,
            current_daily_notional=current_daily_notional,
            current_position=current_position,
        )

        # 4. Imbalance analysis
        imbalance = self.imbalance_estimator.analyze(book)

        # 5. Execution recommendation
        recommendation = self.imbalance_estimator.get_execution_recommendation(
            book=book, side=side, quantity=quantity,
        )

        # Override recommendation with impact-based analysis
        if impact.recommended_slices > 1:
            recommendation["recommended_algorithm"] = impact.recommended_algorithm
            recommendation["recommended_slices"] = impact.recommended_slices

        return {
            "symbol": book.symbol,
            "score": score.to_dict(),
            "impact": impact.to_dict(),
            "capacity": capacity.to_dict(),
            "imbalance": imbalance.to_dict(),
            "recommendation": recommendation,
        }

    def quick_evaluate(
        self,
        book: OrderBook,
        quantity: float = 0.0,
        side: Side = Side.BUY,
        volatility: float = 0.25,
    ) -> Dict[str, Any]:
        """Quick evaluation — score + recommendation only.

        Lighter version of evaluate() for real-time decision making.

        Args:
            book: Current order book
            quantity: Order quantity
            side: BUY or SELL
            volatility: Annualized volatility

        Returns:
            Dict with score, impact summary, and recommendation
        """
        score = self.scorer.score(book, order_quantity=quantity, volatility=volatility)
        impact = self.impact_engine.estimate(
            book=book, quantity=quantity, side=side, volatility=volatility,
        )
        recommendation = self.imbalance_estimator.get_execution_recommendation(
            book=book, side=side, quantity=quantity,
        )

        return {
            "symbol": book.symbol,
            "score": score.grade.value,
            "score_value": round(score.score, 2),
            "impact_bps": round(impact.total_cost_bps, 2),
            "impact_grade": impact.impact_grade.value,
            "recommended_algorithm": recommendation["recommended_algorithm"],
            "aggressiveness": recommendation["aggressiveness"],
            "urgency": recommendation["urgency"],
        }

    # -------------------------------------------------------------------------
    # Book Management (delegated)
    # -------------------------------------------------------------------------

    def update_book(
        self,
        symbol: str,
        bids: List[Tuple[float, float]],
        asks: List[Tuple[float, float]],
        last_price: float = 0.0,
        daily_volume: float = 0.0,
        adv: float = 0.0,
    ) -> OrderBook:
        """Update the order book for a symbol.

        Args:
            symbol: Trading symbol
            bids: List of (price, volume) bid levels
            asks: List of (price, volume) ask levels
            last_price: Last traded price
            daily_volume: Current day volume
            adv: Average daily volume

        Returns:
            Updated OrderBook
        """
        return self.book_manager.build_book(
            symbol=symbol,
            bids=bids,
            asks=asks,
            last_price=last_price,
            daily_volume=daily_volume,
            adv=adv,
        )

    def get_book(self, symbol: str) -> Optional[OrderBook]:
        """Get the current order book for a symbol."""
        return self.book_manager.get_book(symbol)

    def analyze_depth(self, book: OrderBook, order_quantity: float = 0.0) -> DepthAnalysis:
        """Analyze order book depth."""
        return self.depth_analyzer.analyze(book, order_quantity)
