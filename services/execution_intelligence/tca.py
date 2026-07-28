"""Transaction Cost Analysis – post-trade execution quality measurement."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class TCAResult:
    """Result of a transaction cost analysis."""

    symbol: str
    side: str = ""
    quantity: int = 0

    # Price comparison
    expected_price: float = 0.0
    actual_price: float = 0.0

    # Cost breakdown (in basis points)
    spread_cost_bps: float = 0.0
    slippage_cost_bps: float = 0.0
    market_impact_bps: float = 0.0
    timing_cost_bps: float = 0.0
    total_cost_bps: float = 0.0

    # Notional
    notional_value: float = 0.0
    cost_in_currency: float = 0.0

    # Quality
    execution_quality: str = "unknown"  # "excellent", "good", "fair", "poor"
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "expected_price": self.expected_price,
            "actual_price": self.actual_price,
            "spread_cost_bps": self.spread_cost_bps,
            "slippage_cost_bps": self.slippage_cost_bps,
            "market_impact_bps": self.market_impact_bps,
            "timing_cost_bps": self.timing_cost_bps,
            "total_cost_bps": self.total_cost_bps,
            "notional_value": self.notional_value,
            "cost_in_currency": self.cost_in_currency,
            "execution_quality": self.execution_quality,
            "notes": self.notes,
        }


class TransactionCostAnalyzer:
    """Analyzes execution quality by comparing expected vs actual prices.

    Decomposes total cost into:
    - Spread cost: crossing the bid-ask spread
    - Slippage cost: deviation from expected due to adverse price movement
    - Market impact: price moved by own order
    - Timing cost: cost of delay between decision and execution
    """

    def __init__(
        self,
        benchmark: str = "arrival",  # "arrival", "VWAP", "close"
    ):
        self.benchmark = benchmark

    def analyze(
        self,
        expected: float,
        actual: float,
        symbol: str = "",
        side: str = "",
        quantity: int = 0,
        arrival_price: Optional[float] = None,
        vwap_price: Optional[float] = None,
        spread_bps: float = 2.0,
    ) -> float:
        """Quick analysis: return the total cost in basis points."""
        result = self.analyze_detailed(
            expected=expected,
            actual=actual,
            symbol=symbol,
            side=side,
            quantity=quantity,
            arrival_price=arrival_price,
            vwap_price=vwap_price,
            spread_bps=spread_bps,
        )
        return result.total_cost_bps

    def analyze_detailed(
        self,
        expected: float,
        actual: float,
        symbol: str = "",
        side: str = "",
        quantity: int = 0,
        arrival_price: Optional[float] = None,
        vwap_price: Optional[float] = None,
        spread_bps: float = 2.0,
    ) -> TCAResult:
        """Full transaction cost analysis with decomposition.

        Args:
            expected: Expected / decision price.
            actual: Actual fill price.
            symbol: Instrument symbol.
            side: "BUY" or "SELL".
            quantity: Number of shares.
            arrival_price: Price when order arrived at market.
            vwap_price: VWAP price during execution.
            spread_bps: Estimated bid-ask spread in bps.
        """
        if expected <= 0:
            return TCAResult(
                symbol=symbol,
                side=side,
                quantity=quantity,
                expected_price=expected,
                actual_price=actual,
                total_cost_bps=0.0,
                execution_quality="unknown",
                notes="Invalid expected price.",
            )

        arrival = arrival_price if arrival_price is not None else expected
        vwap = vwap_price if vwap_price is not None else expected

        # Direction: for BUY, higher actual = worse; for SELL, lower actual = worse
        direction = 1 if side.upper() == "BUY" else -1

        # Total slippage: (actual - expected) in bps, signed for direction
        price_diff = (actual - expected) * direction
        total_bps = round(price_diff / expected * 10000, 2)

        # Spread cost: half-spread as unavoidable cost
        spread_cost = spread_bps / 2.0

        # Market impact: actual vs arrival (price moved due to our order)
        impact_diff = (actual - arrival) * direction
        impact_bps = round(impact_diff / expected * 10000, 2)

        # Slippage: residual after removing spread and impact
        slippage_bps = round(max(total_bps - spread_cost - impact_bps, 0.0), 2)

        # Timing cost: arrival vs decision (cost of delay)
        timing_diff = (arrival - expected) * direction
        timing_bps = round(timing_diff / expected * 10000, 2)

        # Execution quality rating
        if total_bps < 1.0:
            quality = "excellent"
        elif total_bps < 5.0:
            quality = "good"
        elif total_bps < 15.0:
            quality = "fair"
        else:
            quality = "poor"

        notional = quantity * actual
        cost_currency = round(notional * total_bps / 10000, 2)

        return TCAResult(
            symbol=symbol,
            side=side,
            quantity=quantity,
            expected_price=expected,
            actual_price=actual,
            spread_cost_bps=round(spread_cost, 2),
            slippage_cost_bps=slippage_bps,
            market_impact_bps=impact_bps,
            timing_cost_bps=timing_bps,
            total_cost_bps=total_bps,
            notional_value=round(notional, 2),
            cost_in_currency=cost_currency,
            execution_quality=quality,
            notes=self._generate_notes(quality, total_bps),
        )

    def analyze_batch(
        self,
        trades: List[dict],
    ) -> List[TCAResult]:
        """Analyze a batch of trades."""
        results = []
        for t in trades:
            result = self.analyze_detailed(
                expected=t.get("expected", 0.0),
                actual=t.get("actual", 0.0),
                symbol=t.get("symbol", ""),
                side=t.get("side", ""),
                quantity=t.get("quantity", 0),
                arrival_price=t.get("arrival_price"),
                spread_bps=t.get("spread_bps", 2.0),
            )
            results.append(result)
        return results

    def summary(self, results: List[TCAResult]) -> dict:
        """Generate a summary across multiple TCA results."""
        if not results:
            return {"total_trades": 0, "avg_cost_bps": 0.0,
                    "total_cost_currency": 0.0}

        total_cost = sum(r.total_cost_bps for r in results)
        total_currency = sum(r.cost_in_currency for r in results)
        avg_cost = round(total_cost / len(results), 2)

        quality_counts = {"excellent": 0, "good": 0, "fair": 0, "poor": 0}
        for r in results:
            quality_counts[r.execution_quality] += 1

        return {
            "total_trades": len(results),
            "avg_cost_bps": avg_cost,
            "total_cost_currency": round(total_currency, 2),
            "quality_distribution": quality_counts,
            "best_trade": min(results, key=lambda r: r.total_cost_bps).to_dict() if results else None,
            "worst_trade": max(results, key=lambda r: r.total_cost_bps).to_dict() if results else None,
        }

    def _generate_notes(self, quality: str, total_bps: float) -> str:
        """Generate human-readable notes about execution quality."""
        if quality == "excellent":
            return f"Execution within {total_bps:.1f} bps – minimal cost."
        elif quality == "good":
            return f"Acceptable execution at {total_bps:.1f} bps."
        elif quality == "fair":
            return f"Moderate cost of {total_bps:.1f} bps – review strategy."
        else:
            return f"High execution cost ({total_bps:.1f} bps) – urgent review needed."
