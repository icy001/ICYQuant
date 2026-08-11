"""
Explainability Engine — Factor and alpha contribution analysis for signals.

Part of Commit 13 Part 1.2: Signal & Alpha Engine.

Pipeline:
    Signal → Factor Contribution → Alpha Contribution → Reason → Explanation

Produces human-readable explanations for AI-driven trading decisions,
enabling trader review and regulatory audit trails.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from services.strategy.signal.signal_engine import Signal, SignalDirection

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ExplanationLevel(str, Enum):
    """Detail level for explanations."""
    BRIEF = "brief"        # One-line summary
    STANDARD = "standard"  # Key contributors
    DETAILED = "detailed"  # Full breakdown


@dataclass
class FactorAttribution:
    """How much each factor contributed to the signal."""
    factor_name: str
    contribution: float  # Signed contribution
    weight: float = 1.0
    description: str = ""


@dataclass
class AlphaAttribution:
    """How much each alpha contributed to the signal."""
    alpha_id: str
    alpha_name: str
    contribution: float
    weight: float = 1.0


@dataclass
class SignalExplanation:
    """Full explanation of a trading signal."""
    signal_id: str
    summary: str = ""
    direction: str = ""
    confidence: float = 0.0
    top_factors: List[FactorAttribution] = field(default_factory=list)
    alpha_breakdown: List[AlphaAttribution] = field(default_factory=list)
    market_context: str = ""
    risk_notes: str = ""
    detailed_reasoning: str = ""


# ---------------------------------------------------------------------------
# Explainability Engine
# ---------------------------------------------------------------------------

class ExplainabilityEngine:
    """Generates human-readable explanations for trading signals.

    Each signal gets:
        1. A brief summary (one line)
        2. Factor contribution breakdown
        3. Alpha contribution breakdown
        4. Market context notes
        5. Detailed reasoning text
    """

    def __init__(self):
        self._explanation_templates = {
            SignalDirection.LONG: "LONG {instrument}: {strength} conviction ({confidence:.0%}) — {reason}",
            SignalDirection.SHORT: "SHORT {instrument}: {strength} conviction ({confidence:.0%}) — {reason}",
            SignalDirection.FLAT: "FLAT {instrument}: {reason}",
        }

    # ------------------------------------------------------------------
    # Explanation Generation
    # ------------------------------------------------------------------

    async def explain(self, signal: Signal, level: ExplanationLevel = ExplanationLevel.STANDARD) -> str:
        """Generate an explanation string for a signal.

        Returns a human-readable explanation text.
        """
        explanation = await self._build_explanation(signal, level)
        return explanation.summary

    async def explain_detailed(self, signal: Signal) -> SignalExplanation:
        """Generate a detailed SignalExplanation with full breakdown."""
        return await self._build_explanation(signal, ExplanationLevel.DETAILED)

    async def _build_explanation(self, signal: Signal, level: ExplanationLevel) -> SignalExplanation:
        """Build the full explanation object."""
        exp = SignalExplanation(
            signal_id=signal.signal_id,
            direction=signal.direction.value,
            confidence=signal.confidence,
        )

        # 1. Factor attributions
        exp.top_factors = self._compute_factor_attributions(signal)

        # 2. Alpha breakdown
        exp.alpha_breakdown = self._compute_alpha_attributions(signal)

        # 3. Market context
        exp.market_context = self._build_market_context(signal)

        # 4. Risk notes
        exp.risk_notes = self._build_risk_notes(signal)

        # 5. Summary
        exp.summary = self._build_summary(signal, exp, level)

        # 6. Detailed reasoning
        if level == ExplanationLevel.DETAILED:
            exp.detailed_reasoning = self._build_detailed_reasoning(signal, exp)

        return exp

    # ------------------------------------------------------------------
    # Attribution Computation
    # ------------------------------------------------------------------

    def _compute_factor_attributions(self, signal: Signal) -> List[FactorAttribution]:
        """Compute factor-level contributions to the signal."""
        contributions = signal.factor_contributions
        if not contributions:
            return []

        # Sort by absolute contribution
        sorted_items = sorted(contributions.items(), key=lambda x: abs(x[1]), reverse=True)

        attributions = []
        for factor_name, contrib in sorted_items[:10]:  # Top 10
            attributions.append(FactorAttribution(
                factor_name=factor_name,
                contribution=contrib,
                description=self._describe_factor(factor_name, contrib),
            ))

        return attributions

    def _compute_alpha_attributions(self, signal: Signal) -> List[AlphaAttribution]:
        """Compute alpha-level contributions to the signal."""
        alpha_scores = signal.alpha_scores
        if not alpha_scores:
            return []

        sorted_items = sorted(alpha_scores.items(), key=lambda x: abs(x[1]), reverse=True)

        attributions = []
        for alpha_id, score in sorted_items:
            attributions.append(AlphaAttribution(
                alpha_id=alpha_id,
                alpha_name=alpha_id.replace("_", " ").title(),
                contribution=score,
            ))

        return attributions

    # ------------------------------------------------------------------
    # Context Builders
    # ------------------------------------------------------------------

    def _build_summary(self, signal: Signal, exp: SignalExplanation,
                       level: ExplanationLevel) -> str:
        """Build the summary text."""
        template = self._explanation_templates.get(signal.direction, "{direction} {instrument}: {reason}")

        # Build reason from top factors
        if exp.top_factors:
            top_reasons = [f"{f.factor_name}({f.contribution:+.2f})" for f in exp.top_factors[:3]]
            reason = ", ".join(top_reasons)
        else:
            reason = signal.reason or "No specific factors identified"

        summary = template.format(
            instrument=signal.instrument,
            direction=signal.direction.value,
            strength=signal.strength.value,
            confidence=signal.confidence,
            reason=reason,
        )

        if level in (ExplanationLevel.STANDARD, ExplanationLevel.DETAILED):
            if exp.market_context:
                summary += f" | Market: {exp.market_context}"

        return summary

    def _build_market_context(self, signal: Signal) -> str:
        """Build market context notes."""
        regime = signal.market_regime
        if not regime:
            return ""

        context_parts = [f"Regime: {regime}"]

        # Add regime-specific notes
        regime_notes = {
            "BULL": "Favorable for momentum and growth strategies",
            "BEAR": "Defensive positioning; value and low-vol strategies preferred",
            "RANGE": "Mean-reversion opportunities; trend strategies underperform",
            "HIGH_VOLATILITY": "Elevated risk environment; reduce position sizes",
            "LOW_VOLATILITY": "Low dispersion; factor timing critical",
        }
        note = regime_notes.get(regime, "")
        if note:
            context_parts.append(note)

        return " | ".join(context_parts)

    def _build_risk_notes(self, signal: Signal) -> str:
        """Build risk-related notes."""
        notes = []

        confidence = signal.confidence
        if confidence < 0.3:
            notes.append("LOW CONFIDENCE: Consider reduced position size")
        elif confidence > 0.8:
            notes.append("HIGH CONFIDENCE: Standard risk parameters apply")

        risk_score = signal.metadata.get("risk_score")
        if risk_score is not None and risk_score > 0.7:
            notes.append(f"Elevated risk score: {risk_score:.2f}")

        return "; ".join(notes) if notes else ""

    def _build_detailed_reasoning(self, signal: Signal, exp: SignalExplanation) -> str:
        """Build a detailed multi-paragraph reasoning text."""
        parts = []

        # Header
        parts.append(f"Signal Analysis: {signal.signal_id}")
        parts.append(f"Instrument: {signal.instrument}")
        parts.append(f"Direction: {signal.direction.value} | Confidence: {signal.confidence:.2%}")
        parts.append("")

        # Factor breakdown
        if exp.top_factors:
            parts.append("Factor Contributions:")
            for f in exp.top_factors:
                parts.append(f"  - {f.factor_name}: {f.contribution:+.4f} ({f.description})")
            parts.append("")

        # Alpha breakdown
        if exp.alpha_breakdown:
            parts.append("Alpha Model Contributions:")
            for a in exp.alpha_breakdown:
                parts.append(f"  - {a.alpha_name}: {a.contribution:+.4f}")
            parts.append("")

        # Market context
        if exp.market_context:
            parts.append(f"Market Context: {exp.market_context}")
            parts.append("")

        # Risk notes
        if exp.risk_notes:
            parts.append(f"Risk Notes: {exp.risk_notes}")
            parts.append("")

        # Tags
        if signal.tags:
            parts.append(f"Tags: {', '.join(signal.tags)}")

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _describe_factor(self, factor_name: str, contribution: float) -> str:
        """Generate a human-readable description for a factor."""
        direction = "positive" if contribution > 0 else "negative"
        magnitude = "strong" if abs(contribution) > 0.5 else "moderate" if abs(contribution) > 0.2 else "weak"
        return f"{magnitude} {direction} contribution"

    # ------------------------------------------------------------------
    # Batch Operations
    # ------------------------------------------------------------------

    async def explain_batch(self, signals: List[Signal],
                            level: ExplanationLevel = ExplanationLevel.STANDARD) -> Dict[str, str]:
        """Generate explanations for a batch of signals."""
        results = {}
        for signal in signals:
            exp = await self._build_explanation(signal, level)
            results[signal.signal_id] = exp.summary
        return results
