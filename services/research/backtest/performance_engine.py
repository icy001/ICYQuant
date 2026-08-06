"""Performance Engine — comprehensive backtest performance analysis.

Computes standard institutional performance metrics for evaluating
strategy and portfolio performance.

Metrics::

    Return → Volatility → Sharpe → Sortino → Calmar → Max Drawdown
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .backtest_context import BacktestContext

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics for a backtest."""

    # Returns
    total_return: float = 0.0
    annual_return: float = 0.0
    cumulative_return: float = 0.0

    # Risk
    volatility: float = 0.0  # annualized
    downside_volatility: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0  # days
    var_95: float = 0.0  # Value at Risk 95%
    cvar_95: float = 0.0  # Conditional VaR
    skewness: float = 0.0
    kurtosis: float = 0.0

    # Risk-adjusted ratios
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    information_ratio: float = 0.0

    # Trading
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_trade_return: float = 0.0
    total_trades: int = 0

    # Benchmark
    benchmark_return: float = 0.0
    excess_return: float = 0.0
    tracking_error: float = 0.0
    beta: float = 0.0
    alpha: float = 0.0  # Jensen's alpha

    # Summary
    start_date: str = ""
    end_date: str = ""
    total_days: int = 0
    final_equity: float = 0.0
    best_day: float = 0.0
    worst_day: float = 0.0
    positive_days: int = 0
    negative_days: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            # Returns
            "total_return": self.total_return,
            "annual_return": self.annual_return,
            "cumulative_return": self.cumulative_return,
            # Risk
            "volatility": self.volatility,
            "downside_volatility": self.downside_volatility,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_duration": self.max_drawdown_duration,
            "var_95": self.var_95,
            "cvar_95": self.cvar_95,
            "skewness": self.skewness,
            "kurtosis": self.kurtosis,
            # Ratios
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "information_ratio": self.information_ratio,
            # Trading
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "avg_trade_return": self.avg_trade_return,
            "total_trades": self.total_trades,
            # Benchmark
            "benchmark_return": self.benchmark_return,
            "excess_return": self.excess_return,
            "tracking_error": self.tracking_error,
            "beta": self.beta,
            "alpha": self.alpha,
            # Summary
            "start_date": self.start_date,
            "end_date": self.end_date,
            "total_days": self.total_days,
            "final_equity": self.final_equity,
            "best_day": self.best_day,
            "worst_day": self.worst_day,
            "positive_days": self.positive_days,
            "negative_days": self.negative_days,
        }


class PerformanceEngine:
    """Comprehensive performance analysis engine.

    Computes institutional-grade performance metrics including
    risk-adjusted ratios, drawdown analysis, and VaR estimates.

    Usage::

        engine = PerformanceEngine()
        metrics = await engine.compute(equity_curve, trades, ctx)
    """

    def __init__(self, trading_days_per_year: int = 252) -> None:
        self._trading_days = trading_days_per_year

    # ── computation ────────────────────────────────────────────────────────

    async def compute(
        self,
        equity_curve: List[Dict[str, Any]],
        trades: List[Dict[str, Any]],
        ctx: Optional[BacktestContext] = None,
        benchmark_returns: Optional[List[float]] = None,
    ) -> PerformanceMetrics:
        """Compute all performance metrics.

        Args:
            equity_curve: List of {timestamp, equity, cash} per period.
            trades: List of trade records.
            ctx: Backtest context.
            benchmark_returns: Optional benchmark return series.

        Returns:
            Comprehensive PerformanceMetrics.
        """
        if not equity_curve:
            return PerformanceMetrics()

        # Extract equity values and compute returns
        equity_values = [e["equity"] for e in equity_curve]
        returns = self._compute_returns(equity_values)
        total_days = len(returns)

        metrics = PerformanceMetrics()
        metrics.total_days = total_days
        metrics.start_date = equity_curve[0].get("timestamp", "")
        metrics.end_date = equity_curve[-1].get("timestamp", "")
        metrics.final_equity = equity_values[-1]

        # Return metrics
        metrics.total_return = (equity_values[-1] / equity_values[0] - 1) if equity_values[0] > 0 else 0
        metrics.cumulative_return = metrics.total_return
        metrics.annual_return = self._compute_annual_return(metrics.total_return, total_days)

        # Daily stats
        metrics.best_day = max(returns) if returns else 0
        metrics.worst_day = min(returns) if returns else 0
        metrics.positive_days = sum(1 for r in returns if r > 0)
        metrics.negative_days = sum(1 for r in returns if r < 0)

        # Risk metrics
        metrics.volatility = self._compute_volatility(returns)
        metrics.downside_volatility = self._compute_downside_volatility(returns)
        self._compute_drawdown(equity_values, metrics)
        metrics.var_95 = self._compute_var(returns, 0.95)
        metrics.cvar_95 = self._compute_cvar(returns, 0.95)
        metrics.skewness = self._compute_skewness(returns)
        metrics.kurtosis = self._compute_kurtosis(returns)

        # Risk-adjusted ratios
        metrics.sharpe_ratio = self._compute_sharpe(metrics.annual_return, metrics.volatility)
        metrics.sortino_ratio = self._compute_sortino(metrics.annual_return, metrics.downside_volatility)
        metrics.calmar_ratio = self._compute_calmar(metrics.annual_return, metrics.max_drawdown)

        # Trade statistics
        self._compute_trade_stats(trades, metrics)

        # Benchmark comparison
        if benchmark_returns:
            self._compute_benchmark_metrics(returns, benchmark_returns, metrics)

        return metrics

    # ── return methods ─────────────────────────────────────────────────────

    def _compute_returns(self, equity_values: List[float]) -> List[float]:
        """Compute period returns from equity curve."""
        if len(equity_values) < 2:
            return []
        returns = []
        for i in range(1, len(equity_values)):
            if equity_values[i - 1] != 0:
                r = (equity_values[i] - equity_values[i - 1]) / equity_values[i - 1]
            else:
                r = 0.0
            returns.append(r)
        return returns

    def _compute_annual_return(self, total_return: float, days: int) -> float:
        """Annualize total return."""
        if days <= 0:
            return 0.0
        return (1 + total_return) ** (self._trading_days / days) - 1

    # ── risk methods ───────────────────────────────────────────────────────

    def _compute_volatility(self, returns: List[float]) -> float:
        """Compute annualized volatility."""
        if len(returns) < 2:
            return 0.0
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        daily_vol = math.sqrt(variance)
        return daily_vol * math.sqrt(self._trading_days)

    def _compute_downside_volatility(self, returns: List[float]) -> float:
        """Compute downside (semi) volatility."""
        negative = [r for r in returns if r < 0]
        if len(negative) < 2:
            return 0.0
        mean = sum(negative) / len(negative)
        variance = sum((r - mean) ** 2 for r in negative) / (len(negative) - 1)
        return math.sqrt(variance) * math.sqrt(self._trading_days)

    def _compute_drawdown(
        self,
        equity_values: List[float],
        metrics: PerformanceMetrics,
    ) -> None:
        """Compute maximum drawdown and duration."""
        if not equity_values:
            return

        peak = equity_values[0]
        max_dd = 0.0
        dd_start = 0
        max_dd_duration = 0
        current_dd_duration = 0

        for i, val in enumerate(equity_values):
            if val > peak:
                peak = val
                current_dd_duration = 0
            else:
                dd = (peak - val) / peak if peak > 0 else 0
                current_dd_duration += 1
                if dd > max_dd:
                    max_dd = dd
                    max_dd_duration = current_dd_duration

        metrics.max_drawdown = max_dd
        metrics.max_drawdown_duration = max_dd_duration

    def _compute_var(self, returns: List[float], confidence: float = 0.95) -> float:
        """Compute Value at Risk (historical method)."""
        if not returns:
            return 0.0
        sorted_returns = sorted(returns)
        idx = int(len(sorted_returns) * (1 - confidence))
        return abs(sorted_returns[idx]) if idx < len(sorted_returns) else 0.0

    def _compute_cvar(self, returns: List[float], confidence: float = 0.95) -> float:
        """Compute Conditional VaR (expected shortfall)."""
        if not returns:
            return 0.0
        sorted_returns = sorted(returns)
        idx = int(len(sorted_returns) * (1 - confidence))
        tail = sorted_returns[:idx]
        if not tail:
            return 0.0
        return abs(sum(tail) / len(tail))

    def _compute_skewness(self, returns: List[float]) -> float:
        """Compute return distribution skewness."""
        if len(returns) < 3:
            return 0.0
        mean = sum(returns) / len(returns)
        n = len(returns)
        m2 = sum((r - mean) ** 2 for r in returns) / n
        m3 = sum((r - mean) ** 3 for r in returns) / n
        if m2 == 0:
            return 0.0
        return m3 / (m2 ** 1.5)

    def _compute_kurtosis(self, returns: List[float]) -> float:
        """Compute excess kurtosis."""
        if len(returns) < 4:
            return 0.0
        mean = sum(returns) / len(returns)
        n = len(returns)
        m2 = sum((r - mean) ** 2 for r in returns) / n
        m4 = sum((r - mean) ** 4 for r in returns) / n
        if m2 == 0:
            return 0.0
        return (m4 / (m2 ** 2)) - 3  # excess kurtosis

    # ── ratio methods ──────────────────────────────────────────────────────

    def _compute_sharpe(self, annual_return: float, volatility: float, risk_free: float = 0.02) -> float:
        """Compute Sharpe ratio."""
        if volatility == 0:
            return 0.0
        return (annual_return - risk_free) / volatility

    def _compute_sortino(self, annual_return: float, downside_vol: float, risk_free: float = 0.02) -> float:
        """Compute Sortino ratio."""
        if downside_vol == 0:
            return 0.0
        return (annual_return - risk_free) / downside_vol

    def _compute_calmar(self, annual_return: float, max_drawdown: float) -> float:
        """Compute Calmar ratio."""
        if max_drawdown == 0:
            return 0.0
        return annual_return / max_drawdown

    # ── trade stats ────────────────────────────────────────────────────────

    def _compute_trade_stats(
        self,
        trades: List[Dict[str, Any]],
        metrics: PerformanceMetrics,
    ) -> None:
        """Compute trade-level statistics."""
        if not trades:
            return

        # Pair buys and sells
        buy_sell_pairs = self._pair_trades(trades)
        if not buy_sell_pairs:
            metrics.total_trades = len(trades)
            return

        returns_list: List[float] = []
        wins = 0
        losses = 0
        gross_profit = 0.0
        gross_loss = 0.0

        for pair in buy_sell_pairs:
            buy_price = pair["buy"]["price"]
            sell_price = pair["sell"]["price"]
            qty = pair["buy"]["quantity"]
            pnl = (sell_price - buy_price) * qty
            ret = (sell_price / buy_price - 1) if buy_price > 0 else 0

            returns_list.append(ret)
            if pnl > 0:
                wins += 1
                gross_profit += pnl
            else:
                losses += 1
                gross_loss += abs(pnl)

        total = wins + losses
        metrics.total_trades = total
        metrics.win_rate = wins / total if total > 0 else 0
        metrics.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
        metrics.avg_win = gross_profit / wins if wins > 0 else 0
        metrics.avg_loss = gross_loss / losses if losses > 0 else 0
        metrics.avg_trade_return = sum(returns_list) / len(returns_list) if returns_list else 0

    @staticmethod
    def _pair_trades(
        trades: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Pair buy and sell trades for P&L calculation."""
        pairs = []
        symbol_queue: Dict[str, List[Dict[str, Any]]] = {}

        for trade in sorted(trades, key=lambda t: t.get("timestamp", "")):
            symbol = trade.get("symbol", "")
            side = trade.get("side", "buy")

            if symbol not in symbol_queue:
                symbol_queue[symbol] = []

            if side == "buy":
                symbol_queue[symbol].append(trade)
            elif side == "sell" and symbol_queue[symbol]:
                buy = symbol_queue[symbol].pop(0)
                pairs.append({"buy": buy, "sell": trade})

        return pairs

    # ── benchmark methods ──────────────────────────────────────────────────

    def _compute_benchmark_metrics(
        self,
        portfolio_returns: List[float],
        benchmark_returns: List[float],
        metrics: PerformanceMetrics,
    ) -> None:
        """Compute benchmark-relative metrics."""
        n = min(len(portfolio_returns), len(benchmark_returns))
        if n < 2:
            return

        pr = portfolio_returns[:n]
        br = benchmark_returns[:n]

        # Benchmark return
        metrics.benchmark_return = (1 + sum(br)) - 1

        # Excess return
        excess = [pr[i] - br[i] for i in range(n)]
        avg_excess = sum(excess) / n
        metrics.excess_return = avg_excess

        # Tracking error (annualized)
        te_variance = sum((e - avg_excess) ** 2 for e in excess) / (n - 1)
        metrics.tracking_error = math.sqrt(te_variance) * math.sqrt(self._trading_days)

        # Beta (via linear regression)
        avg_bmr = sum(br) / n
        avg_port = sum(pr) / n
        cov = sum((pr[i] - avg_port) * (br[i] - avg_bmr) for i in range(n)) / (n - 1)
        var_bmr = sum((r - avg_bmr) ** 2 for r in br) / (n - 1)
        metrics.beta = cov / var_bmr if var_bmr > 0 else 0

        # Alpha (Jensen's alpha, annualized)
        risk_free_daily = 0.02 / self._trading_days
        metrics.alpha = (
            avg_port - risk_free_daily - metrics.beta * (avg_bmr - risk_free_daily)
        ) * self._trading_days

        # Information ratio
        metrics.information_ratio = (
            (avg_excess * self._trading_days) / metrics.tracking_error
            if metrics.tracking_error > 0 else 0
        )

    # ── helpers ────────────────────────────────────────────────────────────

    def compute_rolling_sharpe(
        self,
        returns: List[float],
        window: int = 60,
    ) -> List[float]:
        """Compute rolling Sharpe ratio."""
        if len(returns) < window:
            return []
        results = []
        for i in range(window, len(returns) + 1):
            window_returns = returns[i - window:i]
            vol = self._compute_volatility(window_returns)
            ann_return = self._compute_annual_return(
                (1 + sum(window_returns)) - 1, len(window_returns)
            )
            results.append(self._compute_sharpe(ann_return, vol))
        return results

    def compute_monthly_returns(
        self,
        equity_curve: List[Dict[str, Any]],
    ) -> Dict[str, float]:
        """Compute monthly return breakdown."""
        monthly: Dict[str, List[float]] = {}
        for e in equity_curve:
            ts = e.get("timestamp", "")
            if len(ts) >= 7:
                month = ts[:7]  # YYYY-MM
                if month not in monthly:
                    monthly[month] = []
                monthly[month].append(e["equity"])

        result: Dict[str, float] = {}
        for month, values in sorted(monthly.items()):
            if len(values) >= 2 and values[0] > 0:
                result[month] = (values[-1] - values[0]) / values[0]
        return result

    def get_stats(self) -> Dict[str, Any]:
        """Return performance engine statistics."""
        return {
            "trading_days_per_year": self._trading_days,
        }
