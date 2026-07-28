"""Trade Review Assistant – post-trade analysis and learning."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TradeReview:
    """Post-trade review with quality assessment and actionable feedback."""

    trade_id: str
    symbol: str = ""
    entry_price: float = 0.0
    exit_price: float = 0.0
    pnl_pct: float = 0.0
    result: str = ""  # "win", "loss", "breakeven"
    entry_quality: str = ""  # "good", "acceptable", "poor"
    exit_quality: str = ""  # "good", "acceptable", "poor"
    risk_control: str = ""  # "followed", "partial", "violated"
    issues: List[str] = field(default_factory=list)
    improvements: List[str] = field(default_factory=list)
    feedback: str = ""

    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "pnl_pct": self.pnl_pct,
            "result": self.result,
            "entry_quality": self.entry_quality,
            "exit_quality": self.exit_quality,
            "risk_control": self.risk_control,
            "issues": self.issues,
            "improvements": self.improvements,
            "feedback": self.feedback,
        }


class TradeReviewer:
    """Analyses completed trades and generates structured review reports.

    Evaluates entry/exit quality, risk control adherence, strategy
    deviation, and produces actionable improvement suggestions.
    """

    def review(
        self,
        trade_id: str,
        symbol: str,
        entry_price: float,
        exit_price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        planned_action: str = "",
        actual_action: str = "",
    ) -> TradeReview:
        """Perform a full post-trade review."""
        issues: List[str] = []
        improvements: List[str] = []

        # PnL
        pnl_pct = (exit_price - entry_price) / entry_price

        if pnl_pct > 0.01:
            result = "win"
        elif pnl_pct < -0.01:
            result = "loss"
        else:
            result = "breakeven"

        # Entry quality
        if planned_action and planned_action == actual_action:
            entry_quality = "good"
        elif planned_action:
            entry_quality = "acceptable"
        else:
            entry_quality = "poor"

        # Exit quality: check if stop-loss or take-profit was hit
        exit_quality = "acceptable"
        if take_profit is not None and exit_price >= take_profit:
            exit_quality = "good"
        elif stop_loss is not None and exit_price <= stop_loss:
            exit_quality = "acceptable"
            issues.append("Stop-loss triggered.")
            improvements.append("Review position sizing and entry timing.")
        elif take_profit is not None and pnl_pct > 0 and exit_price < take_profit:
            exit_quality = "acceptable"
            issues.append("Exited before target.")
            improvements.append("Consider holding to target when trend intact.")
        elif stop_loss is not None and pnl_pct < 0 and exit_price > stop_loss:
            exit_quality = "poor"
            issues.append("Exited early during drawdown.")
            improvements.append("Trust stop-loss levels; avoid panic exits.")

        # Risk control
        risk_control = "followed"
        if stop_loss is not None and exit_price < stop_loss * 0.98:
            risk_control = "violated"
            issues.append("Risk limit violated.")
            improvements.append("Enforce strict stop-loss discipline.")

        # Build feedback
        fb_parts: List[str] = [
            f"Trade {trade_id} ({symbol}): {result.upper()} ({pnl_pct:+.2%})."
        ]
        if issues:
            fb_parts.append(f"Issues: {'; '.join(issues)}.")
        if improvements:
            fb_parts.append(f"Improvements: {'; '.join(improvements)}.")

        return TradeReview(
            trade_id=trade_id,
            symbol=symbol,
            entry_price=entry_price,
            exit_price=exit_price,
            pnl_pct=round(pnl_pct, 4),
            result=result,
            entry_quality=entry_quality,
            exit_quality=exit_quality,
            risk_control=risk_control,
            issues=issues,
            improvements=improvements,
            feedback=" ".join(fb_parts),
        )
