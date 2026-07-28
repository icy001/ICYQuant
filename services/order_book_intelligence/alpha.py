"""Microstructure Alpha Generator — synthesize order book signals into alpha.

Combines order imbalance, liquidity, iceberg detection, toxicity, and
order flow metrics into actionable microstructure alpha signals for
short-term trading and execution optimization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AlphaSignalType(str, Enum):
    """Type of microstructure alpha signal."""

    MOMENTUM = "momentum"  # Directional momentum from imbalance
    REVERSAL = "reversal"  # Mean reversion signal
    BREAKOUT = "breakout"  # Liquidity wall breach signal
    EXECUTION = "execution"  # Optimal execution timing
    LIQUIDITY = "liquidity"  # Liquidity-driven opportunity


class SignalStrength(str, Enum):
    """Alpha signal strength classification."""

    WEAK = "weak"  # < 0.3
    MODERATE = "moderate"  # 0.3–0.6
    STRONG = "strong"  # 0.6–0.8
    VERY_STRONG = "very_strong"  # > 0.8


class SignalDirection(str, Enum):
    """Signal direction."""

    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class MicroAlphaSignal:
    """Microstructure alpha signal.

    Attributes:
        signal_type: Type of alpha signal.
        direction: LONG, SHORT, or FLAT.
        strength: Signal strength classification.
        alpha_score: Normalized alpha score (-1 to +1).
        confidence: Signal confidence (0–1).
        expected_horizon_sec: Expected signal duration in seconds.
        components: Breakdown of component contributions.
        reasoning: Human-readable rationale.
        timestamp: Signal generation time.
    """

    signal_type: AlphaSignalType
    direction: SignalDirection = SignalDirection.FLAT
    strength: SignalStrength = SignalStrength.WEAK
    alpha_score: float = 0.0
    confidence: float = 0.0
    expected_horizon_sec: float = 60.0
    components: dict[str, float] = field(default_factory=dict)
    reasoning: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_actionable(self) -> bool:
        """Whether the signal is strong enough to act on."""
        return self.strength in (SignalStrength.STRONG, SignalStrength.VERY_STRONG) and abs(self.alpha_score) > 0.5

    @property
    def magnitude(self) -> float:
        """Absolute alpha score magnitude."""
        return abs(self.alpha_score)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "signal_type": self.signal_type.value,
            "direction": self.direction.value,
            "strength": self.strength.value,
            "alpha_score": round(self.alpha_score, 4),
            "confidence": round(self.confidence, 4),
            "expected_horizon_sec": round(self.expected_horizon_sec, 2),
            "is_actionable": self.is_actionable,
            "components": {k: round(v, 4) for k, v in self.components.items()},
            "reasoning": self.reasoning,
        }


# ---------------------------------------------------------------------------
# MicrostructureAlphaGenerator
# ---------------------------------------------------------------------------


class MicrostructureAlphaGenerator:
    """Microstructure alpha signal generator.

    Synthesizes signals from order book intelligence components:
    - Order imbalance → directional momentum
    - Liquidity walls → breakout/reversal signals
    - Iceberg detection → institutional flow signal
    - Toxicity → execution timing
    - Hidden liquidity → liquidity premium

    Attributes:
        component_weights: Weights for each signal component.
        signal_thresholds: Thresholds for signal strength classification.
        history: Generated alpha signals.
    """

    # Default weights for component blend
    COMPONENT_WEIGHTS: dict[str, float] = {
        "imbalance": 0.35,      # Order imbalance signal
        "liquidity_wall": 0.15,  # Wall support/resistance
        "toxicity": 0.20,        # Inverted: high toxicity = bearish
        "iceberg": 0.15,         # Iceberg sentiment
        "hidden_liquidity": 0.10,  # Hidden liquidity premium
        "institutional_flow": 0.05, # Net institutional flow
    }

    SIGNAL_THRESHOLDS: dict[SignalStrength, tuple[float, float]] = {
        SignalStrength.WEAK: (0.0, 0.3),
        SignalStrength.MODERATE: (0.3, 0.6),
        SignalStrength.STRONG: (0.6, 0.8),
        SignalStrength.VERY_STRONG: (0.8, 1.0),
    }

    def __init__(
        self,
        weights: Optional[dict[str, float]] = None,
    ) -> None:
        """Initialize the microstructure alpha generator.

        Args:
            weights: Custom component weights (merges with defaults).
        """
        self.weights = {**self.COMPONENT_WEIGHTS, **(weights or {})}
        self.history: list[MicroAlphaSignal] = []

    # ------------------------------------------------------------------
    # Main Entry Point
    # ------------------------------------------------------------------

    def generate(
        self,
        imbalance: float,
        toxicity: float,
        wall_imbalance: float = 0.0,
        iceberg_confidence: float = 0.0,
        hidden_liquidity_conf: float = 0.0,
        institutional_flow: float = 0.0,
    ) -> dict[str, Any]:
        """Generate microstructure alpha signal.

        Args:
            imbalance: Order imbalance score (-1 to +1).
            toxicity: Order flow toxicity score (0–1).
            wall_imbalance: Wall imbalance (-1 to +1, bid-heavy = positive).
            iceberg_confidence: Max iceberg detection confidence (0–1).
            hidden_liquidity_conf: Hidden liquidity confidence (0–1).
            institutional_flow: Net institutional flow signal (-1 to +1).

        Returns:
            Dict with alpha score and signal details.
        """
        # Component contributions
        components = {
            "imbalance": imbalance * self.weights.get("imbalance", 0.35),
            "toxicity": -toxicity * self.weights.get("toxicity", 0.20),  # inverted
            "liquidity_wall": wall_imbalance * self.weights.get("liquidity_wall", 0.15),
            "iceberg": iceberg_confidence * self.weights.get("iceberg", 0.15),
            "hidden_liquidity": hidden_liquidity_conf * self.weights.get("hidden_liquidity", 0.10),
            "institutional_flow": institutional_flow * self.weights.get("institutional_flow", 0.05),
        }

        alpha = sum(components.values())
        alpha = max(-1.0, min(1.0, alpha))

        return {
            "alpha": alpha,
            "components": components,
        }

    def synthesize(
        self,
        imbalance: float = 0.0,
        toxicity: float = 0.0,
        wall_imbalance: float = 0.0,
        iceberg_confidence: float = 0.0,
        hidden_liquidity_conf: float = 0.0,
        institutional_flow: float = 0.0,
        snapshot_imbalance: Optional[float] = None,
        queue_fill_prob: Optional[float] = None,
    ) -> MicroAlphaSignal:
        """Synthesize full alpha signal from all available metrics.

        Args:
            imbalance: Order imbalance score (-1 to +1).
            toxicity: Order flow toxicity (0–1).
            wall_imbalance: Wall strength imbalance (-1 to +1).
            iceberg_confidence: Iceberg detection confidence.
            hidden_liquidity_conf: Hidden liquidity confidence.
            institutional_flow: Net institutional flow signal.
            snapshot_imbalance: Additional snapshot-level imbalance.
            queue_fill_prob: Queue fill probability (for execution alpha).

        Returns:
            MicroAlphaSignal with full analysis.
        """
        result = self.generate(
            imbalance=imbalance,
            toxicity=toxicity,
            wall_imbalance=wall_imbalance,
            iceberg_confidence=iceberg_confidence,
            hidden_liquidity_conf=hidden_liquidity_conf,
            institutional_flow=institutional_flow,
        )

        alpha = result["alpha"]
        magnitude = abs(alpha)

        # Determine direction
        if alpha > 0.15:
            direction = SignalDirection.LONG
        elif alpha < -0.15:
            direction = SignalDirection.SHORT
        else:
            direction = SignalDirection.FLAT

        # Determine signal type
        signal_type = self._classify_type(result["components"])

        # Classify strength
        strength = SignalStrength.WEAK
        for st, (lo, hi) in self.SIGNAL_THRESHOLDS.items():
            if lo <= magnitude < hi:
                strength = st
                break
        if magnitude >= 0.8:
            strength = SignalStrength.VERY_STRONG

        # Confidence
        confidence = self._compute_confidence(result["components"])

        # Expected horizon (shorter for stronger signals)
        horizon = max(5.0, 120.0 * (1.0 - magnitude))

        # Reasoning
        reasoning = self._build_reasoning(result["components"], direction)

        signal = MicroAlphaSignal(
            signal_type=signal_type,
            direction=direction,
            strength=strength,
            alpha_score=alpha,
            confidence=confidence,
            expected_horizon_sec=horizon,
            components=result["components"],
            reasoning=reasoning,
        )

        self.history.append(signal)
        return signal

    # ------------------------------------------------------------------
    # Signal Classification & Reasoning
    # ------------------------------------------------------------------

    def _classify_type(self, components: dict[str, float]) -> AlphaSignalType:
        """Classify signal type based on dominant component."""
        abs_components = {k: abs(v) for k, v in components.items()}
        dominant = max(abs_components, key=abs_components.get)

        type_map = {
            "imbalance": AlphaSignalType.MOMENTUM,
            "liquidity_wall": AlphaSignalType.BREAKOUT,
            "toxicity": AlphaSignalType.EXECUTION,
            "iceberg": AlphaSignalType.MOMENTUM,
            "hidden_liquidity": AlphaSignalType.LIQUIDITY,
            "institutional_flow": AlphaSignalType.MOMENTUM,
        }

        return type_map.get(dominant, AlphaSignalType.MOMENTUM)

    def _compute_confidence(self, components: dict[str, float]) -> float:
        """Compute signal confidence from component agreement.

        Higher agreement = higher confidence.
        """
        values = list(components.values())
        if not values:
            return 0.0

        positives = sum(1 for v in values if v > 0.05)
        negatives = sum(1 for v in values if v < -0.05)
        total_significant = positives + negatives

        if total_significant == 0:
            return 0.2  # No agreement

        # Agreement ratio
        agreement = max(positives, negatives) / total_significant
        # Magnitude bonus
        magnitude = sum(abs(v) for v in values) / len(values)

        return min(1.0, agreement * 0.7 + magnitude * 2.0 * 0.3)

    def _build_reasoning(
        self,
        components: dict[str, float],
        direction: SignalDirection,
    ) -> str:
        """Build human-readable reasoning string."""
        parts = []

        imb = components.get("imbalance", 0)
        if abs(imb) > 0.05:
            parts.append(f"Imbalance {'bullish' if imb > 0 else 'bearish'} ({imb:+.3f})")

        tox = components.get("toxicity", 0)
        if abs(tox) > 0.05:
            parts.append(f"Toxicity {'signal' if tox < 0 else 'signal'} ({tox:+.3f})")

        wall = components.get("liquidity_wall", 0)
        if abs(wall) > 0.03:
            parts.append(f"Wall {'support' if wall > 0 else 'resistance'} ({wall:+.3f})")

        iceberg = components.get("iceberg", 0)
        if abs(iceberg) > 0.03:
            parts.append(f"Iceberg detected ({iceberg:+.3f})")

        if not parts:
            return "No significant microstructure signals"

        conclusion = (
            "Long bias" if direction == SignalDirection.LONG
            else "Short bias" if direction == SignalDirection.SHORT
            else "Neutral"
        )
        return "; ".join(parts) + f". Conclusion: {conclusion}"

    # ------------------------------------------------------------------
    # Convenience Methods
    # ------------------------------------------------------------------

    def quick_generate(
        self,
        imbalance: float,
        toxicity: float,
    ) -> dict[str, Any]:
        """Quick alpha generation from core metrics.

        Args:
            imbalance: Order imbalance score.
            toxicity: Order flow toxicity.

        Returns:
            Dict with alpha score and direction.
        """
        result = self.generate(imbalance=imbalance, toxicity=toxicity)
        alpha = result["alpha"]
        direction = "LONG" if alpha > 0.1 else "SHORT" if alpha < -0.1 else "FLAT"
        return {
            "alpha": round(alpha, 4),
            "direction": direction,
            "components": {k: round(v, 4) for k, v in result["components"].items()},
        }

    def last_result(self) -> Optional[MicroAlphaSignal]:
        """Return the most recent alpha signal."""
        return self.history[-1] if self.history else None

    def clear(self) -> None:
        """Reset signal history."""
        self.history.clear()
