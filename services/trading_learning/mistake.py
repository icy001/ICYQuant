"""Mistake Detection Engine – identify trading errors from completed trades."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .trade_result import TradeResult


@dataclass
class MistakeReport:
    """Report of detected trading mistakes."""

    trade_id: str
    mistakes: List[str] = field(default_factory=list)
    severity: str = "none"  # "none", "minor", "moderate", "major", "critical"
    error_count: int = 0

    def has_mistakes(self) -> bool:
        return len(self.mistakes) > 0 and self.mistakes != ["none"]

    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "mistakes": self.mistakes,
            "severity": self.severity,
            "error_count": self.error_count,
            "has_mistakes": self.has_mistakes(),
        }


class MistakeDetector:
    """Detects common trading mistakes from completed trade data.

    Checks for:
    - Late entry (excessive entry slippage)
    - Early exit (exiting before trend completion)
    - Over-positioning (risk score vs position size)
    - Stop-loss violations (not honoring stop-loss)
    - Emotion bias indicators (holding losers too long, cutting winners short)
    - Poor execution (high slippage on both entry and exit)
    """

    def __init__(
        self,
        entry_slippage_threshold_bps: float = 10.0,
        exit_slippage_threshold_bps: float = 10.0,
        max_holding_days_threshold: int = 30,
        min_win_holding_days: int = 1,
    ):
        self.entry_slippage_threshold = entry_slippage_threshold_bps
        self.exit_slippage_threshold = exit_slippage_threshold_bps
        self.max_holding_days_threshold = max_holding_days_threshold
        self.min_win_holding_days = min_win_holding_days

    def detect(self, trade: TradeResult) -> list:
        """Detect mistakes, returns list of mistake strings."""
        report = self.detect_detailed(trade)
        return report.mistakes if report.mistakes else ["none"]

    def detect_detailed(self, trade: TradeResult) -> MistakeReport:
        """Detailed mistake detection with severity assessment."""
        report = MistakeReport(trade_id=trade.trade_id)
        mistakes = []

        # 1. Late entry: high entry slippage
        if abs(trade.entry_slippage_bps) > self.entry_slippage_threshold:
            mistakes.append(
                f"Late entry – {abs(trade.entry_slippage_bps):.0f}bps entry slippage"
            )

        # 2. Poor exit: high exit slippage
        if abs(trade.exit_slippage_bps) > self.exit_slippage_threshold:
            mistakes.append(
                f"Poor exit – {abs(trade.exit_slippage_bps):.0f}bps exit slippage"
            )

        # 3. Stop-loss violation
        if trade.stop_loss > 0 and trade.exit_price > 0:
            violated = False
            if trade.side.upper() == "LONG" and trade.exit_price < trade.stop_loss:
                violated = True
            elif trade.side.upper() == "SHORT" and trade.exit_price > trade.stop_loss:
                violated = True
            if violated:
                mistakes.append(
                    f"Stop-loss violation – exit at {trade.exit_price} vs stop {trade.stop_loss}"
                )

        # 4. Over-positioning: high risk score with large quantity
        if trade.risk_score > 0.7:
            mistakes.append(
                f"Over-positioning – risk score {trade.risk_score:.1f} with {trade.quantity} shares"
            )

        # 5. Early exit (cutting winners too soon)
        if trade.pnl_pct > 0 and trade.holding_days <= self.min_win_holding_days:
            mistakes.append(
                f"Early exit – profitable trade held only {trade.holding_days} day(s)"
            )

        # 6. Holding losers too long
        if trade.pnl_pct < -3 and trade.holding_days > self.max_holding_days_threshold:
            mistakes.append(
                f"Holding loser too long – {trade.holding_days} days for {trade.pnl_pct:.1f}% loss"
            )

        # 7. Emotion bias: high slippage on both entry and exit
        if (abs(trade.entry_slippage_bps) > 5 and
                abs(trade.exit_slippage_bps) > 5):
            mistakes.append("Emotion bias – poor execution on both entry and exit")

        # 8. No stop-loss set
        if trade.stop_loss <= 0:
            mistakes.append("No stop-loss set – unmanaged risk")

        report.mistakes = mistakes if mistakes else ["none"]
        report.error_count = len(mistakes)
        report.severity = self._assess_severity(mistakes, trade)

        return report

    def detect_batch(self, trades: List[TradeResult]) -> List[MistakeReport]:
        """Detect mistakes across a batch of trades."""
        return [self.detect_detailed(t) for t in trades]

    def batch_summary(self, reports: List[MistakeReport]) -> dict:
        """Summarize mistakes across multiple reports."""
        if not reports:
            return {"total_trades": 0, "trades_with_mistakes": 0,
                    "common_mistakes": []}

        trades_with_errors = [r for r in reports if r.has_mistakes()]
        all_mistakes: Dict[str, int] = {}
        for r in reports:
            for m in r.mistakes:
                if m != "none":
                    all_mistakes[m] = all_mistakes.get(m, 0) + 1

        common = sorted(all_mistakes.items(), key=lambda x: x[1], reverse=True)

        return {
            "total_trades": len(reports),
            "trades_with_mistakes": len(trades_with_errors),
            "error_rate": round(len(trades_with_errors) / len(reports), 3) if reports else 0.0,
            "common_mistakes": [{"mistake": m, "count": c} for m, c in common[:5]],
        }

    def _assess_severity(self, mistakes: List[str],
                         trade: TradeResult) -> str:
        """Assess overall mistake severity."""
        if not mistakes or mistakes == ["none"]:
            return "none"

        n = len(mistakes)
        has_stop_violation = any("Stop-loss violation" in m for m in mistakes)
        has_large_loss = trade.pnl_pct < -5

        if has_stop_violation and has_large_loss:
            return "critical"
        elif n >= 3 or has_stop_violation:
            return "major"
        elif n >= 2:
            return "moderate"
        else:
            return "minor"
