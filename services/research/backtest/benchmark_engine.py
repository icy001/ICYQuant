"""Benchmark Engine — benchmark data retrieval and return calculation.

Supports major benchmarks (SPY, QQQ, CSI300, etc.) and custom
benchmark definitions for computing excess returns.

Benchmarks::

    SPY → QQQ → CSI300 → Custom
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BenchmarkEngine:
    """Benchmark manager for backtesting performance comparison.

    Manages benchmark data (prices, returns) for computing
    excess returns and tracking error against market indices.

    Usage::

        engine = BenchmarkEngine()
        engine.set_benchmark_data("CSI300", returns)
        excess = engine.compute_excess_return(portfolio_return, "CSI300")
    """

    def __init__(self) -> None:
        self._benchmarks: Dict[str, Dict[str, Any]] = {}
        self._active_benchmark: str = "CSI300"

    # ── data management ────────────────────────────────────────────────────

    def set_benchmark_data(
        self,
        symbol: str,
        data: Dict[str, Any],
    ) -> None:
        """Set benchmark price/return data.

        Args:
            symbol: Benchmark symbol (e.g., SPY, CSI300).
            data: Dict with returns (list of floats), prices, dates, etc.
        """
        self._benchmarks[symbol] = {
            "symbol": symbol,
            "returns": data.get("returns", []),
            "prices": data.get("prices", []),
            "dates": data.get("dates", []),
            "label": data.get("label", symbol),
            "currency": data.get("currency", "CNY"),
        }
        logger.info("Benchmark data set for %s: %d periods", symbol, len(data.get("returns", [])))

    def set_active(self, symbol: str) -> None:
        """Set the active benchmark for comparisons."""
        self._active_benchmark = symbol
        logger.info("Active benchmark set to: %s", symbol)

    async def get_returns(
        self,
        symbol: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[float]:
        """Get benchmark returns for a period."""
        symbol = symbol or self._active_benchmark
        bm = self._benchmarks.get(symbol, {})
        returns = bm.get("returns", [])

        if start_date and end_date and "dates" in bm:
            dates = bm["dates"]
            start_idx = next((i for i, d in enumerate(dates) if d >= start_date), 0)
            end_idx = next((i for i, d in enumerate(dates) if d > end_date), len(dates))
            returns = returns[start_idx:end_idx]

        return returns

    # ── excess return ──────────────────────────────────────────────────────

    def compute_excess_return(
        self,
        portfolio_return: float,
        benchmark_return: float,
    ) -> float:
        """Compute excess return: portfolio - benchmark.

        Args:
            portfolio_return: Portfolio return (decimal).
            benchmark_return: Benchmark return (decimal).

        Returns:
            Excess return (decimal).
        """
        return portfolio_return - benchmark_return

    def compute_excess_returns(
        self,
        portfolio_returns: List[float],
        benchmark_symbol: Optional[str] = None,
    ) -> List[float]:
        """Compute excess returns for a series.

        Args:
            portfolio_returns: List of portfolio returns.
            benchmark_symbol: Optional benchmark override.

        Returns:
            List of excess returns.
        """
        symbol = benchmark_symbol or self._active_benchmark
        bm_returns = self._benchmarks.get(symbol, {}).get("returns", [])

        length = min(len(portfolio_returns), len(bm_returns))
        return [portfolio_returns[i] - bm_returns[i] for i in range(length)]

    def compute_tracking_error(
        self,
        portfolio_returns: List[float],
        benchmark_symbol: Optional[str] = None,
    ) -> float:
        """Compute annualized tracking error.

        Tracking error = std(portfolio_returns - benchmark_returns) * sqrt(periods).

        Args:
            portfolio_returns: List of portfolio returns.
            benchmark_symbol: Optional benchmark override.

        Returns:
            Annualized tracking error (decimal).
        """
        excess = self.compute_excess_returns(portfolio_returns, benchmark_symbol)
        if len(excess) < 2:
            return 0.0

        mean_excess = sum(excess) / len(excess)
        variance = sum((x - mean_excess) ** 2 for x in excess) / (len(excess) - 1)
        daily_te = variance ** 0.5

        # Annualize (assuming daily returns, 252 trading days)
        return daily_te * (252 ** 0.5)

    def compute_information_ratio(
        self,
        portfolio_returns: List[float],
        benchmark_symbol: Optional[str] = None,
    ) -> float:
        """Compute Information Ratio (excess return / tracking error)."""
        excess = self.compute_excess_returns(portfolio_returns, benchmark_symbol)
        if len(excess) < 2:
            return 0.0

        avg_excess = sum(excess) / len(excess)
        tracking_error = self.compute_tracking_error(portfolio_returns, benchmark_symbol)

        if tracking_error == 0:
            return 0.0
        return (avg_excess * 252) / tracking_error  # annualize numerator

    # ── query ──────────────────────────────────────────────────────────────

    def get_active_benchmark(self) -> str:
        """Get the active benchmark symbol."""
        return self._active_benchmark

    def list_benchmarks(self) -> List[str]:
        """List all available benchmark symbols."""
        return sorted(self._benchmarks.keys())

    def get_benchmark_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get full benchmark data for a symbol."""
        return self._benchmarks.get(symbol)

    def get_stats(self) -> Dict[str, Any]:
        """Return benchmark engine statistics."""
        bms = self._benchmarks
        return {
            "active": self._active_benchmark,
            "count": len(bms),
            "symbols": sorted(bms.keys()),
            "periods": max((len(b.get("returns", [])) for b in bms.values()), default=0),
        }
