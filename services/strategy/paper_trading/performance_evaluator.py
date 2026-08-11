"""
Performance Evaluator
=====================
Evaluates strategy performance from paper trading results.

Metrics:
    Total Return, Sharpe Ratio, Sortino Ratio, Max Drawdown,
    Win Rate, Profit Factor, Calmar Ratio, Turnover, CAGR
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Core performance metrics."""
    total_return: float = 0.0
    annualized_return: float = 0.0
    cagr: float = 0.0
    annualized_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    turnover: float = 0.0
    avg_holding_period_days: float = 0.0
    information_ratio: float = 0.0
    alpha: float = 0.0
    beta: float = 0.0
    var_95: float = 0.0
    cvar_95: float = 0.0


@dataclass
class PerformanceReport:
    """Full performance evaluation report."""
    report_id: str = ""
    strategy_id: str = ""
    session_id: str = ""
    metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    benchmark_return: float = 0.0
    excess_return: float = 0.0
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "strategy_id": self.strategy_id,
            "session_id": self.session_id,
            "metrics": {
                "total_return": round(self.metrics.total_return, 6),
                "annualized_return": round(self.metrics.annualized_return, 6),
                "cagr": round(self.metrics.cagr, 6),
                "sharpe_ratio": round(self.metrics.sharpe_ratio, 4),
                "sortino_ratio": round(self.metrics.sortino_ratio, 4),
                "calmar_ratio": round(self.metrics.calmar_ratio, 4),
                "max_drawdown": round(self.metrics.max_drawdown, 6),
                "win_rate": round(self.metrics.win_rate, 4),
                "profit_factor": round(self.metrics.profit_factor, 4),
                "total_trades": self.metrics.total_trades,
                "alpha": round(self.metrics.alpha, 6),
                "beta": round(self.metrics.beta, 4),
            },
            "benchmark_return": round(self.benchmark_return, 6),
            "excess_return": round(self.excess_return, 6),
            "generated_at": self.generated_at.isoformat(),
        }


class PerformanceEvaluator:
    """Evaluates strategy performance from paper trading results."""

    def __init__(self):
        self._risk_free_rate: float = 0.03
        self._trading_days_per_year: int = 252
        self.is_initialized = False

    async def initialize(self) -> None:
        self.is_initialized = True
        logger.info("PerformanceEvaluator initialized")

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    async def evaluate(self, returns: List[float],
                       benchmark_returns: Optional[List[float]] = None,
                       trades: Optional[List[Dict[str, Any]]] = None,
                       ) -> PerformanceReport:
        """Compute full performance metrics from return series."""
        if not returns:
            return PerformanceReport()

        metrics = PerformanceMetrics()

        n = len(returns)
        metrics.total_return = self._total_return(returns)
        metrics.annualized_return = self._annualize_return(metrics.total_return, n)
        metrics.cagr = metrics.annualized_return

        # Volatility
        mean_r = sum(returns) / n
        variance = sum((r - mean_r) ** 2 for r in returns) / n
        std = variance ** 0.5
        metrics.annualized_volatility = std * (self._trading_days_per_year ** 0.5)

        # Sharpe
        metrics.sharpe_ratio = (
            (metrics.annualized_return - self._risk_free_rate) / metrics.annualized_volatility
            if metrics.annualized_volatility > 0 else 0.0
        )

        # Sortino
        downside_returns = [r for r in returns if r < 0]
        downside_std = (
            (sum((r ** 2) for r in downside_returns) / n) ** 0.5
            if downside_returns else 0.0
        )
        ann_downside = downside_std * (self._trading_days_per_year ** 0.5)
        metrics.sortino_ratio = (
            (metrics.annualized_return - self._risk_free_rate) / ann_downside
            if ann_downside > 0 else 0.0
        )

        # Max Drawdown
        metrics.max_drawdown = self._max_drawdown(returns)

        # Calmar
        metrics.calmar_ratio = (
            metrics.annualized_return / abs(metrics.max_drawdown)
            if metrics.max_drawdown != 0 else 0.0
        )

        # Trade analysis
        if trades:
            metrics.total_trades = len(trades)
            winning = [t for t in trades if t.get("pnl", 0) > 0]
            losing = [t for t in trades if t.get("pnl", 0) < 0]
            metrics.winning_trades = len(winning)
            metrics.losing_trades = len(losing)
            metrics.win_rate = len(winning) / len(trades) if trades else 0.0
            metrics.avg_win = (
                sum(t["pnl"] for t in winning) / len(winning) if winning else 0.0
            )
            metrics.avg_loss = (
                abs(sum(t["pnl"] for t in losing)) / len(losing) if losing else 0.0
            )
            metrics.profit_factor = (
                metrics.avg_win * len(winning) / (metrics.avg_loss * len(losing))
                if metrics.avg_loss > 0 and losing else float('inf')
            )

        # VaR / CVaR
        sorted_returns = sorted(returns)
        var_idx = int(n * 0.05)
        metrics.var_95 = abs(sorted_returns[var_idx]) if var_idx < n else 0.0
        tail = sorted_returns[:var_idx + 1]
        metrics.cvar_95 = abs(sum(tail) / len(tail)) if tail else 0.0

        # Benchmark comparison
        benchmark_return = 0.0
        if benchmark_returns:
            benchmark_return = self._total_return(benchmark_returns)

            # Beta and Alpha
            if len(benchmark_returns) == len(returns):
                bench_mean = sum(benchmark_returns) / len(benchmark_returns)
                cov = sum(
                    (returns[i] - mean_r) * (benchmark_returns[i] - bench_mean)
                    for i in range(n)
                ) / n
                bench_var = sum(
                    (r - bench_mean) ** 2 for r in benchmark_returns
                ) / n
                metrics.beta = cov / bench_var if bench_var > 0 else 1.0
                metrics.alpha = metrics.annualized_return - (
                    self._risk_free_rate + metrics.beta * (
                        self._annualize_return(benchmark_return, n) - self._risk_free_rate
                    )
                )

        return PerformanceReport(
            report_id=f"perf_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            metrics=metrics,
            benchmark_return=benchmark_return,
            excess_return=metrics.total_return - benchmark_return,
        )

    async def evaluate_session(self, session_id: str) -> PerformanceReport:
        """Evaluate a paper trading session."""
        # Placeholder: in production, load returns from session
        return PerformanceReport(
            session_id=session_id,
        )

    # ------------------------------------------------------------------
    # Internal Calculations
    # ------------------------------------------------------------------

    def _total_return(self, returns: List[float]) -> float:
        cumulative = 1.0
        for r in returns:
            cumulative *= (1 + r)
        return cumulative - 1.0

    def _annualize_return(self, total_return: float, periods: int) -> float:
        if periods <= 0 or total_return <= -1.0:
            return 0.0
        return (1 + total_return) ** (self._trading_days_per_year / periods) - 1

    def _max_drawdown(self, returns: List[float]) -> float:
        peak = 0.0
        cumulative = 1.0
        max_dd = 0.0
        for r in returns:
            cumulative *= (1 + r)
            if cumulative > peak:
                peak = cumulative
            dd = (peak - cumulative) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
        return max_dd

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_risk_free_rate(self, rate: float) -> None:
        self._risk_free_rate = rate

    def set_trading_days(self, days: int) -> None:
        self._trading_days_per_year = days

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "risk_free_rate": self._risk_free_rate,
            "trading_days_per_year": self._trading_days_per_year,
        }
