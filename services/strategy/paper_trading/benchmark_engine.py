"""
Benchmark Engine
================
Computes benchmark returns for strategy performance comparison.

Supported benchmarks:
    - SPY / S&P 500
    - Custom index
    - Risk-free rate
    - Peer group (placeholder)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BenchmarkType(str, Enum):
    SP500 = "SP500"
    NASDAQ = "NASDAQ"
    CUSTOM = "CUSTOM"
    RISK_FREE = "RISK_FREE"
    PEER_GROUP = "PEER_GROUP"


@dataclass
class BenchmarkResult:
    """Benchmark return data for a period."""
    benchmark_type: BenchmarkType = BenchmarkType.SP500
    symbol: str = ""
    period_return: float = 0.0
    annualized_return: float = 0.0
    annualized_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    data_points: int = 0


class BenchmarkEngine:
    """Computes benchmark returns for strategy comparison."""

    def __init__(self):
        self._price_series: Dict[str, List[float]] = {}
        self._risk_free_rate: float = 0.03  # 3% annual
        self.is_initialized = False

    async def initialize(self) -> None:
        self.is_initialized = True
        logger.info("BenchmarkEngine initialized")

    # ------------------------------------------------------------------
    # Data Loading
    # ------------------------------------------------------------------

    async def load_prices(self, symbol: str, prices: List[float]) -> None:
        """Load a price series for a benchmark symbol."""
        self._price_series[symbol] = prices
        logger.info("Benchmark prices loaded for %s: %d data points", symbol, len(prices))

    # ------------------------------------------------------------------
    # Computation
    # ------------------------------------------------------------------

    async def compute_returns(self, symbol: str) -> BenchmarkResult:
        """Compute benchmark returns from price series."""
        prices = self._price_series.get(symbol, [])
        if len(prices) < 2:
            return BenchmarkResult(benchmark_type=BenchmarkType.CUSTOM, symbol=symbol)

        returns = []
        peak = prices[0]
        max_dd = 0.0

        for i in range(1, len(prices)):
            r = (prices[i] - prices[i-1]) / prices[i-1] if prices[i-1] > 0 else 0.0
            returns.append(r)

            if prices[i] > peak:
                peak = prices[i]
            dd = (peak - prices[i]) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd

        if not returns:
            return BenchmarkResult(benchmark_type=BenchmarkType.CUSTOM, symbol=symbol)

        total_return = (prices[-1] / prices[0] - 1) if prices[0] > 0 else 0.0
        mean_r = sum(returns) / len(returns)
        variance = sum((r - mean_r) ** 2 for r in returns) / len(returns)
        std = variance ** 0.5

        # Annualize (assuming daily data, 252 trading days)
        ann_return = (1 + total_return) ** (252 / len(returns)) - 1
        ann_vol = std * (252 ** 0.5)
        sharpe = (
            (ann_return - self._risk_free_rate) / ann_vol if ann_vol > 0 else 0.0
        )

        return BenchmarkResult(
            benchmark_type=BenchmarkType.CUSTOM,
            symbol=symbol,
            period_return=total_return,
            annualized_return=ann_return,
            annualized_volatility=ann_vol,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            data_points=len(prices),
        )

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_risk_free_rate(self, rate: float) -> None:
        self._risk_free_rate = rate

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "risk_free_rate": self._risk_free_rate,
            "benchmarks_loaded": len(self._price_series),
            "symbols": list(self._price_series.keys()),
        }
