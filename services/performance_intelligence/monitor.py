"""Performance Monitoring Agent - real-time portfolio and strategy performance tracking."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class PerformanceFrequency(str, Enum):
    TICK = "TICK"
    MINUTE = "MINUTE"
    HOURLY = "HOURLY"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class PerformanceStatus(str, Enum):
    EXCEEDING = "EXCEEDING"
    MEETING = "MEETING"
    UNDERPERFORMING = "UNDERPERFORMING"
    CRITICAL = "CRITICAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass
class PerformanceSnapshot:
    snapshot_id: str
    timestamp: str
    total_return: float
    daily_return: float
    weekly_return: float
    monthly_return: float
    ytd_return: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    calmar_ratio: float
    information_ratio: float
    aum: float
    status: PerformanceStatus
    strategy_returns: Dict[str, float] = field(default_factory=dict)


@dataclass
class AlertThresholds:
    max_drawdown_limit: float = 0.15
    daily_loss_limit: float = 0.03
    sharpe_minimum: float = 0.5
    win_rate_minimum: float = 0.45
    volatility_max: float = 0.35


class PerformanceMonitor:
    """Performance Monitoring Agent.

    Tracks portfolio and strategy performance in real-time.
    Monitors key metrics: return, drawdown, win rate, risk-adjusted return.
    """

    def __init__(self):
        self.snapshots: List[PerformanceSnapshot] = []
        self.thresholds = AlertThresholds()
        self.alerts: List[Dict[str, Any]] = []

    def collect(self, portfolio) -> Dict[str, Any]:
        """Collect performance data from a portfolio.

        Args:
            portfolio: Portfolio data or identifier.

        Returns:
            Dict with collected performance metrics.
        """
        if isinstance(portfolio, dict):
            return self._collect_from_dict(portfolio)
        return {"performance": portfolio}

    def _collect_from_dict(self, portfolio: Dict[str, Any]) -> Dict[str, Any]:
        """Collect metrics from portfolio dict."""
        returns = portfolio.get("returns", [])
        equity_curve = portfolio.get("equity_curve", [])
        trades = portfolio.get("trades", [])

        total_return = self._compute_total_return(equity_curve)
        volatility = self._compute_volatility(returns)
        max_dd = self._compute_max_drawdown(equity_curve)
        win_rate = self._compute_win_rate(trades)
        sharpe = self._compute_sharpe(returns, volatility)
        sortino = self._compute_sortino(returns)
        profit_factor = self._compute_profit_factor(trades)
        calmar = self._compute_calmar(total_return, max_dd)
        daily_ret = self._compute_period_return(returns, 1) if returns else 0.0

        snapshot = PerformanceSnapshot(
            snapshot_id=f"PERF_{len(self.snapshots):04d}",
            timestamp=portfolio.get("timestamp", ""),
            total_return=total_return,
            daily_return=daily_ret,
            weekly_return=self._compute_period_return(returns, 5),
            monthly_return=self._compute_period_return(returns, 21),
            ytd_return=total_return,
            volatility=volatility,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_dd,
            win_rate=win_rate,
            profit_factor=profit_factor,
            calmar_ratio=calmar,
            information_ratio=sharpe,
            aum=portfolio.get("aum", 0.0),
            status=self._determine_status(sharpe, win_rate, max_dd, volatility),
            strategy_returns=portfolio.get("strategy_returns", {}),
        )
        self.snapshots.append(snapshot)
        self._check_alerts(snapshot)

        return {
            "performance": portfolio,
            "metrics": {
                "total_return": total_return,
                "volatility": volatility,
                "max_drawdown": max_dd,
                "sharpe_ratio": sharpe,
                "sortino_ratio": sortino,
                "win_rate": win_rate,
                "profit_factor": profit_factor,
                "calmar_ratio": calmar,
                "information_ratio": sharpe,
            },
            "status": snapshot.status.value,
            "alerts": list(self.alerts[-5:]),
        }

    def _compute_total_return(self, equity_curve: List[float]) -> float:
        if not equity_curve or len(equity_curve) < 2:
            return 0.0
        return (equity_curve[-1] / equity_curve[0]) - 1.0

    def _compute_volatility(self, returns: List[float]) -> float:
        if not returns or len(returns) < 2:
            return 0.0
        n = len(returns)
        mean = sum(returns) / n
        variance = sum((r - mean) ** 2 for r in returns) / (n - 1)
        return variance ** 0.5

    def _compute_max_drawdown(self, equity_curve: List[float]) -> float:
        if not equity_curve or len(equity_curve) < 2:
            return 0.0
        peak = equity_curve[0]
        max_dd = 0.0
        for val in equity_curve:
            if val > peak:
                peak = val
            dd = (peak - val) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
        return max_dd

    def _compute_win_rate(self, trades: List[Dict]) -> float:
        if not trades:
            return 0.5
        wins = sum(1 for t in trades if t.get("pnl", 0) > 0)
        return wins / len(trades)

    def _compute_sharpe(self, returns: List[float], volatility: float) -> float:
        if not returns or volatility == 0:
            return 0.0
        mean_return = sum(returns) / len(returns)
        risk_free = 0.02 / 252
        return (mean_return - risk_free) / volatility

    def _compute_sortino(self, returns: List[float]) -> float:
        if not returns:
            return 0.0
        negative = [r for r in returns if r < 0]
        if not negative:
            return 999.0
        mean_ret = sum(returns) / len(returns)
        downside = (sum(r**2 for r in negative) / len(negative)) ** 0.5
        return (mean_ret - 0.02 / 252) / downside if downside > 0 else 0.0

    def _compute_profit_factor(self, trades: List[Dict]) -> float:
        if not trades:
            return 1.0
        gross_profit = sum(t.get("pnl", 0) for t in trades if t.get("pnl", 0) > 0)
        gross_loss = abs(sum(t.get("pnl", 0) for t in trades if t.get("pnl", 0) < 0))
        return gross_profit / gross_loss if gross_loss > 0 else 999.0

    def _compute_calmar(self, total_return: float, max_dd: float) -> float:
        return total_return / max_dd if max_dd > 0 else 0.0

    def _compute_period_return(self, returns: List[float], periods: int) -> float:
        if not returns:
            return 0.0
        recent = returns[-periods:] if len(returns) >= periods else returns
        cumulative = 1.0
        for r in recent:
            cumulative *= (1 + r)
        return cumulative - 1.0

    def _determine_status(self, sharpe: float, win_rate: float, max_dd: float, vol: float) -> PerformanceStatus:
        if sharpe > 2.0 and win_rate > 0.60:
            return PerformanceStatus.EXCEEDING
        elif sharpe > 1.0 and win_rate > 0.50:
            return PerformanceStatus.MEETING
        elif max_dd > self.thresholds.max_drawdown_limit or sharpe < 0.0:
            return PerformanceStatus.CRITICAL
        else:
            return PerformanceStatus.UNDERPERFORMING

    def _check_alerts(self, snapshot: PerformanceSnapshot):
        """Check thresholds and generate alerts."""
        if snapshot.max_drawdown > self.thresholds.max_drawdown_limit:
            self.alerts.append({
                "type": "MAX_DRAWDOWN_BREACH",
                "value": snapshot.max_drawdown,
                "limit": self.thresholds.max_drawdown_limit,
                "message": f"Max drawdown {snapshot.max_drawdown:.1%} exceeds limit {self.thresholds.max_drawdown_limit:.1%}",
            })
        if snapshot.sharpe_ratio < self.thresholds.sharpe_minimum:
            self.alerts.append({
                "type": "SHARPE_MINIMUM_BREACH",
                "value": snapshot.sharpe_ratio,
                "limit": self.thresholds.sharpe_minimum,
                "message": f"Sharpe {snapshot.sharpe_ratio:.2f} below minimum {self.thresholds.sharpe_minimum}",
            })
        if snapshot.win_rate < self.thresholds.win_rate_minimum:
            self.alerts.append({
                "type": "WIN_RATE_BREACH",
                "value": snapshot.win_rate,
                "limit": self.thresholds.win_rate_minimum,
                "message": f"Win rate {snapshot.win_rate:.1%} below minimum {self.thresholds.win_rate_minimum:.1%}",
            })
        if snapshot.volatility > self.thresholds.volatility_max:
            self.alerts.append({
                "type": "VOLATILITY_BREACH",
                "value": snapshot.volatility,
                "limit": self.thresholds.volatility_max,
                "message": f"Volatility {snapshot.volatility:.1%} exceeds limit {self.thresholds.volatility_max:.1%}",
            })

    def get_latest_snapshot(self) -> Optional[PerformanceSnapshot]:
        """Get the most recent performance snapshot."""
        return self.snapshots[-1] if self.snapshots else None

    def get_metrics_trend(self, metric: str) -> List[float]:
        """Get trend of a specific metric across snapshots."""
        metric_map = {
            "sharpe": "sharpe_ratio",
            "drawdown": "max_drawdown",
            "win_rate": "win_rate",
            "volatility": "volatility",
            "total_return": "total_return",
        }
        attr = metric_map.get(metric, metric)
        return [getattr(s, attr, 0.0) for s in self.snapshots]

    def get_alerts(self, alert_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get alerts, optionally filtered by type."""
        if alert_type:
            return [a for a in self.alerts if a.get("type") == alert_type]
        return list(self.alerts)
