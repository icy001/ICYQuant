"""Strategy Performance Analyzer - evaluates strategy performance across multiple metrics."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class StrategyStatus(str, Enum):
    SCALING = "SCALING"
    STABLE = "STABLE"
    MONITORING = "MONITORING"
    UNDER_REVIEW = "UNDER_REVIEW"
    RETIRE = "RETIRE"


@dataclass
class StrategyMetrics:
    strategy_name: str
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    recovery_factor: float
    expectancy: float
    annual_return: float
    annual_volatility: float
    total_trades: int
    consecutive_losses: int
    avg_holding_period: float
    status: StrategyStatus
    score: float


class StrategyPerformanceAnalyzer:
    """Strategy Performance Analyzer.

    Evaluates: Sharpe, Sortino, Max Drawdown, Win Rate, Profit Factor.
    Provides comprehensive strategy health assessment.
    """

    def __init__(self):
        self.analyses: List[StrategyMetrics] = []

    def analyze(self, strategy) -> Dict[str, Any]:
        """Analyze strategy performance.

        Args:
            strategy: Strategy data to analyze.

        Returns:
            Dict with strategy performance analysis.
        """
        if isinstance(strategy, dict):
            return self._analyze_from_dict(strategy)
        return {"strategy": strategy}

    def _analyze_from_dict(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze strategy from structured data."""
        name = strategy.get("name", "Unknown Strategy")
        trades = strategy.get("trades", [])
        returns = strategy.get("returns", [])
        equity = strategy.get("equity_curve", [])

        total_trades = len(trades)
        if not trades:
            metrics = StrategyMetrics(
                strategy_name=name, sharpe_ratio=0.0, sortino_ratio=0.0,
                max_drawdown=0.0, win_rate=0.0, profit_factor=0.0,
                avg_win=0.0, avg_loss=0.0, recovery_factor=0.0,
                expectancy=0.0, annual_return=0.0, annual_volatility=0.0,
                total_trades=0, consecutive_losses=0, avg_holding_period=0.0,
                status=StrategyStatus.UNDER_REVIEW, score=50.0,
            )
            self.analyses.append(metrics)
            return {
                "strategy": strategy,
                "metrics": {"name": name, "total_trades": 0, "score": 50.0},
                "status": "UNDER_REVIEW",
                "message": "Insufficient trade data",
            }

        # Compute all metrics
        wins = [t.get("pnl", 0) for t in trades if t.get("pnl", 0) > 0]
        losses = [t.get("pnl", 0) for t in trades if t.get("pnl", 0) < 0]

        win_rate = len(wins) / total_trades
        avg_win = sum(wins) / len(wins) if wins else 0.0
        avg_loss = abs(sum(losses) / len(losses)) if losses else 0.0

        profit_factor = sum(wins) / abs(sum(losses)) if losses and sum(losses) != 0 else 0.0

        max_dd = self._compute_max_drawdown(equity) if equity else strategy.get("max_drawdown", 0.0)
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

        sharpe = self._compute_sharpe(returns)
        sortino = self._compute_sortino(returns)
        annual_return = self._annualize_return(returns)
        annual_vol = self._annualize_vol(returns)

        recovery_factor = abs(annual_return / max_dd) if max_dd > 0 else 0.0

        consecutive_losses = self._count_consecutive_losses(trades)
        avg_holding = self._avg_holding(trades)

        # Compute composite score
        score = self._compute_score(sharpe, sortino, win_rate, profit_factor, max_dd, recovery_factor)
        status = self._determine_status(score, max_dd, win_rate)

        metrics = StrategyMetrics(
            strategy_name=name,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_dd,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            recovery_factor=recovery_factor,
            expectancy=expectancy,
            annual_return=annual_return,
            annual_volatility=annual_vol,
            total_trades=total_trades,
            consecutive_losses=consecutive_losses,
            avg_holding_period=avg_holding,
            status=status,
            score=score,
        )
        self.analyses.append(metrics)

        return {
            "strategy": strategy,
            "metrics": {
                "name": name,
                "sharpe_ratio": sharpe,
                "sortino_ratio": sortino,
                "max_drawdown": max_dd,
                "win_rate": win_rate,
                "profit_factor": profit_factor,
                "avg_win": avg_win,
                "avg_loss": avg_loss,
                "expectancy": expectancy,
                "annual_return": annual_return,
                "annual_volatility": annual_vol,
                "recovery_factor": recovery_factor,
                "total_trades": total_trades,
                "consecutive_losses": consecutive_losses,
                "avg_holding_period": avg_holding,
                "score": score,
            },
            "status": status.value,
            "recommendation": self._generate_recommendation(status, score),
        }

    def _compute_max_drawdown(self, equity: List[float]) -> float:
        if len(equity) < 2:
            return 0.0
        peak = equity[0]
        max_dd = 0.0
        for val in equity:
            if val > peak:
                peak = val
            dd = (peak - val) / peak if peak > 0 else 0.0
            max_dd = max(max_dd, dd)
        return max_dd

    def _compute_sharpe(self, returns: List[float]) -> float:
        if len(returns) < 2:
            return 0.0
        mean_r = sum(returns) / len(returns)
        var = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
        vol = var ** 0.5
        if vol == 0:
            return 0.0
        return (mean_r - 0.02 / 252) / vol

    def _compute_sortino(self, returns: List[float]) -> float:
        if not returns:
            return 0.0
        negative = [r for r in returns if r < 0]
        if not negative:
            return 999.0
        mean_ret = sum(returns) / len(returns)
        downside = (sum(r**2 for r in negative) / len(negative)) ** 0.5
        if downside == 0:
            return 0.0
        return (mean_ret - 0.02 / 252) / downside

    def _annualize_return(self, returns: List[float]) -> float:
        if not returns:
            return 0.0
        cumulative = 1.0
        for r in returns:
            cumulative *= (1 + r)
        periods = len(returns)
        if periods == 0:
            return 0.0
        return cumulative ** (252 / periods) - 1.0

    def _annualize_vol(self, returns: List[float]) -> float:
        if len(returns) < 2:
            return 0.0
        mean_r = sum(returns) / len(returns)
        var = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
        return (var ** 0.5) * (252 ** 0.5)

    def _count_consecutive_losses(self, trades: List[Dict]) -> int:
        max_consecutive = 0
        current = 0
        for t in trades:
            if t.get("pnl", 0) < 0:
                current += 1
                max_consecutive = max(max_consecutive, current)
            else:
                current = 0
        return max_consecutive

    def _avg_holding(self, trades: List[Dict]) -> float:
        holdings = [t.get("holding_period", 0) for t in trades if t.get("holding_period", 0) > 0]
        return sum(holdings) / len(holdings) if holdings else 0.0

    def _compute_score(self, sharpe: float, sortino: float, win_rate: float,
                       profit_factor: float, max_dd: float, recovery: float) -> float:
        score = 50.0
        score += min(20.0, max(-10.0, sharpe * 8.0))
        score += min(15.0, max(-5.0, sortino * 5.0))
        score += min(10.0, max(-5.0, (win_rate - 0.45) * 40.0))
        score += min(10.0, max(-5.0, (profit_factor - 1.0) * 5.0))
        score -= min(10.0, max_dd * 30.0)
        score += min(5.0, recovery * 2.0)
        return max(0.0, min(100.0, score))

    def _determine_status(self, score: float, max_dd: float, win_rate: float) -> StrategyStatus:
        if score >= 85:
            return StrategyStatus.SCALING
        elif score >= 70:
            return StrategyStatus.STABLE
        elif score >= 55:
            return StrategyStatus.MONITORING
        elif max_dd > 0.30 or win_rate < 0.35:
            return StrategyStatus.RETIRE
        else:
            return StrategyStatus.UNDER_REVIEW

    def _generate_recommendation(self, status: StrategyStatus, score: float) -> str:
        recommendations = {
            StrategyStatus.SCALING: f"Score {score:.0f}/100: Continue scaling capital allocation",
            StrategyStatus.STABLE: f"Score {score:.0f}/100: Maintain current allocation, monitor closely",
            StrategyStatus.MONITORING: f"Score {score:.0f}/100: Reduce allocation, investigate weaknesses",
            StrategyStatus.UNDER_REVIEW: f"Score {score:.0f}/100: Place under formal review",
            StrategyStatus.RETIRE: f"Score {score:.0f}/100: Consider retiring this strategy",
        }
        return recommendations.get(status, "Review required")

    def get_latest_analysis(self) -> Optional[StrategyMetrics]:
        """Get the most recent strategy analysis."""
        return self.analyses[-1] if self.analyses else None

    def get_top_strategies(self, min_trades: int = 10) -> List[StrategyMetrics]:
        """Get strategies ranked by score."""
        return sorted(
            [a for a in self.analyses if a.total_trades >= min_trades],
            key=lambda x: x.score,
            reverse=True,
        )
