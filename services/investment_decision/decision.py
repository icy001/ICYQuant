from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class DecisionType(str, Enum):
    BUY = "BUY"
    STRONG_BUY = "STRONG_BUY"
    HOLD = "HOLD"
    REDUCE = "REDUCE"
    SELL = "SELL"
    REJECT = "REJECT"


class DecisionUrgency(str, Enum):
    IMMEDIATE = "IMMEDIATE"
    SHORT_TERM = "SHORT_TERM"
    MEDIUM_TERM = "MEDIUM_TERM"
    OPPORTUNISTIC = "OPPORTUNISTIC"


@dataclass
class InvestmentDecision:
    decision_id: str
    symbol: str
    decision: DecisionType
    conviction_score: float
    position_size_pct: float
    entry_price_range: str
    stop_loss: float
    take_profit: float
    urgency: DecisionUrgency = DecisionUrgency.MEDIUM_TERM
    rationale: str = ""
    risk_controls: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    valid_until: str = ""


class InvestmentDecisionEngine:
    """Investment Decision Engine - makes final investment decisions based on conviction and risk."""

    def __init__(self):
        self.decisions: List[InvestmentDecision] = []
        self.decision_count = 0

    def decide(self, score):
        """Make an investment decision based on conviction score.

        Args:
            score: Conviction score data (int, dict, or InvestmentDecision).

        Returns:
            Dict containing the investment decision.
        """
        if isinstance(score, InvestmentDecision):
            return self._process_decision(score)
        if isinstance(score, dict):
            return self._decide_from_dict(score)
        if isinstance(score, (int, float)):
            return self._decide_from_score(float(score))
        return {"decision": "BUY"}

    def _decide_from_dict(self, data: dict) -> dict:
        score_data = data.get("score", data)
        conviction = score_data.get("score", 50)
        symbol = score_data.get("symbol", "UNKNOWN")
        return self._decide_from_score(float(conviction), symbol)

    def _decide_from_score(self, conviction: float, symbol: str = "UNKNOWN") -> dict:
        self.decision_count += 1

        # Map conviction score to decision
        if conviction >= 85:
            decision = DecisionType.STRONG_BUY
            position_pct = min(0.10, conviction / 1000 + 0.03)
            urgency = DecisionUrgency.IMMEDIATE
        elif conviction >= 70:
            decision = DecisionType.BUY
            position_pct = 0.05
            urgency = DecisionUrgency.SHORT_TERM
        elif conviction >= 50:
            decision = DecisionType.HOLD
            position_pct = 0.02
            urgency = DecisionUrgency.MEDIUM_TERM
        elif conviction >= 35:
            decision = DecisionType.REDUCE
            position_pct = 0.0
            urgency = DecisionUrgency.SHORT_TERM
        elif conviction >= 20:
            decision = DecisionType.SELL
            position_pct = 0.0
            urgency = DecisionUrgency.IMMEDIATE
        else:
            decision = DecisionType.REJECT
            position_pct = 0.0
            urgency = DecisionUrgency.IMMEDIATE

        # Generate stop loss and take profit
        stop_loss = 0.05 if decision in (DecisionType.BUY, DecisionType.STRONG_BUY) else 0.03
        take_profit = 0.15 if conviction > 70 else 0.10

        rationale = self._generate_rationale(decision, conviction)
        risk_controls = self._generate_risk_controls(decision)

        inv_decision = InvestmentDecision(
            decision_id=f"DEC_{self.decision_count:04d}",
            symbol=symbol,
            decision=decision,
            conviction_score=round(conviction, 1),
            position_size_pct=round(position_pct, 4),
            entry_price_range="Market ± 2%",
            stop_loss=round(stop_loss, 2),
            take_profit=round(take_profit, 2),
            urgency=urgency,
            rationale=rationale,
            risk_controls=risk_controls,
            dependencies=["Market liquidity sufficient", "No adverse news pending"],
            valid_until="24H",
        )
        self.decisions.append(inv_decision)
        return self._to_dict(inv_decision)

    def _process_decision(self, decision: InvestmentDecision) -> dict:
        self.decisions.append(decision)
        return self._to_dict(decision)

    def _generate_rationale(self, decision: DecisionType, conviction: float) -> str:
        rationales = {
            DecisionType.STRONG_BUY: (
                f"Strong conviction ({conviction:.0f}/100) supports aggressive entry. "
                "Multiple factors align: positive thesis, low risk, strong committee support."
            ),
            DecisionType.BUY: (
                f"Positive conviction ({conviction:.0f}/100). "
                "Risk/reward profile is favorable with adequate margin of safety."
            ),
            DecisionType.HOLD: (
                f"Moderate conviction ({conviction:.0f}/100). "
                "Maintain current exposure, monitor for changes in thesis or risk profile."
            ),
            DecisionType.REDUCE: (
                f"Weak conviction ({conviction:.0f}/100). "
                "Reduce exposure as thesis weakens or risk increases."
            ),
            DecisionType.SELL: (
                f"Low conviction ({conviction:.0f}/100). "
                "Exit position. Thesis invalidated or risk/reward no longer favorable."
            ),
            DecisionType.REJECT: (
                f"Negative conviction ({conviction:.0f}/100). "
                "Do not initiate position. Thesis is fundamentally flawed or risk is too high."
            ),
        }
        return rationales.get(decision, f"Conviction: {conviction:.0f}/100")

    def _generate_risk_controls(self, decision: DecisionType) -> List[str]:
        controls = ["Hard stop-loss at 5% below entry", "Position size limit enforced"]
        if decision == DecisionType.STRONG_BUY:
            controls.append("Scale in over 3 tranches")
        elif decision == DecisionType.BUY:
            controls.append("Scale in over 2 tranches")
            controls.append("Reduce if conviction drops below 60")
        elif decision == DecisionType.HOLD:
            controls.append("Trailing stop at 3%")
            controls.append("Review weekly for thesis validity")
        elif decision in (DecisionType.REDUCE, DecisionType.SELL, DecisionType.REJECT):
            controls.append("Execute within 24 hours")
            controls.append("No additional buying permitted")
        return controls

    def _to_dict(self, decision: InvestmentDecision) -> dict:
        return {
            "decision": {
                "decision_id": decision.decision_id,
                "symbol": decision.symbol,
                "decision": decision.decision.value,
                "conviction_score": decision.conviction_score,
                "position_size_pct": decision.position_size_pct,
                "entry_price_range": decision.entry_price_range,
                "stop_loss": decision.stop_loss,
                "take_profit": decision.take_profit,
                "urgency": decision.urgency.value,
                "rationale": decision.rationale,
                "risk_controls": decision.risk_controls,
                "dependencies": decision.dependencies,
                "valid_until": decision.valid_until,
            }
        }

    def get_decisions(self, symbol: Optional[str] = None) -> List[InvestmentDecision]:
        """Get all decisions, optionally filtered by symbol."""
        if symbol:
            return [d for d in self.decisions if d.symbol == symbol]
        return list(self.decisions)
