"""Outcome Analyzer – analyze completed trade results."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .trade_result import TradeResult


@dataclass
class OutcomeReport:
    """Detailed analysis report for a single trade."""

    trade_id: str
    pnl: float = 0.0
    pnl_pct: float = 0.0
    quality: str = "unknown"  # "excellent", "good", "fair", "poor"
    outcome_category: str = ""  # "trend_win", "mean_reversion_win", "cut_loss", etc.
    holding_efficiency: str = ""  # how well the holding period was utilized
    risk_adjusted_return: float = 0.0

    # Detailed analysis
    score: float = 0.0  # 0-100 composite score
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "quality": self.quality,
            "outcome_category": self.outcome_category,
            "holding_efficiency": self.holding_efficiency,
            "risk_adjusted_return": self.risk_adjusted_return,
            "score": self.score,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "recommendations": self.recommendations,
        }


class OutcomeAnalyzer:
    """Analyzes completed trade results for performance and quality assessment.

    Evaluates trades on multiple dimensions:
    - Profitability (absolute and risk-adjusted)
    - Execution quality (entry/exit slippage)
    - Holding efficiency (PnL per day held)
    - Strategy adherence (target/stop-loss discipline)
    """

    def analyze(self, trade: TradeResult) -> dict:
        """Quick analysis returning a summary dict."""
        report = self.analyze_detailed(trade)
        return {
            "pnl": trade.pnl,
            "quality": report.quality,
            "score": report.score,
            "outcome_category": report.outcome_category,
        }

    def analyze_detailed(self, trade: TradeResult) -> OutcomeReport:
        """Full detailed trade outcome analysis."""
        report = OutcomeReport(
            trade_id=trade.trade_id,
            pnl=trade.pnl,
            pnl_pct=trade.pnl_pct,
        )

        # 1. Profitability scoring (0-40)
        pnl_score = self._score_pnl(trade)

        # 2. Execution quality scoring (0-20)
        exec_score = self._score_execution(trade)

        # 3. Holding efficiency scoring (0-20)
        holding_score = self._score_holding(trade)

        # 4. Strategy discipline scoring (0-20)
        discipline_score = self._score_discipline(trade)

        total = pnl_score + exec_score + holding_score + discipline_score
        report.score = round(total, 1)

        # Categorize outcome
        report.outcome_category = self._categorize(trade)
        report.holding_efficiency = self._holding_efficiency_label(trade)

        # Quality rating
        if report.score >= 80:
            report.quality = "excellent"
        elif report.score >= 60:
            report.quality = "good"
        elif report.score >= 40:
            report.quality = "fair"
        else:
            report.quality = "poor"

        # Risk-adjusted return (annualized Sharpe-style, simplified)
        report.risk_adjusted_return = self._risk_adjusted(trade)

        # Strengths & weaknesses
        report.strengths = self._identify_strengths(trade, report)
        report.weaknesses = self._identify_weaknesses(trade, report)
        report.recommendations = self._generate_recommendations(trade, report)

        return report

    def analyze_batch(self, trades: List[TradeResult]) -> List[OutcomeReport]:
        """Analyze a batch of trades."""
        return [self.analyze_detailed(t) for t in trades]

    def batch_summary(self, reports: List[OutcomeReport]) -> dict:
        """Summarize across multiple trade reports."""
        if not reports:
            return {"total_trades": 0, "win_rate": 0.0, "avg_score": 0.0}

        wins = sum(1 for r in reports if r.pnl > 0)
        losses = sum(1 for r in reports if r.pnl < 0)
        total_pnl = sum(r.pnl for r in reports)
        avg_score = sum(r.score for r in reports) / len(reports)

        quality_dist = {"excellent": 0, "good": 0, "fair": 0, "poor": 0}
        for r in reports:
            quality_dist[r.quality] = quality_dist.get(r.quality, 0) + 1

        return {
            "total_trades": len(reports),
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / len(reports), 3) if reports else 0.0,
            "total_pnl": round(total_pnl, 2),
            "avg_score": round(avg_score, 1),
            "quality_distribution": quality_dist,
        }

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------

    def _score_pnl(self, trade: TradeResult) -> float:
        """Score profitability (0-40)."""
        if trade.pnl_pct > 10:
            return 40.0
        elif trade.pnl_pct > 5:
            return 35.0
        elif trade.pnl_pct > 2:
            return 30.0
        elif trade.pnl_pct > 0:
            return 20.0
        elif trade.pnl_pct > -2:
            return 10.0
        elif trade.pnl_pct > -5:
            return 5.0
        else:
            return 0.0

    def _score_execution(self, trade: TradeResult) -> float:
        """Score execution quality (0-20)."""
        avg_slippage = (abs(trade.entry_slippage_bps) + abs(trade.exit_slippage_bps)) / 2
        if avg_slippage < 1.0:
            return 20.0
        elif avg_slippage < 3.0:
            return 15.0
        elif avg_slippage < 5.0:
            return 10.0
        elif avg_slippage < 10.0:
            return 5.0
        else:
            return 0.0

    def _score_holding(self, trade: TradeResult) -> float:
        """Score holding efficiency (0-20)."""
        if trade.holding_days <= 0:
            return 0.0
        daily_return = trade.pnl_pct / trade.holding_days
        if daily_return > 1.0:
            return 20.0
        elif daily_return > 0.5:
            return 15.0
        elif daily_return > 0.1:
            return 10.0
        elif daily_return > 0:
            return 5.0
        else:
            return 0.0

    def _score_discipline(self, trade: TradeResult) -> float:
        """Score strategy discipline (0-20)."""
        score = 10.0  # start neutral

        # Reward: exited near target
        if trade.target_price > 0 and trade.exit_price > 0:
            if trade.side.upper() == "LONG":
                if trade.exit_price >= trade.target_price * 0.95:
                    score += 5.0
            else:
                if trade.exit_price <= trade.target_price * 1.05:
                    score += 5.0

        # Penalty: stopped out
        if trade.stop_loss > 0 and trade.exit_price > 0:
            if trade.side.upper() == "LONG":
                if trade.exit_price <= trade.stop_loss:
                    score -= 5.0
            else:
                if trade.exit_price >= trade.stop_loss:
                    score -= 5.0

        # Penalty: held too long relative to target
        if trade.target_price > 0 and trade.holding_days > 20:
            score -= 3.0

        return max(0.0, min(20.0, score))

    def _categorize(self, trade: TradeResult) -> str:
        """Categorize the trade outcome."""
        if trade.pnl > 0:
            if trade.holding_days <= 3:
                return "quick_win"
            elif trade.holding_days <= 10:
                return "trend_win"
            else:
                return "long_term_win"
        elif trade.pnl < 0:
            if trade.exit_slippage_bps > 10:
                return "execution_loss"
            elif trade.holding_days <= 1:
                return "cut_loss"
            elif trade.holding_days <= 10:
                return "trend_loss"
            else:
                return "stubborn_loss"
        return "breakeven"

    def _holding_efficiency_label(self, trade: TradeResult) -> str:
        """Label holding period efficiency."""
        if trade.holding_days <= 0:
            return "N/A"
        daily = trade.pnl_pct / trade.holding_days
        if daily > 1.0:
            return "excellent"
        elif daily > 0.5:
            return "good"
        elif daily > 0.1:
            return "fair"
        elif daily > 0:
            return "low"
        else:
            return "negative"

    def _risk_adjusted(self, trade: TradeResult) -> float:
        """Simplified risk-adjusted return."""
        if trade.risk_score <= 0 or trade.holding_days <= 0:
            return trade.pnl_pct
        return round(trade.pnl_pct / (trade.risk_score + 0.01), 2)

    # ------------------------------------------------------------------
    # Strengths & Weaknesses
    # ------------------------------------------------------------------

    def _identify_strengths(self, trade: TradeResult,
                            report: OutcomeReport) -> List[str]:
        strengths = []
        if trade.pnl_pct > 5:
            strengths.append(f"Strong return: {trade.pnl_pct:.1f}%")
        if trade.entry_slippage_bps < 2.0:
            strengths.append("Excellent entry execution")
        if trade.exit_slippage_bps < 2.0:
            strengths.append("Excellent exit execution")
        if trade.holding_days > 0 and trade.pnl_pct / trade.holding_days > 0.5:
            strengths.append("Efficient holding period")
        if trade.target_price > 0 and trade.exit_price >= trade.target_price * 0.98:
            strengths.append("Near-target exit achieved")
        return strengths

    def _identify_weaknesses(self, trade: TradeResult,
                             report: OutcomeReport) -> List[str]:
        weaknesses = []
        if trade.pnl_pct < -5:
            weaknesses.append(f"Large loss: {trade.pnl_pct:.1f}%")
        if trade.entry_slippage_bps > 10:
            weaknesses.append(f"High entry slippage: {trade.entry_slippage_bps:.0f}bps")
        if trade.exit_slippage_bps > 10:
            weaknesses.append(f"High exit slippage: {trade.exit_slippage_bps:.0f}bps")
        if trade.stop_loss > 0 and trade.exit_price > 0:
            if trade.side.upper() == "LONG" and trade.exit_price <= trade.stop_loss:
                weaknesses.append("Stop-loss triggered")
            elif trade.side.upper() == "SHORT" and trade.exit_price >= trade.stop_loss:
                weaknesses.append("Stop-loss triggered")
        if trade.holding_days > 20 and trade.pnl_pct < 0:
            weaknesses.append("Extended holding with negative result")
        return weaknesses

    def _generate_recommendations(self, trade: TradeResult,
                                  report: OutcomeReport) -> List[str]:
        recs = []
        if trade.entry_slippage_bps > 5:
            recs.append("Use limit orders or VWAP for entry to reduce slippage")
        if trade.exit_slippage_bps > 5:
            recs.append("Improve exit timing with staged liquidation")
        if trade.pnl_pct < -3 and trade.holding_days > 10:
            recs.append("Consider tighter stop-loss or earlier exit criteria")
        if trade.pnl_pct > 5 and trade.holding_days < 3:
            recs.append("Quick wins – consider scaling up in similar setups")
        if report.quality == "excellent":
            recs.append("Model trade – analyze for repeatable patterns")
        if report.quality == "poor":
            recs.append("Review decision rationale and risk sizing")
        return recs
