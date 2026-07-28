"""Strategy Feedback Engine – analyze strategy performance and generate feedback."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .trade_result import TradeResult


@dataclass
class StrategyFeedback:
    """Feedback report for a strategy based on recent trade results."""

    strategy_id: str = ""
    strategy_name: str = ""
    period: str = ""  # e.g. "last_10_trades", "last_week"

    # Metrics
    win_rate: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    profit_factor: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_estimate: float = 0.0

    # Assessment
    status: str = "stable"  # "improving", "stable", "deteriorating", "critical"
    action: str = "maintain"  # "increase", "maintain", "reduce", "pause", "stop"
    confidence: float = 0.5
    explanation: str = ""
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "period": self.period,
            "win_rate": self.win_rate,
            "avg_win_pct": self.avg_win_pct,
            "avg_loss_pct": self.avg_loss_pct,
            "profit_factor": self.profit_factor,
            "max_drawdown_pct": self.max_drawdown_pct,
            "sharpe_estimate": self.sharpe_estimate,
            "status": self.status,
            "action": self.action,
            "confidence": self.confidence,
            "explanation": self.explanation,
            "suggestions": self.suggestions,
        }


class StrategyFeedbackEngine:
    """Generates feedback on strategy performance from trade history.

    Analyzes a strategy's recent trades to compute key metrics (win rate,
    profit factor, drawdown) and recommends action: increase allocation,
    maintain, reduce, pause, or stop the strategy entirely.
    """

    def generate(self, trades: List[TradeResult],
                 strategy_name: str = "",
                 strategy_id: str = "") -> StrategyFeedback:
        """Generate feedback from a list of trades."""
        if not trades:
            return StrategyFeedback(
                strategy_id=strategy_id,
                strategy_name=strategy_name,
                status="stable",
                action="maintain",
                explanation="No trade data available.",
            )

        return self._compute_feedback(trades, strategy_id, strategy_name)

    def generate_from_result(self, result: dict) -> dict:
        """Legacy interface: pass through a single result dict."""
        return {"feedback": result}

    # ------------------------------------------------------------------
    # Computation
    # ------------------------------------------------------------------

    def _compute_feedback(
        self,
        trades: List[TradeResult],
        strategy_id: str,
        strategy_name: str,
    ) -> StrategyFeedback:
        fb = StrategyFeedback(
            strategy_id=strategy_id,
            strategy_name=strategy_name or trades[0].strategy_name,
            period=f"last_{len(trades)}_trades",
        )

        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl < 0]

        fb.win_rate = round(len(wins) / len(trades), 3)
        fb.avg_win_pct = round(sum(t.pnl_pct for t in wins) / len(wins), 2) if wins else 0.0
        fb.avg_loss_pct = round(sum(t.pnl_pct for t in losses) / len(losses), 2) if losses else 0.0

        # Profit factor
        total_gain = sum(t.pnl for t in wins)
        total_loss = abs(sum(t.pnl for t in losses))
        fb.profit_factor = round(total_gain / total_loss, 2) if total_loss > 0 else float("inf")

        # Drawdown (simplified: max consecutive loss)
        fb.max_drawdown_pct = self._calc_max_drawdown(trades)

        # Sharpe estimate
        fb.sharpe_estimate = self._estimate_sharpe(trades)

        # Determine status
        fb.status, fb.action = self._assess(fb, len(trades))

        # Explanation
        fb.explanation = self._explain(fb)

        # Suggestions
        fb.suggestions = self._suggest(fb)

        fb.confidence = min(0.9, 0.3 + len(trades) * 0.02)

        return fb

    def _calc_max_drawdown(self, trades: List[TradeResult]) -> float:
        """Calculate maximum drawdown from cumulative PnL."""
        if not trades:
            return 0.0
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for t in trades:
            cumulative += t.pnl_pct
            peak = max(peak, cumulative)
            dd = peak - cumulative
            max_dd = max(max_dd, dd)
        return round(max_dd, 2)

    def _estimate_sharpe(self, trades: List[TradeResult]) -> float:
        """Simple Sharpe-like ratio from trade returns."""
        if not trades:
            return 0.0
        returns = [t.pnl_pct for t in trades]
        mean_ret = sum(returns) / len(returns)
        if len(returns) < 2:
            return 0.0
        variance = sum((r - mean_ret) ** 2 for r in returns) / (len(returns) - 1)
        std = variance ** 0.5
        if std == 0:
            return 0.0
        return round(mean_ret / std, 2)

    def _assess(self, fb: StrategyFeedback, n_trades: int) -> tuple:
        """Determine strategy status and recommended action."""
        if n_trades < 3:
            return "stable", "maintain"

        # Status (check critical first, then deteriorating)
        if fb.win_rate > 0.60 and fb.profit_factor > 2.0:
            status = "improving"
        elif fb.win_rate < 0.20 or fb.max_drawdown_pct > 15:
            status = "critical"
        elif fb.win_rate < 0.35 or fb.profit_factor < 0.8:
            status = "deteriorating"
        else:
            status = "stable"

        # Action
        if status == "improving":
            action = "increase"
        elif status == "deteriorating":
            action = "reduce"
        elif status == "critical":
            action = "pause"
        else:
            action = "maintain"

        return status, action

    def _explain(self, fb: StrategyFeedback) -> str:
        """Generate a human-readable explanation."""
        parts = []
        parts.append(f"Win rate: {fb.win_rate:.1%}")
        parts.append(f"Profit factor: {fb.profit_factor:.2f}")
        parts.append(f"Avg win: {fb.avg_win_pct:.1f}%, Avg loss: {fb.avg_loss_pct:.1f}%")
        parts.append(f"Max drawdown: {fb.max_drawdown_pct:.1f}%")

        if fb.status == "improving":
            parts.append("Strategy is performing well – consider increasing allocation.")
        elif fb.status == "deteriorating":
            parts.append("Strategy is underperforming – reduce allocation and monitor.")
        elif fb.status == "critical":
            parts.append("Strategy in critical condition – pause and review.")
        else:
            parts.append("Strategy performance is within normal range.")

        return " ".join(parts)

    def _suggest(self, fb: StrategyFeedback) -> List[str]:
        """Generate actionable suggestions."""
        suggestions = []
        if fb.win_rate < 0.40:
            suggestions.append("Review entry criteria – win rate below 40%")
        if fb.avg_loss_pct < -5:
            suggestions.append("Tighten stop-loss – average loss too large")
        if fb.profit_factor < 1.0:
            suggestions.append("Profit factor below 1.0 – strategy may need overhaul")
        if fb.max_drawdown_pct > 10:
            suggestions.append("Reduce position size to limit drawdown")
        if fb.win_rate > 0.60:
            suggestions.append("Consider scaling up position size")
        if not suggestions:
            suggestions.append("Maintain current parameters")
        return suggestions
