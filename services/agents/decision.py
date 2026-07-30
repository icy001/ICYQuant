"""Decision Engine - unified AI trading decision maker.

Combines all agent inputs into a final trading decision:
- Signal from Market Agent
- Confidence from Trading Agent
- Risk assessment from Risk Agent
- Portfolio constraints from Portfolio Agent
- Execution parameters from Execution Agent

Generates the final "EXECUTE / HOLD / REDUCE / SKIP" decision.
"""

import time
import uuid
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FinalDecision(Enum):
    """Final decision outcome from the Decision Engine."""
    EXECUTE = "execute"
    EXECUTE_REDUCED = "execute_reduced"
    HOLD = "hold"
    REDUCE = "reduce"
    SKIP = "skip"
    REJECTED = "rejected"
    DEFER = "defer"


@dataclass
class DecisionInput:
    """Inputs to the decision engine from all agents."""
    market_signal: Optional[Dict[str, Any]] = None   # From Market Agent
    trade_proposal: Optional[Dict[str, Any]] = None   # From Trading Agent
    risk_assessment: Optional[Dict[str, Any]] = None  # From Risk Agent
    portfolio_state: Optional[Dict[str, Any]] = None  # From Portfolio Agent
    execution_context: Optional[Dict[str, Any]] = None  # From Execution Agent


@dataclass
class DecisionOutput:
    """Final decision output from the Decision Engine."""

    decision_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    symbol: str = ""
    decision: FinalDecision = FinalDecision.HOLD
    action: str = ""  # BUY, SELL, HOLD
    size_pct: float = 0.0
    confidence: float = 0.0
    composite_score: float = 0.0  # 0-100 weighted decision score
    weights: Dict[str, float] = field(default_factory=dict)  # component weights
    scores: Dict[str, float] = field(default_factory=dict)    # component scores
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggested_algorithm: str = "adaptive"
    suggested_slices: int = 1
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "symbol": self.symbol,
            "decision": self.decision.value,
            "action": self.action,
            "size_pct": self.size_pct,
            "confidence": self.confidence,
            "composite_score": self.composite_score,
            "weights": self.weights,
            "scores": self.scores,
            "reasons": self.reasons,
            "warnings": self.warnings,
            "suggested_algorithm": self.suggested_algorithm,
            "suggested_slices": self.suggested_slices,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


class DecisionEngine:
    """Unified Decision Engine.

    Takes inputs from all agents and produces a final executable decision.
    Weighted scoring approach:
    - Market Signal: 25%
    - Trading Confidence: 25%
    - Risk Assessment: 30%
    - Portfolio Fit: 15%
    - Execution Feasibility: 5%
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._decisions: List[DecisionOutput] = []
        self._decision_count = 0
        self._weights = {
            "market_signal": self.config.get("weight_market", 0.25),
            "trading_confidence": self.config.get("weight_trading", 0.25),
            "risk_assessment": self.config.get("weight_risk", 0.30),
            "portfolio_fit": self.config.get("weight_portfolio", 0.15),
            "execution_feasibility": self.config.get("weight_execution", 0.05),
        }

    def decide(self, inputs: DecisionInput) -> DecisionOutput:
        """Make final decision from agent inputs.

        Args:
            inputs: DecisionInput containing all agent assessments

        Returns:
            DecisionOutput with final decision
        """
        scores: Dict[str, float] = {}
        reasons: List[str] = []
        warnings: List[str] = []
        symbol = ""

        # 1. Market Signal Score (0-100)
        market_score = self._score_market_signal(inputs.market_signal)
        scores["market_signal"] = market_score
        if inputs.market_signal:
            symbol = inputs.market_signal.get("symbol", "")
            regime = inputs.market_signal.get("regime", "unknown")
            trend = inputs.market_signal.get("trend", "neutral")
            reasons.append(f"Market: regime={regime}, trend={trend}")

        # 2. Trading Confidence Score (0-100)
        trade_score = self._score_trade_proposal(inputs.trade_proposal)
        scores["trading_confidence"] = trade_score
        if inputs.trade_proposal:
            symbol = symbol or inputs.trade_proposal.get("symbol", "")
            action = inputs.trade_proposal.get("action", "HOLD")
            confidence = inputs.trade_proposal.get("confidence", 0)
            reasons.append(f"Trading: {action} with confidence {confidence:.2f}")

        # 3. Risk Assessment Score (0-100) - most important
        risk_score = self._score_risk_assessment(inputs.risk_assessment)
        scores["risk_assessment"] = risk_score
        if inputs.risk_assessment:
            decision = inputs.risk_assessment.get("decision", "unknown")
            risk_value = inputs.risk_assessment.get("risk_score", 0)
            reasons.append(f"Risk: {decision} (score={risk_value:.2f})")
            # Risk warnings
            for w in inputs.risk_assessment.get("warnings", []):
                warnings.append(w)

        # 4. Portfolio Fit Score (0-100)
        portfolio_score = self._score_portfolio_fit(inputs.portfolio_state)
        scores["portfolio_fit"] = portfolio_score
        if inputs.portfolio_state:
            drift = inputs.portfolio_state.get("total_drift", 0)
            reasons.append(f"Portfolio: drift={drift:.1f}%")

        # 5. Execution Feasibility Score (0-100)
        execution_score = self._score_execution_feasibility(inputs.execution_context)
        scores["execution_feasibility"] = execution_score

        # Calculate composite weighted score
        composite = sum(
            self._weights.get(k, 0) * v for k, v in scores.items()
        )

        # Determine final decision
        decision, action, size_pct = self._determine_decision(
            composite, scores, inputs
        )

        # Select execution algorithm
        algorithm, slices = self._select_execution_params(inputs)

        output = DecisionOutput(
            symbol=symbol,
            decision=decision,
            action=action,
            size_pct=size_pct,
            confidence=composite / 100.0,
            composite_score=composite,
            weights=dict(self._weights),
            scores=scores,
            reasons=reasons,
            warnings=warnings,
            suggested_algorithm=algorithm,
            suggested_slices=slices,
        )

        self._decisions.append(output)
        self._decision_count += 1

        # Keep bounded
        if len(self._decisions) > 500:
            self._decisions = self._decisions[-500:]

        logger.info(
            "Decision: %s %s (score=%.1f, confidence=%.2f)",
            output.decision.value, output.action, composite, output.confidence,
        )

        return output

    # ── Scoring Functions ───────────────────────────────────────

    def _score_market_signal(self, signal: Optional[Dict[str, Any]]) -> float:
        """Score market signal 0-100."""
        if not signal:
            return 50.0  # Neutral when no data

        score = 50.0
        regime = signal.get("regime", "unknown")
        trend = signal.get("trend", "neutral")

        # Regime scoring
        regime_scores = {
            "risk_on": 80.0,
            "bullish": 75.0,
            "trending_up": 70.0,
            "neutral": 50.0,
            "sideways": 45.0,
            "trending_down": 30.0,
            "risk_off": 20.0,
            "crisis": 10.0,
        }
        score += regime_scores.get(regime, 50.0) - 50.0

        # Trend scoring
        trend_scores = {
            "bullish": 15.0,
            "moderately_bullish": 10.0,
            "neutral": 0.0,
            "moderately_bearish": -10.0,
            "bearish": -15.0,
        }
        score += trend_scores.get(trend, 0.0)

        return max(0.0, min(100.0, score))

    def _score_trade_proposal(self, proposal: Optional[Dict[str, Any]]) -> float:
        """Score trade proposal 0-100."""
        if not proposal:
            return 50.0

        confidence = proposal.get("confidence", 0.5)
        action = proposal.get("action", "HOLD")

        base = confidence * 100.0

        # Penalize SELL without strong confidence
        if action == "SELL" and confidence < 0.7:
            base *= 0.8

        # Bonus for high-confidence BUY in favorable conditions
        if action == "BUY" and confidence > 0.8:
            base *= 1.1

        return max(0.0, min(100.0, base))

    def _score_risk_assessment(self, assessment: Optional[Dict[str, Any]]) -> float:
        """Score risk assessment 0-100. Higher = safer."""
        if not assessment:
            return 60.0  # Conservative when no assessment

        decision = assessment.get("decision", "unknown")
        risk_score = assessment.get("risk_score", 0.5)

        # Map risk decision to score
        decision_scores = {
            "approved": 90.0,
            "approved_with_warnings": 70.0,
            "size_reduced": 50.0,
            "rejected": 20.0,
            "blocked": 5.0,
        }
        base = decision_scores.get(decision, 50.0)

        # Adjust by risk score
        base -= risk_score * 30.0

        # Violations severely reduce score
        violations = assessment.get("violations", [])
        base -= len(violations) * 15.0

        return max(0.0, min(100.0, base))

    def _score_portfolio_fit(self, state: Optional[Dict[str, Any]]) -> float:
        """Score portfolio fit 0-100."""
        if not state:
            return 50.0

        score = 70.0
        drift = state.get("total_drift", 0)

        # Penalize large drift
        if drift > 10.0:
            score -= 20.0
        elif drift > 5.0:
            score -= 10.0

        # Cash buffer check
        cash = state.get("cash_pct", 5.0)
        if cash < 1.0:
            score -= 15.0  # Too little cash
        elif cash > 20.0:
            score -= 5.0   # Too much idle cash

        return max(0.0, min(100.0, score))

    def _score_execution_feasibility(self, context: Optional[Dict[str, Any]]) -> float:
        """Score execution feasibility 0-100."""
        if not context:
            return 70.0

        score = 80.0
        active_orders = context.get("active_orders", 0)
        liquidity = context.get("liquidity", "normal")

        if active_orders > 10:
            score -= 20.0
        elif active_orders > 5:
            score -= 10.0

        if liquidity == "tight":
            score -= 15.0
        elif liquidity == "abundant":
            score += 10.0

        return max(0.0, min(100.0, score))

    # ── Decision Determination ──────────────────────────────────

    def _determine_decision(
        self,
        composite: float,
        scores: Dict[str, float],
        inputs: DecisionInput,
    ) -> tuple:
        """Determine final decision, action, and size."""
        risk_score = scores.get("risk_assessment", 60)
        trade_score = scores.get("trading_confidence", 50)
        market_score = scores.get("market_signal", 50)

        # Hard blocks
        if risk_score < 20:
            return FinalDecision.REJECTED, "HOLD", 0.0

        # Risk requires size reduction
        if risk_score < 40:
            # Get original proposed size
            proposed_size = 2.0  # default
            if inputs.trade_proposal:
                proposed_size = inputs.trade_proposal.get("size", 2.0)
            reduced = proposed_size * (risk_score / 100.0)
            action = inputs.trade_proposal.get("action", "HOLD") if inputs.trade_proposal else "HOLD"
            return FinalDecision.EXECUTE_REDUCED, action, max(0.5, reduced)

        # Strong buy signal
        if composite >= 70 and risk_score >= 60:
            size = 2.0  # default size
            if inputs.trade_proposal:
                size = inputs.trade_proposal.get("size", 2.0)
                # Scale by confidence
                confidence = inputs.trade_proposal.get("confidence", 0.5)
                size = size * (0.5 + confidence * 0.5)
            action = inputs.trade_proposal.get("action", "BUY") if inputs.trade_proposal else "BUY"
            return FinalDecision.EXECUTE, action, size

        # Moderate signal
        if composite >= 50 and risk_score >= 40:
            if inputs.trade_proposal:
                action = inputs.trade_proposal.get("action", "HOLD")
                size = inputs.trade_proposal.get("size", 1.0) * 0.5
                return FinalDecision.EXECUTE_REDUCED, action, size
            return FinalDecision.HOLD, "HOLD", 0.0

        # Weak signal
        if composite < 40:
            # Check if we should reduce
            if market_score < 30 and risk_score < 50:
                return FinalDecision.REDUCE, "SELL", 1.0
            return FinalDecision.SKIP, "HOLD", 0.0

        return FinalDecision.HOLD, "HOLD", 0.0

    # ── Execution Parameters ────────────────────────────────────

    def _select_execution_params(self, inputs: DecisionInput) -> tuple:
        """Select execution algorithm and slice count."""
        risk = inputs.risk_assessment or {}
        market = inputs.market_signal or {}

        risk_score = risk.get("risk_score", 0.5)
        volatility = market.get("volatility", "medium")

        # High risk or volatility → adaptive execution
        if risk_score > 0.6 or volatility in ("high", "extreme"):
            return "adaptive", 15

        # Large trades → VWAP
        trade = inputs.trade_proposal or {}
        size = trade.get("size", 2.0)
        if size > 5.0:
            return "vwap", 20

        # Normal conditions → smart adaptive
        return "adaptive", 10

    # ── Decision History ────────────────────────────────────────

    def get_decisions(
        self, decision: FinalDecision = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get historical decisions."""
        results = self._decisions
        if decision:
            results = [d for d in results if d.decision == decision]
        return [d.to_dict() for d in results[-limit:]]

    def get_decision(self, decision_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific decision by ID."""
        for d in self._decisions:
            if d.decision_id == decision_id:
                return d.to_dict()
        return None

    def get_summary(self) -> Dict[str, Any]:
        """Get decision engine summary."""
        decisions = self._decisions
        if not decisions:
            return {"total": 0, "by_type": {}}

        by_type: Dict[str, int] = {}
        for d in decisions:
            dt = d.decision.value
            by_type[dt] = by_type.get(dt, 0) + 1

        return {
            "total": len(decisions),
            "by_type": by_type,
            "avg_confidence": sum(d.confidence for d in decisions) / len(decisions),
            "avg_composite_score": sum(d.composite_score for d in decisions) / len(decisions),
        }

    def update_weights(self, weights: Dict[str, float]) -> None:
        """Update decision component weights."""
        for k, v in weights.items():
            if k in self._weights:
                self._weights[k] = v
        logger.info("Decision weights updated: %s", self._weights)
