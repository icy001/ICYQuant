"""TCA Analyzer — Transaction Cost Analysis engine.

Analyzes execution quality:
- Implementation Shortfall: Difference between decision price and execution price
- Slippage Analysis: Execution vs benchmark prices
- Cost Attribution: Breakdown of costs (commission, spread, impact, delay)
- Execution Quality Scoring
- Historical Performance Tracking
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..optimization.models import ExecutionOutcome, ExecutionQuality
from .benchmark import BenchmarkCalculator, BenchmarkResult


@dataclass
class TCAResult:
    """Full TCA analysis result."""

    order_id: str
    symbol: str
    side: str
    quantity: float
    arrival_price: float
    execution_price: float
    benchmark_vwap: float = 0.0
    benchmark_twap: float = 0.0
    implementation_shortfall_bps: float = 0.0
    arrival_slippage_bps: float = 0.0
    vwap_slippage_bps: float = 0.0
    twap_slippage_bps: float = 0.0
    spread_cost_bps: float = 0.0
    market_impact_bps: float = 0.0
    delay_cost_bps: float = 0.0
    commission_bps: float = 0.0
    total_cost_bps: float = 0.0
    total_cost_amount: float = 0.0
    quality: ExecutionQuality = ExecutionQuality.FAIR
    analysis_timestamp: datetime = field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "arrival_price": self.arrival_price,
            "execution_price": self.execution_price,
            "benchmark_vwap": self.benchmark_vwap,
            "benchmark_twap": self.benchmark_twap,
            "implementation_shortfall_bps": self.implementation_shortfall_bps,
            "arrival_slippage_bps": self.arrival_slippage_bps,
            "vwap_slippage_bps": self.vwap_slippage_bps,
            "twap_slippage_bps": self.twap_slippage_bps,
            "spread_cost_bps": self.spread_cost_bps,
            "market_impact_bps": self.market_impact_bps,
            "delay_cost_bps": self.delay_cost_bps,
            "commission_bps": self.commission_bps,
            "total_cost_bps": self.total_cost_bps,
            "total_cost_amount": self.total_cost_amount,
            "quality": self.quality.value,
            "details": self.details,
        }


class TCAAnalyzer:
    """Transaction Cost Analysis engine.

    Measures and attributes the full cost of executing an order,
    breaking it down into components:
    - Commission: Explicit broker fees
    - Spread: Half the bid-ask spread
    - Market Impact: Price movement caused by the order
    - Delay: Cost of waiting to execute
    - Slippage: Execution vs benchmark price
    """

    def __init__(self):
        self.benchmark_calc = BenchmarkCalculator()
        self._history: List[TCAResult] = []

    def analyze(
        self,
        order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        arrival_price: float,
        execution_price: float,
        benchmark_vwap: float = 0.0,
        benchmark_twap: float = 0.0,
        spread_bps: float = 0.0,
        commission: float = 0.0,
        expected_impact_bps: float = 0.0,
        market_prices: Optional[List[float]] = None,
        market_volumes: Optional[List[float]] = None,
    ) -> TCAResult:
        """Perform full TCA analysis on an execution.

        Args:
            order_id: Order identifier.
            symbol: Trading symbol.
            side: BUY or SELL.
            quantity: Executed quantity.
            arrival_price: Price at decision time.
            execution_price: Volume-weighted average execution price.
            benchmark_vwap: Market VWAP over execution period.
            benchmark_twap: Market TWAP over execution period.
            spread_bps: Bid-ask spread in basis points.
            commission: Total commission paid.
            expected_impact_bps: Pre-trade impact estimate.
            market_prices: Market price series during execution.
            market_volumes: Corresponding volume series.

        Returns:
            TCAResult with full cost breakdown.
        """
        notional = execution_price * quantity

        # 1. Implementation Shortfall (arrival price vs execution price)
        if arrival_price > 0:
            is_buy = side.upper() == "BUY"
            price_diff = execution_price - arrival_price
            if not is_buy:
                price_diff = -price_diff  # For sells, we want lower prices
            impl_shortfall_bps = (price_diff / arrival_price) * 10000
        else:
            impl_shortfall_bps = 0.0

        # 2. Arrival slippage
        if arrival_price > 0:
            arrival_slip = (
                (execution_price - arrival_price) / arrival_price * 10000
            )
        else:
            arrival_slip = 0.0

        # 3. VWAP slippage
        vwap_slip = 0.0
        if benchmark_vwap > 0:
            vwap_slip = (
                (execution_price - benchmark_vwap) / benchmark_vwap * 10000
            )

        # 4. TWAP slippage
        twap_slip = 0.0
        if benchmark_twap > 0:
            twap_slip = (
                (execution_price - benchmark_twap) / benchmark_twap * 10000
            )

        # 5. Spread cost (half spread per trade)
        spread_cost = spread_bps / 2.0

        # 6. Commission in bps
        comm_bps = 0.0
        if notional > 0:
            comm_bps = commission / notional * 10000

        # 7. Market impact (estimated)
        impact_bps = expected_impact_bps

        # 8. Delay cost (remaining unexplained cost)
        delay_cost = abs(arrival_slip) - spread_cost - impact_bps - comm_bps
        delay_cost = max(0.0, delay_cost)

        # 9. Total cost
        total_cost_bps = abs(arrival_slip) + comm_bps
        total_cost_amount = total_cost_bps / 10000 * notional

        # 10. Quality assessment
        quality = self._assess_quality(
            impl_shortfall_bps=abs(impl_shortfall_bps),
            vwap_slip=abs(vwap_slip),
        )

        result = TCAResult(
            order_id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            arrival_price=arrival_price,
            execution_price=execution_price,
            benchmark_vwap=benchmark_vwap,
            benchmark_twap=benchmark_twap,
            implementation_shortfall_bps=round(impl_shortfall_bps, 2),
            arrival_slippage_bps=round(arrival_slip, 2),
            vwap_slippage_bps=round(vwap_slip, 2),
            twap_slippage_bps=round(twap_slip, 2),
            spread_cost_bps=round(spread_cost, 2),
            market_impact_bps=round(impact_bps, 2),
            delay_cost_bps=round(delay_cost, 2),
            commission_bps=round(comm_bps, 2),
            total_cost_bps=round(total_cost_bps, 2),
            total_cost_amount=round(total_cost_amount, 2),
            quality=quality,
        )

        self._history.append(result)
        return result

    def analyze_from_outcome(
        self,
        outcome: ExecutionOutcome,
        spread_bps: float = 0.0,
        commission: float = 0.0,
    ) -> TCAResult:
        """Analyze from an ExecutionOutcome object.

        Args:
            outcome: Execution outcome from the optimizer.
            spread_bps: Bid-ask spread in bps.
            commission: Total commission.

        Returns:
            TCAResult with full analysis.
        """
        return self.analyze(
            order_id=outcome.order_id,
            symbol="",  # Not in outcome, use plan
            side="BUY",
            quantity=outcome.executed_quantity,
            arrival_price=outcome.arrival_price,
            execution_price=outcome.average_price,
            benchmark_vwap=outcome.vwap_price,
            spread_bps=spread_bps,
            commission=commission or outcome.commission,
            expected_impact_bps=outcome.impact_bps,
        )

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get aggregate statistics from historical analyses.

        Returns:
            Dict with summary statistics.
        """
        if not self._history:
            return {
                "total_orders": 0,
                "message": "No TCA history available",
            }

        costs = [r.total_cost_bps for r in self._history]
        shortfalls = [r.implementation_shortfall_bps for r in self._history]

        qualities = [r.quality for r in self._history]
        excellent = sum(1 for q in qualities if q == ExecutionQuality.EXCELLENT)
        good = sum(1 for q in qualities if q == ExecutionQuality.GOOD)
        fair = sum(1 for q in qualities if q == ExecutionQuality.FAIR)
        poor = sum(1 for q in qualities if q == ExecutionQuality.POOR)

        return {
            "total_orders": len(self._history),
            "avg_cost_bps": round(sum(costs) / len(costs), 2),
            "min_cost_bps": round(min(costs), 2),
            "max_cost_bps": round(max(costs), 2),
            "avg_shortfall_bps": round(sum(shortfalls) / len(shortfalls), 2),
            "quality_distribution": {
                "EXCELLENT": excellent,
                "GOOD": good,
                "FAIR": fair,
                "POOR": poor,
            },
            "excellent_rate": f"{excellent / len(self._history):.1%}",
        }

    def _assess_quality(
        self,
        impl_shortfall_bps: float,
        vwap_slip: float,
    ) -> ExecutionQuality:
        """Assess execution quality from TCA metrics."""
        combined = impl_shortfall_bps + abs(vwap_slip)

        if combined < 3.0:
            return ExecutionQuality.EXCELLENT
        elif combined < 8.0:
            return ExecutionQuality.GOOD
        elif combined < 20.0:
            return ExecutionQuality.FAIR
        else:
            return ExecutionQuality.POOR

    def clear_history(self):
        """Clear TCA history."""
        self._history.clear()
