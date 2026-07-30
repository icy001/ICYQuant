"""Performance Calculator — portfolio performance metrics and analytics."""

import time
import uuid
import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class PerformanceFrequency(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


@dataclass
class PerformanceConfig:
    """Configuration for performance calculation."""

    risk_free_rate_annual: float = 0.03
    frequency: PerformanceFrequency = PerformanceFrequency.DAILY
    annualization_factor: int = 252  # trading days
    benchmark_id: str = ""
    use_log_returns: bool = True
    min_periods: int = 20  # minimum data points for valid metrics
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReturnSeries:
    """Time series of portfolio returns."""

    portfolio_id: str = ""
    returns: List[float] = field(default_factory=list)
    dates: List[str] = field(default_factory=list)
    cumulative_return: float = 0.0
    total_return: float = 0.0
    start_date: str = ""
    end_date: str = ""

    @property
    def length(self) -> int:
        return len(self.returns)

    @property
    def positive_days(self) -> int:
        return sum(1 for r in self.returns if r > 0)

    @property
    def win_rate(self) -> float:
        return (self.positive_days / self.length * 100) if self.length > 0 else 0.0


@dataclass
class RiskMetrics:
    """Risk metrics for a portfolio."""

    volatility_annual: float = 0.0
    var_95_daily: float = 0.0
    var_99_daily: float = 0.0
    cvar_95_daily: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration_days: int = 0
    downside_deviation: float = 0.0
    beta: float = 0.0
    tracking_error: float = 0.0
    skewness: float = 0.0
    kurtosis: float = 0.0
    ulcer_index: float = 0.0
    pain_index: float = 0.0


@dataclass
class PerformanceMetrics:
    """Complete performance metrics for a portfolio."""

    portfolio_id: str = ""
    period: str = ""
    total_return: float = 0.0
    annual_return: float = 0.0
    volatility_annual: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    information_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    risk: Optional[RiskMetrics] = None
    benchmark_return: float = 0.0
    excess_return: float = 0.0
    calculated_at: float = field(default_factory=time.time)


class PerformanceCalculator:
    """Calculates portfolio performance and risk metrics.

    Computes:
    - Returns: total, annualized, cumulative
    - Risk: volatility, VaR, CVaR, drawdown, beta, tracking error
    - Ratios: Sharpe, Sortino, Calmar, Information
    - Statistics: win rate, profit factor, skewness, kurtosis
    """

    def __init__(self, config: Optional[PerformanceConfig] = None):
        self.config = config or PerformanceConfig()
        self._return_series: Dict[str, List[ReturnSeries]] = {}
        self._metrics_history: Dict[str, List[PerformanceMetrics]] = {}

    def add_returns(
        self, portfolio_id: str, returns_data: ReturnSeries
    ) -> None:
        if portfolio_id not in self._return_series:
            self._return_series[portfolio_id] = []
        self._return_series[portfolio_id].append(returns_data)

    def calculate_metrics(
        self,
        portfolio_id: str,
        returns: List[float],
        benchmark_returns: Optional[List[float]] = None,
    ) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics."""
        if len(returns) < self.config.min_periods:
            logger.warning("Insufficient data: %d periods < %d minimum",
                         len(returns), self.config.min_periods)
            return PerformanceMetrics(portfolio_id=portfolio_id)

        # Returns
        total_return = self._total_return(returns)
        annual_return = self._annualize_return(total_return, len(returns))

        # Risk
        volatility = self._volatility(returns)
        annual_vol = volatility * math.sqrt(self.config.annualization_factor)
        drawdown = self._max_drawdown(returns)
        var_95 = self._value_at_risk(returns, 0.95)
        cvar_95 = self._conditional_var(returns, 0.95)
        downside_dev = self._downside_deviation(returns)

        # Ratios
        excess_return = annual_return - self.config.risk_free_rate_annual
        sharpe = excess_return / annual_vol if annual_vol > 0 else 0.0
        sortino = excess_return / downside_dev if downside_dev > 0 else 0.0
        calmar = annual_return / abs(drawdown) if abs(drawdown) > 0 else 0.0

        # Win/Loss
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r < 0]
        win_rate = len(wins) / len(returns) * 100 if returns else 0.0
        avg_win = sum(wins) / len(wins) if wins else 0.0
        avg_loss = sum(losses) / len(losses) if losses else 0.0
        profit_factor = (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else 0.0

        # Benchmark comparison
        bench_return = 0.0
        excess = 0.0
        tracking_error = 0.0
        info_ratio = 0.0
        beta = 0.0

        if benchmark_returns and len(benchmark_returns) >= self.config.min_periods:
            bench_return = self._total_return(benchmark_returns)
            excess = total_return - bench_return
            # Tracking error
            te_returns = [r - b for r, b in zip(returns, benchmark_returns)]
            tracking_error = self._volatility(te_returns) * math.sqrt(self.config.annualization_factor)
            info_ratio = (self._annualize_return(excess, len(returns))) / tracking_error if tracking_error > 0 else 0.0
            # Beta
            bench_vol = self._volatility(benchmark_returns)
            if bench_vol > 0:
                cov = sum(
                    (r - sum(returns) / len(returns)) * (b - sum(benchmark_returns) / len(benchmark_returns))
                    for r, b in zip(returns, benchmark_returns)
                ) / len(returns)
                beta = cov / (bench_vol ** 2)

        # Skewness & Kurtosis
        skew = self._skewness(returns)
        kurt = self._kurtosis(returns)

        risk = RiskMetrics(
            volatility_annual=annual_vol,
            var_95_daily=var_95,
            cvar_95_daily=cvar_95,
            max_drawdown=drawdown,
            downside_deviation=downside_dev,
            beta=beta,
            tracking_error=tracking_error,
            skewness=skew,
            kurtosis=kurt,
            ulcer_index=self._ulcer_index(returns),
            pain_index=self._pain_index(returns),
        )

        metrics = PerformanceMetrics(
            portfolio_id=portfolio_id,
            total_return=total_return,
            annual_return=annual_return,
            volatility_annual=annual_vol,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            information_ratio=info_ratio,
            max_drawdown=drawdown,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            risk=risk,
            benchmark_return=bench_return,
            excess_return=excess,
        )

        if portfolio_id not in self._metrics_history:
            self._metrics_history[portfolio_id] = []
        self._metrics_history[portfolio_id].append(metrics)

        return metrics

    # ---- Internal Calculation Methods ----

    def _total_return(self, returns: List[float]) -> float:
        if self.config.use_log_returns:
            return math.exp(sum(returns)) - 1
        result = 1.0
        for r in returns:
            result *= (1 + r)
        return result - 1

    def _annualize_return(self, total_return: float, n_periods: int) -> float:
        if n_periods <= 0:
            return 0.0
        if self.config.use_log_returns:
            # For log returns: exp(mean * annualization) - 1
            return math.exp(math.log(1 + total_return) * self.config.annualization_factor / n_periods) - 1
        return (1 + total_return) ** (self.config.annualization_factor / n_periods) - 1

    def _volatility(self, returns: List[float]) -> float:
        if len(returns) < 2:
            return 0.0
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        return math.sqrt(max(variance, 0.0))

    def _max_drawdown(self, returns: List[float]) -> float:
        """Calculate maximum drawdown from peak."""
        if not returns:
            return 0.0
        cumulative = 1.0
        peak = 1.0
        max_dd = 0.0
        for r in returns:
            cumulative *= (1 + r)
            peak = max(peak, cumulative)
            dd = (peak - cumulative) / peak
            max_dd = max(max_dd, dd)
        return -max_dd

    def _value_at_risk(self, returns: List[float], confidence: float = 0.95) -> float:
        """Historical VaR at given confidence level."""
        if not returns:
            return 0.0
        sorted_returns = sorted(returns)
        index = int((1 - confidence) * len(sorted_returns))
        return -sorted_returns[max(0, min(index, len(sorted_returns) - 1))]

    def _conditional_var(self, returns: List[float], confidence: float = 0.95) -> float:
        """Conditional VaR (Expected Shortfall)."""
        if not returns:
            return 0.0
        var = self._value_at_risk(returns, confidence)
        tail = [r for r in returns if r <= -var]
        return -sum(tail) / len(tail) if tail else var

    def _downside_deviation(self, returns: List[float], target: float = 0.0) -> float:
        """Downside deviation (semi-deviation) below target."""
        below = [min(r - target, 0) ** 2 for r in returns]
        return math.sqrt(sum(below) / len(below)) if below else 0.0

    def _skewness(self, returns: List[float]) -> float:
        if len(returns) < 3:
            return 0.0
        mean = sum(returns) / len(returns)
        std = self._volatility(returns)
        if std == 0:
            return 0.0
        n = len(returns)
        m3 = sum((r - mean) ** 3 for r in returns) / n
        return m3 / (std ** 3)

    def _kurtosis(self, returns: List[float]) -> float:
        if len(returns) < 4:
            return 0.0
        mean = sum(returns) / len(returns)
        std = self._volatility(returns)
        if std == 0:
            return 0.0
        n = len(returns)
        m4 = sum((r - mean) ** 4 for r in returns) / n
        return m4 / (std ** 4) - 3  # excess kurtosis

    def _ulcer_index(self, returns: List[float]) -> float:
        """Ulcer Index — measures depth and duration of drawdowns."""
        if not returns:
            return 0.0
        cumulative = 1.0
        peak = 1.0
        squared_drawdowns = []
        for r in returns:
            cumulative *= (1 + r)
            peak = max(peak, cumulative)
            dd = (peak - cumulative) / peak
            squared_drawdowns.append(dd ** 2)
        return math.sqrt(sum(squared_drawdowns) / len(squared_drawdowns))

    def _pain_index(self, returns: List[float]) -> float:
        """Pain Index — mean of all drawdowns."""
        if not returns:
            return 0.0
        cumulative = 1.0
        peak = 1.0
        drawdowns = []
        for r in returns:
            cumulative *= (1 + r)
            peak = max(peak, cumulative)
            dd = (peak - cumulative) / peak
            drawdowns.append(dd)
        return sum(drawdowns) / len(drawdowns)

    # ---- Query Methods ----

    def get_metrics_history(
        self, portfolio_id: str, limit: int = 100
    ) -> List[PerformanceMetrics]:
        return self._metrics_history.get(portfolio_id, [])[-limit:]

    def get_latest_metrics(self, portfolio_id: str) -> Optional[PerformanceMetrics]:
        history = self._metrics_history.get(portfolio_id, [])
        return history[-1] if history else None

    def compare_portfolios(
        self, portfolio_ids: List[str]
    ) -> Dict[str, Optional[PerformanceMetrics]]:
        return {pid: self.get_latest_metrics(pid) for pid in portfolio_ids}

    def get_summary(self) -> Dict[str, Any]:
        total = sum(len(v) for v in self._metrics_history.values())
        portfolios = list(self._metrics_history.keys())
        avg_sharpe = 0.0
        count = 0
        for pid in portfolios:
            m = self.get_latest_metrics(pid)
            if m:
                avg_sharpe += m.sharpe_ratio
                count += 1
        return {
            "portfolios_tracked": len(portfolios),
            "total_calculations": total,
            "avg_sharpe_ratio": avg_sharpe / count if count > 0 else 0.0,
            "risk_free_rate": self.config.risk_free_rate_annual,
        }
