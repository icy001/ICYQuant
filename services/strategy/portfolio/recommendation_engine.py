"""
Recommendation Engine
=====================
Generates portfolio recommendations from signal pools and candidate
portfolios, supporting AI-assisted investment decisions.

Pipeline:
    Signal Pool → Candidate Portfolio → Recommendation

Outputs:
    PortfolioRecommendation with confidence, rationale, and action plan
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class RecommendationType(str, Enum):
    """Type of portfolio recommendation."""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    REDUCE = "reduce"
    INCREASE = "increase"
    REBALANCE = "rebalance"
    HEDGE = "hedge"
    LIQUIDATE = "liquidate"
    NO_ACTION = "no_action"


class RecommendationUrgency(str, Enum):
    """Urgency level of a recommendation."""

    IMMEDIATE = "immediate"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


@dataclass
class CandidatePosition:
    """A candidate position in a portfolio recommendation."""

    instrument: str = ""
    instrument_type: str = ""
    current_weight: float = 0.0
    target_weight: float = 0.0
    quantity: float = 0.0
    direction: str = ""
    expected_return: float = 0.0
    risk_contribution: float = 0.0
    confidence: float = 0.0
    signal_ids: List[str] = field(default_factory=list)
    reasoning: str = ""


@dataclass
class PortfolioRecommendation:
    """
    A complete portfolio recommendation.

    Contains candidate positions, action plan, risk assessment,
    and human-readable rationale.
    """

    recommendation_id: str = field(default_factory=lambda: f"rec_{uuid4().hex[:12]}")
    portfolio_id: str = ""
    name: str = ""

    recommendation_type: RecommendationType = RecommendationType.REBALANCE
    urgency: RecommendationUrgency = RecommendationUrgency.MEDIUM

    # Candidate positions
    candidates: List[CandidatePosition] = field(default_factory=list)
    remove_positions: List[str] = field(default_factory=list)

    # Portfolio metrics
    expected_return: float = 0.0
    expected_risk: float = 0.0
    sharpe_ratio: float = 0.0
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    turnover: float = 0.0

    # Metadata
    confidence: float = 0.0
    rationale: str = ""
    risk_assessment: str = ""
    alternative_scenarios: List[str] = field(default_factory=list)

    # Lifecycle
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    valid_until: Optional[datetime] = None
    status: str = "draft"  # draft, approved, rejected, executed, expired

    # Traceability
    signal_ids: List[str] = field(default_factory=list)
    strategy_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)

    @property
    def total_notional(self) -> float:
        """Estimated total notional value of all candidates."""
        return sum(c.target_weight for c in self.candidates)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "portfolio_id": self.portfolio_id,
            "name": self.name,
            "recommendation_type": self.recommendation_type.value,
            "urgency": self.urgency.value,
            "candidates": [
                {
                    "instrument": c.instrument,
                    "instrument_type": c.instrument_type,
                    "current_weight": c.current_weight,
                    "target_weight": c.target_weight,
                    "quantity": c.quantity,
                    "direction": c.direction,
                    "expected_return": c.expected_return,
                    "confidence": c.confidence,
                    "reasoning": c.reasoning,
                }
                for c in self.candidates
            ],
            "remove_positions": self.remove_positions,
            "expected_return": self.expected_return,
            "expected_risk": self.expected_risk,
            "sharpe_ratio": self.sharpe_ratio,
            "gross_exposure": self.gross_exposure,
            "net_exposure": self.net_exposure,
            "turnover": self.turnover,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "risk_assessment": self.risk_assessment,
            "alternative_scenarios": self.alternative_scenarios,
            "created_at": self.created_at.isoformat(),
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "status": self.status,
            "signal_ids": self.signal_ids,
            "strategy_ids": self.strategy_ids,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Recommendation Engine
# ---------------------------------------------------------------------------

class RecommendationEngine:
    """
    Portfolio Recommendation Engine.

    Generates actionable portfolio recommendations by analyzing signal
    pools, evaluating candidate portfolios, and scoring alternatives.

    Supports AI-assisted investment decision-making with human-readable
    rationale and risk assessment.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._initialized = False

        # Scoring weights
        self._return_weight = self._config.get("return_weight", 0.35)
        self._risk_weight = self._config.get("risk_weight", 0.25)
        self._confidence_weight = self._config.get("confidence_weight", 0.25)
        self._diversification_weight = self._config.get("diversification_weight", 0.15)

        # Thresholds
        self._min_confidence = self._config.get("min_confidence", 0.3)
        self._min_return = self._config.get("min_return", 0.0)
        self._max_turnover = self._config.get("max_turnover", 0.5)
        self._min_signal_count = self._config.get("min_signal_count", 2)

        # Decision engine (wired post-init)
        self._decision_engine = None  # PortfolioDecisionEngine

        # History
        self._recommendation_history: List[PortfolioRecommendation] = []
        self._max_history = self._config.get("max_history", 1000)

        # Metrics
        self._metrics: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info(
            "RecommendationEngine initialized "
            "(return_w=%.2f, risk_w=%.2f, conf_w=%.2f, div_w=%.2f)",
            self._return_weight, self._risk_weight,
            self._confidence_weight, self._diversification_weight,
        )

    async def shutdown(self) -> None:
        self._recommendation_history.clear()
        self._initialized = False
        logger.info("RecommendationEngine shut down")

    def wire(self, decision_engine: Any) -> None:
        """Wire the portfolio decision engine for full-pipeline analysis."""
        self._decision_engine = decision_engine
        logger.info("RecommendationEngine wired to PortfolioDecisionEngine")

    # ------------------------------------------------------------------
    # Recommendation Generation
    # ------------------------------------------------------------------

    async def generate(
        self,
        signals: List[Any],
        portfolio_id: str,
        portfolio_state: Optional[Dict[str, Any]] = None,
    ) -> PortfolioRecommendation:
        """
        Generate a portfolio recommendation from a signal pool.

        Args:
            signals: List of signals from the Signal Engine.
            portfolio_id: Target portfolio identifier.
            portfolio_state: Current portfolio state (holdings, weights, etc.).

        Returns:
            PortfolioRecommendation with candidates and rationale.
        """
        if not self._initialized:
            await self.initialize()

        logger.info(
            "Generating recommendation for portfolio=%s from %d signals",
            portfolio_id, len(signals),
        )

        rec = PortfolioRecommendation(
            portfolio_id=portfolio_id,
            name=f"Recommendation for {portfolio_id}",
            signal_ids=[getattr(s, "signal_id", str(s)) for s in signals],
            strategy_ids=list(set(
                getattr(s, "strategy_id", "") for s in signals
                if getattr(s, "strategy_id", "")
            )),
        )

        if len(signals) < self._min_signal_count:
            rec.recommendation_type = RecommendationType.HOLD
            rec.urgency = RecommendationUrgency.LOW
            rec.rationale = f"Insufficient signals ({len(signals)} < {self._min_signal_count})"
            rec.confidence = 0.0
            self._record_recommendation(rec)
            return rec

        # Step 1: Filter signals by minimum confidence
        filtered = [
            s for s in signals
            if getattr(s, "confidence", 0) >= self._min_confidence
        ]

        if len(filtered) < self._min_signal_count:
            rec.recommendation_type = RecommendationType.HOLD
            rec.urgency = RecommendationUrgency.LOW
            rec.rationale = (
                f"Only {len(filtered)} signals pass minimum confidence "
                f"threshold ({self._min_confidence})"
            )
            rec.confidence = 0.0
            self._record_recommendation(rec)
            return rec

        # Step 2: Try full-pipeline evaluation through Decision Engine
        if self._decision_engine:
            try:
                decision_batch = await self._decision_engine.evaluate(
                    signals=filtered,
                    portfolio_id=portfolio_id,
                    portfolio_state=portfolio_state,
                )

                # Build candidates from decisions
                candidates = []
                for decision in decision_batch.decisions:
                    # Convert signal to signal_id
                    signal_id = decision.signal_id if hasattr(decision, "signal_id") else ""

                    candidate = CandidatePosition(
                        instrument=decision.instrument if hasattr(decision, "instrument") else "",
                        instrument_type=decision.metadata.get("instrument_type", "") if hasattr(decision, "metadata") else "",
                        current_weight=decision.current_weight if hasattr(decision, "current_weight") else 0.0,
                        target_weight=decision.target_weight if hasattr(decision, "target_weight") else 0.0,
                        quantity=decision.quantity if hasattr(decision, "quantity") else 0.0,
                        direction=decision.direction if hasattr(decision, "direction") else "",
                        confidence=decision.confidence if hasattr(decision, "confidence") else 0.0,
                        signal_ids=[signal_id] if signal_id else [],
                        reasoning=decision.reason if hasattr(decision, "reason") else "",
                    )
                    candidates.append(candidate)

                rec.candidates = candidates
                rec.gross_exposure = getattr(decision_batch, "gross_exposure", 0.0)
                rec.net_exposure = getattr(decision_batch, "net_exposure", 0.0)
                rec.confidence = (
                    sum(c.confidence for c in candidates) / len(candidates)
                    if candidates else 0.0
                )

                # Score the recommendation
                rec = self._score_recommendation(rec, portfolio_state)
                rec.rationale = self._build_rationale(rec)

            except Exception as e:
                logger.error("Decision engine evaluation failed: %s", e)
                rec = self._fallback_recommendation(filtered, portfolio_id, rec)
        else:
            rec = self._fallback_recommendation(filtered, portfolio_id, rec)

        self._record_recommendation(rec)

        self._metrics["recommendations_total"] = (
            self._metrics.get("recommendations_total", 0) + 1
        )

        logger.info(
            "Recommendation %s: type=%s, urgency=%s, %d candidates",
            rec.recommendation_id,
            rec.recommendation_type.value,
            rec.urgency.value,
            rec.candidate_count,
        )

        return rec

    async def evaluate_scenario(
        self,
        scenario: Dict[str, Any],
        portfolio_id: str,
        portfolio_state: Optional[Dict[str, Any]] = None,
    ) -> PortfolioRecommendation:
        """
        Evaluate a "what-if" scenario.

        Args:
            scenario: Dict describing the scenario (e.g., {"action": "increase_tech", "pct": 5}).
            portfolio_id: Target portfolio.
            portfolio_state: Current portfolio state.

        Returns:
            PortfolioRecommendation for the scenario.
        """
        if not self._initialized:
            await self.initialize()

        # Build synthetic signals from scenario
        signals = self._scenario_to_signals(scenario)
        return await self.generate(signals, portfolio_id, portfolio_state)

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _score_recommendation(
        self,
        rec: PortfolioRecommendation,
        portfolio_state: Optional[Dict[str, Any]] = None,
    ) -> PortfolioRecommendation:
        """Score a recommendation and determine type/urgency."""
        if not rec.candidates:
            rec.recommendation_type = RecommendationType.HOLD
            rec.urgency = RecommendationUrgency.LOW
            rec.confidence = 0.0
            return rec

        # Calculate expected return
        rec.expected_return = sum(
            c.target_weight * c.expected_return for c in rec.candidates
        )

        # Determine recommendation type based on aggregate direction
        buy_weight = sum(c.target_weight for c in rec.candidates if c.direction.upper() in ("LONG", "BUY"))
        sell_weight = sum(c.target_weight for c in rec.candidates if c.direction.upper() in ("SHORT", "SELL"))

        if buy_weight > 0 and sell_weight == 0:
            rec.recommendation_type = RecommendationType.BUY if buy_weight > 0.1 else RecommendationType.INCREASE
        elif sell_weight > 0 and buy_weight == 0:
            rec.recommendation_type = RecommendationType.SELL if sell_weight > 0.1 else RecommendationType.REDUCE
        elif buy_weight > 0 and sell_weight > 0:
            rec.recommendation_type = RecommendationType.REBALANCE
        else:
            rec.recommendation_type = RecommendationType.HOLD

        # Determine urgency
        total_change = buy_weight + sell_weight
        if total_change > 0.3 or rec.confidence > 0.8:
            rec.urgency = RecommendationUrgency.HIGH
        elif total_change > 0.1 or rec.confidence > 0.5:
            rec.urgency = RecommendationUrgency.MEDIUM
        else:
            rec.urgency = RecommendationUrgency.LOW

        # Estimate risk
        rec.risk_assessment = (
            f"Target gross exposure: {total_change:.1%}\n"
        )

        return rec

    def _build_rationale(self, rec: PortfolioRecommendation) -> str:
        """Build human-readable rationale for a recommendation."""
        lines = [
            f"Recommendation: {rec.recommendation_type.value.upper()}",
            f"Confidence: {rec.confidence:.1%}",
            f"Urgency: {rec.urgency.value}",
            f"Candidates: {rec.candidate_count}",
        ]

        if rec.candidates:
            lines.append("\nTop Candidates:")
            sorted_candidates = sorted(rec.candidates, key=lambda c: c.confidence, reverse=True)
            for c in sorted_candidates[:5]:
                lines.append(
                    f"  • {c.instrument}: {c.direction} {c.target_weight:.1%} "
                    f"(conf: {c.confidence:.1%})"
                )
                if c.reasoning:
                    lines.append(f"    └ {c.reasoning}")

        if rec.risk_assessment:
            lines.append(f"\nRisk: {rec.risk_assessment}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Fallbacks
    # ------------------------------------------------------------------

    def _fallback_recommendation(
        self,
        signals: List[Any],
        portfolio_id: str,
        rec: PortfolioRecommendation,
    ) -> PortfolioRecommendation:
        """Generate a simple recommendation without the full decision engine."""
        candidates = []
        for signal in signals:
            conf = getattr(signal, "confidence", 0) if hasattr(signal, "confidence") else 0.5
            direction = getattr(signal, "direction", "LONG") if hasattr(signal, "direction") else "LONG"
            instrument = getattr(signal, "instrument", "") if hasattr(signal, "instrument") else ""

            candidate = CandidatePosition(
                instrument=instrument,
                direction=direction,
                confidence=conf,
                signal_ids=[getattr(signal, "signal_id", "")] if hasattr(signal, "signal_id") else [],
                reasoning=getattr(signal, "reason", "") if hasattr(signal, "reason") else "Signal-generated candidate",
            )
            candidates.append(candidate)

        rec.candidates = candidates
        rec.confidence = (
            sum(c.confidence for c in candidates) / len(candidates)
            if candidates else 0.0
        )
        rec = self._score_recommendation(rec)
        rec.rationale = self._build_rationale(rec)
        return rec

    def _scenario_to_signals(self, scenario: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert a scenario dict to synthetic signal dicts."""
        signals = []
        action = scenario.get("action", "")
        pct = scenario.get("pct", 0.05)
        instruments = scenario.get("instruments", [])

        for instrument in instruments:
            sig = {
                "signal_id": f"synthetic_{uuid4().hex[:8]}",
                "instrument": instrument,
                "direction": "BUY" if "increase" in action or "buy" in action else "SELL",
                "confidence": scenario.get("confidence", 0.5),
                "reason": f"Scenario: {action}",
            }
            signals.append(sig)

        return signals

    # ------------------------------------------------------------------
    # History & Queries
    # ------------------------------------------------------------------

    def _record_recommendation(self, rec: PortfolioRecommendation) -> None:
        self._recommendation_history.append(rec)
        if len(self._recommendation_history) > self._max_history:
            self._recommendation_history = self._recommendation_history[-self._max_history:]

    def get_recommendation(self, recommendation_id: str) -> Optional[PortfolioRecommendation]:
        for rec in self._recommendation_history:
            if rec.recommendation_id == recommendation_id:
                return rec
        return None

    def list_recent(self, portfolio_id: str = "", limit: int = 20) -> List[PortfolioRecommendation]:
        results = self._recommendation_history
        if portfolio_id:
            results = [r for r in results if r.portfolio_id == portfolio_id]
        results.sort(key=lambda r: r.created_at, reverse=True)
        return results[:limit]

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, int]:
        return dict(self._metrics)

    @property
    def is_initialized(self) -> bool:
        return self._initialized
