"""Trading Journal Generator – auto-generate institutional trading journals."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .trade_result import TradeResult


@dataclass
class JournalEntry:
    """A structured trading journal entry."""

    trade_id: str
    symbol: str = ""
    date: str = ""

    # Trade thesis
    thesis: str = ""
    entry_reason: str = ""
    exit_reason: str = ""

    # Risk management
    risk_assessment: str = ""
    position_sizing: str = ""
    stop_loss_used: bool = False

    # Execution
    execution_quality: str = ""
    entry_slippage_bps: float = 0.0
    exit_slippage_bps: float = 0.0

    # Outcome
    pnl: float = 0.0
    pnl_pct: float = 0.0
    outcome: str = ""
    holding_days: int = 0

    # Reflection
    what_went_well: List[str] = field(default_factory=list)
    what_went_wrong: List[str] = field(default_factory=list)
    lesson: str = ""
    improvement_plan: str = ""

    # Metadata
    strategy_name: str = ""
    market_regime: str = ""
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "date": self.date,
            "thesis": self.thesis,
            "entry_reason": self.entry_reason,
            "exit_reason": self.exit_reason,
            "risk_assessment": self.risk_assessment,
            "position_sizing": self.position_sizing,
            "stop_loss_used": self.stop_loss_used,
            "execution_quality": self.execution_quality,
            "entry_slippage_bps": self.entry_slippage_bps,
            "exit_slippage_bps": self.exit_slippage_bps,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "outcome": self.outcome,
            "holding_days": self.holding_days,
            "what_went_well": self.what_went_well,
            "what_went_wrong": self.what_went_wrong,
            "lesson": self.lesson,
            "improvement_plan": self.improvement_plan,
            "strategy_name": self.strategy_name,
            "market_regime": self.market_regime,
            "tags": self.tags,
        }

    def to_markdown(self) -> str:
        """Render the journal entry as Markdown."""
        lines = [
            f"# Trading Journal: {self.trade_id}",
            "",
            f"**Symbol:** {self.symbol}",
            f"**Date:** {self.date}",
            f"**Strategy:** {self.strategy_name}",
            f"**Market Regime:** {self.market_regime}",
            "",
            "## Trade Thesis",
            self.thesis,
            "",
            "## Entry & Exit",
            f"- **Entry Reason:** {self.entry_reason}",
            f"- **Exit Reason:** {self.exit_reason}",
            "",
            "## Risk Management",
            f"- **Risk Assessment:** {self.risk_assessment}",
            f"- **Position Sizing:** {self.position_sizing}",
            f"- **Stop Loss:** {'Yes' if self.stop_loss_used else 'No'}",
            "",
            "## Execution",
            f"- **Quality:** {self.execution_quality}",
            f"- **Entry Slippage:** {self.entry_slippage_bps:.1f}bps",
            f"- **Exit Slippage:** {self.exit_slippage_bps:.1f}bps",
            "",
            "## Outcome",
            f"- **PnL:** ${self.pnl:,.2f} ({self.pnl_pct:+.2f}%)",
            f"- **Result:** {self.outcome.upper()}",
            f"- **Holding Period:** {self.holding_days} days",
            "",
            "## Reflection",
        ]

        if self.what_went_well:
            lines.append("### What Went Well")
            for item in self.what_went_well:
                lines.append(f"- {item}")
            lines.append("")

        if self.what_went_wrong:
            lines.append("### What Went Wrong")
            for item in self.what_went_wrong:
                lines.append(f"- {item}")
            lines.append("")

        lines.extend([
            f"### Lesson",
            self.lesson,
            "",
            f"### Improvement Plan",
            self.improvement_plan,
            "",
        ])

        if self.tags:
            lines.append(f"**Tags:** {', '.join(self.tags)}")

        return "\n".join(lines)


class TradingJournalGenerator:
    """Generates structured trading journals from completed trades.

    Produces institutional-grade journal entries covering:
    - Trade thesis and rationale
    - Entry and exit reasoning
    - Risk management decisions
    - Execution quality assessment
    - Outcome analysis
    - Reflection and lessons learned
    """

    def generate(self, trade: TradeResult,
                 thesis: str = "",
                 entry_reason: str = "",
                 exit_reason: str = "",
                 lesson: str = "",
                 improvement_plan: str = "") -> JournalEntry:
        """Generate a journal entry from a trade result."""
        return self._build_entry(
            trade, thesis, entry_reason, exit_reason,
            lesson, improvement_plan,
        )

    def generate_from_trade(self, trade: TradeResult) -> dict:
        """Legacy interface: quick dict output."""
        entry = self.generate(trade)
        return {"journal": entry.trade_id, "entry": entry.to_dict()}

    def generate_batch(
        self,
        trades: List[TradeResult],
        theses: Optional[List[str]] = None,
        entry_reasons: Optional[List[str]] = None,
        exit_reasons: Optional[List[str]] = None,
        lessons: Optional[List[str]] = None,
        improvement_plans: Optional[List[str]] = None,
    ) -> List[JournalEntry]:
        """Generate journal entries for a batch of trades."""
        entries = []
        for i, trade in enumerate(trades):
            thesis = theses[i] if theses and i < len(theses) else ""
            entry_r = entry_reasons[i] if entry_reasons and i < len(entry_reasons) else ""
            exit_r = exit_reasons[i] if exit_reasons and i < len(exit_reasons) else ""
            lesson = lessons[i] if lessons and i < len(lessons) else ""
            plan = improvement_plans[i] if improvement_plans and i < len(improvement_plans) else ""
            entries.append(self.generate(trade, thesis, entry_r, exit_r, lesson, plan))
        return entries

    def _build_entry(
        self,
        trade: TradeResult,
        thesis: str,
        entry_reason: str,
        exit_reason: str,
        lesson: str,
        improvement_plan: str,
    ) -> JournalEntry:
        entry = JournalEntry(
            trade_id=trade.trade_id,
            symbol=trade.symbol,
            date=datetime.utcnow().strftime("%Y-%m-%d"),
            thesis=thesis or trade.decision_reason or "No thesis recorded",
            entry_reason=entry_reason or trade.decision_reason or "No entry reason recorded",
            exit_reason=exit_reason or self._infer_exit_reason(trade),
            risk_assessment=self._assess_risk(trade),
            position_sizing=f"{trade.quantity} shares ({trade.notional_value(trade.entry_price):,.0f} notional)" if trade.entry_price > 0 else f"{trade.quantity} shares",
            stop_loss_used=trade.stop_loss > 0,
            execution_quality=self._overall_execution_quality(trade),
            entry_slippage_bps=trade.entry_slippage_bps,
            exit_slippage_bps=trade.exit_slippage_bps,
            pnl=trade.pnl,
            pnl_pct=trade.pnl_pct,
            outcome=trade.outcome,
            holding_days=trade.holding_days,
            what_went_well=self._identify_positives(trade),
            what_went_wrong=self._identify_negatives(trade),
            lesson=lesson or self._default_lesson(trade),
            improvement_plan=improvement_plan or self._default_plan(trade),
            strategy_name=trade.strategy_name,
            market_regime=trade.market_regime,
            tags=trade.tags,
        )
        return entry

    def _infer_exit_reason(self, trade: TradeResult) -> str:
        """Infer exit reason from trade data."""
        reasons = []
        if trade.target_price > 0 and trade.exit_price >= trade.target_price * 0.98:
            reasons.append("Target reached")
        if trade.stop_loss > 0:
            if trade.side.upper() == "LONG" and trade.exit_price <= trade.stop_loss:
                reasons.append("Stop-loss triggered")
            elif trade.side.upper() == "SHORT" and trade.exit_price >= trade.stop_loss:
                reasons.append("Stop-loss triggered")
        if trade.holding_days > 20:
            reasons.append("Time-based exit")
        if not reasons:
            reasons.append("Manual exit")
        return "; ".join(reasons)

    def _assess_risk(self, trade: TradeResult) -> str:
        """Assess risk management quality."""
        if trade.risk_score < 0.3:
            return "Conservative – low risk"
        elif trade.risk_score < 0.6:
            return "Moderate – balanced risk"
        elif trade.risk_score < 0.8:
            return "Aggressive – elevated risk"
        else:
            return "High risk – review sizing"

    def _overall_execution_quality(self, trade: TradeResult) -> str:
        """Rate overall execution quality."""
        avg = (abs(trade.entry_slippage_bps) + abs(trade.exit_slippage_bps)) / 2
        if avg < 1:
            return "excellent"
        elif avg < 5:
            return "good"
        elif avg < 15:
            return "fair"
        else:
            return "poor"

    def _identify_positives(self, trade: TradeResult) -> List[str]:
        positives = []
        if trade.pnl_pct > 3:
            positives.append(f"Strong return of {trade.pnl_pct:.1f}%")
        if abs(trade.entry_slippage_bps) < 2:
            positives.append("Precise entry execution")
        if abs(trade.exit_slippage_bps) < 2:
            positives.append("Precise exit execution")
        if trade.target_price > 0 and trade.exit_price >= trade.target_price * 0.98:
            positives.append("Exited near target price")
        if not positives:
            positives.append("No significant positives identified")
        return positives

    def _identify_negatives(self, trade: TradeResult) -> List[str]:
        negatives = []
        if trade.pnl_pct < -3:
            negatives.append(f"Significant loss of {trade.pnl_pct:.1f}%")
        if abs(trade.entry_slippage_bps) > 10:
            negatives.append(f"High entry slippage: {abs(trade.entry_slippage_bps):.0f}bps")
        if abs(trade.exit_slippage_bps) > 10:
            negatives.append(f"High exit slippage: {abs(trade.exit_slippage_bps):.0f}bps")
        if not negatives:
            negatives.append("No significant negatives identified")
        return negatives

    def _default_lesson(self, trade: TradeResult) -> str:
        if trade.pnl > 0:
            return f"Winning trade – identify repeatable elements. {trade.strategy_name} worked in {trade.market_regime} regime."
        else:
            return f"Losing trade – review entry criteria and risk sizing. Market was {trade.market_regime}."

    def _default_plan(self, trade: TradeResult) -> str:
        if trade.pnl > 0:
            return "Document trade setup for future reference. Consider scaling up."
        else:
            return "Review trade thesis. Tighten stop-loss or reduce position size."
