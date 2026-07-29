"""TCA Benchmark — reference prices for execution quality measurement.

Provides benchmark price calculations:
- Arrival Price: Price at decision time
- VWAP: Volume-Weighted Average Price over execution period
- TWAP: Time-Weighted Average Price over execution period
- Close Price: End-of-day reference
- Implementation Shortfall: Arrival vs execution price
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple


@dataclass
class BenchmarkResult:
    """Benchmark prices for TCA analysis."""

    symbol: str
    arrival_price: float
    vwap: float = 0.0
    twap: float = 0.0
    close_price: float = 0.0
    open_price: float = 0.0
    high_price: float = 0.0
    low_price: float = 0.0
    volume: float = 0.0
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "arrival_price": self.arrival_price,
            "vwap": self.vwap,
            "twap": self.twap,
            "close_price": self.close_price,
            "open_price": self.open_price,
            "high_price": self.high_price,
            "low_price": self.low_price,
            "volume": self.volume,
        }


class BenchmarkCalculator:
    """Calculates benchmark prices for TCA.

    Supports multiple benchmark methodologies for comparing
    execution quality against different reference prices.
    """

    def compute_arrival_price(self, mid_price: float) -> float:
        """Arrival price = mid price at decision time.

        This is the most common benchmark for measuring
        implementation shortfall.
        """
        return mid_price

    def compute_vwap(
        self,
        prices: List[float],
        volumes: List[float],
    ) -> float:
        """Compute VWAP from price/volume series.

        VWAP = Σ(price_i × volume_i) / Σ(volume_i)
        """
        if not prices or not volumes or len(prices) != len(volumes):
            return 0.0

        total_value = sum(p * v for p, v in zip(prices, volumes))
        total_volume = sum(volumes)

        if total_volume <= 0:
            return 0.0

        return total_value / total_volume

    def compute_twap(self, prices: List[float]) -> float:
        """Compute TWAP from price series.

        TWAP = Σ(price_i) / N
        """
        if not prices:
            return 0.0
        return sum(prices) / len(prices)

    def compute_benchmarks(
        self,
        symbol: str,
        arrival_price: float,
        trade_prices: List[float],
        trade_volumes: Optional[List[float]] = None,
        open_price: float = 0.0,
        close_price: float = 0.0,
    ) -> BenchmarkResult:
        """Compute all benchmarks for a given execution.

        Args:
            symbol: Trading symbol.
            arrival_price: Price at decision time.
            trade_prices: List of market prices during execution.
            trade_volumes: Corresponding volumes (for VWAP).
            open_price: Day's open price.
            close_price: Day's close price.

        Returns:
            BenchmarkResult with all computed benchmarks.
        """
        vwap = 0.0
        twap = 0.0

        if trade_prices:
            twap = self.compute_twap(trade_prices)
            if trade_volumes and len(trade_volumes) == len(trade_prices):
                vwap = self.compute_vwap(trade_prices, trade_volumes)

        high = max(trade_prices) if trade_prices else arrival_price
        low = min(trade_prices) if trade_prices else arrival_price
        total_vol = sum(trade_volumes) if trade_volumes else 0.0

        return BenchmarkResult(
            symbol=symbol,
            arrival_price=arrival_price,
            vwap=vwap,
            twap=twap,
            close_price=close_price,
            open_price=open_price,
            high_price=high,
            low_price=low,
            volume=total_vol,
        )

    def compare_to_benchmark(
        self,
        execution_price: float,
        benchmark_price: float,
    ) -> dict:
        """Compare execution price to a benchmark.

        Returns slippage in basis points and cost assessment.
        """
        if benchmark_price <= 0:
            return {"slippage_bps": 0.0, "cost": "N/A", "beats_benchmark": False}

        slippage_bps = (
            (execution_price - benchmark_price) / benchmark_price * 10000
        )

        abs_slip = abs(slippage_bps)
        if abs_slip < 2:
            cost = "NEGLIGIBLE"
        elif abs_slip < 5:
            cost = "LOW"
        elif abs_slip < 15:
            cost = "MODERATE"
        else:
            cost = "HIGH"

        return {
            "slippage_bps": round(slippage_bps, 2),
            "cost": cost,
            "beats_benchmark": slippage_bps <= 0 if slippage_bps != 0 else True,
        }
