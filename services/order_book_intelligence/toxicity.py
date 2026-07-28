"""Order Flow Toxicity Analyzer — VPIN, adverse selection & execution risk.

Measures order flow toxicity (VPIN-based), adverse selection probability,
and toxicity-driven execution risk to inform optimal execution strategies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ToxicityLevel(str, Enum):
    """Order flow toxicity classification."""

    LOW = "low"  # Safe to execute aggressively
    MODERATE = "moderate"  # Caution advised
    HIGH = "high"  # Use passive/patient execution
    EXTREME = "extreme"  # Withdraw from market


class AdverseSelection(str, Enum):
    """Adverse selection risk level."""

    NEGLIGIBLE = "negligible"
    NOTICEABLE = "noticeable"
    SIGNIFICANT = "significant"
    SEVERE = "severe"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class ToxicityAssessment:
    """Order flow toxicity assessment result.

    Attributes:
        vpin: Volume-synchronized probability of informed trading.
        toxicity_score: Normalized toxicity score (0–1).
        toxicity_level: Toxicity classification.
        adverse_selection: Adverse selection risk level.
        execution_risk: Recommended execution risk premium.
        recommended_urgency: How urgently to execute (0 = patient, 1 = aggressive).
        buy_volume_classified: Volume classified as buy-initiated.
        sell_volume_classified: Volume classified as sell-initiated.
        volume_bucket_count: Number of volume buckets analyzed.
        timestamp: Assessment time.
    """

    vpin: float
    toxicity_score: float = 0.0
    toxicity_level: ToxicityLevel = ToxicityLevel.LOW
    adverse_selection: AdverseSelection = AdverseSelection.NEGLIGIBLE
    execution_risk: float = 0.0
    recommended_urgency: float = 0.5
    buy_volume_classified: float = 0.0
    sell_volume_classified: float = 0.0
    volume_bucket_count: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_toxic(self) -> bool:
        """Whether the order flow is considered toxic."""
        return self.toxicity_level in (ToxicityLevel.HIGH, ToxicityLevel.EXTREME)

    @property
    def requires_defensive_execution(self) -> bool:
        """Whether defensive execution strategy is needed."""
        return self.toxicity_score > 0.5

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "vpin": round(self.vpin, 4),
            "toxicity_score": round(self.toxicity_score, 4),
            "toxicity_level": self.toxicity_level.value,
            "adverse_selection": self.adverse_selection.value,
            "execution_risk": round(self.execution_risk, 4),
            "recommended_urgency": round(self.recommended_urgency, 4),
            "is_toxic": self.is_toxic,
            "volume_buckets": self.volume_bucket_count,
        }


# ---------------------------------------------------------------------------
# OrderFlowToxicityAnalyzer
# ---------------------------------------------------------------------------


class OrderFlowToxicityAnalyzer:
    """Order flow toxicity analyzer using VPIN methodology.

    VPIN (Volume-synchronized Probability of Informed Trading) measures
    the imbalance between buy and sell volume within volume buckets,
    indicating the presence of informed traders and adverse selection.

    Attributes:
        bucket_size: Volume per VPIN bucket (as fraction of avg daily vol).
        num_buckets: Number of buckets used in rolling VPIN.
        volume_history: Cumulative volume tracker.
        bucket_imbalances: Recent bucket buy-sell imbalances.
        history: Past toxicity assessments.
    """

    # Toxicity thresholds
    TOXICITY_THRESHOLDS: dict[ToxicityLevel, float] = {
        ToxicityLevel.LOW: 0.3,
        ToxicityLevel.MODERATE: 0.5,
        ToxicityLevel.HIGH: 0.7,
        ToxicityLevel.EXTREME: 1.0,
    }

    # VPIN-guided execution urgency
    URGENCY_MAP: dict[str, float] = {
        "low": 0.8,     # Safe to be aggressive
        "moderate": 0.5,  # Balanced
        "high": 0.3,      # Be patient
        "extreme": 0.1,   # Minimize footprint
    }

    def __init__(
        self,
        bucket_size: float = 50000.0,
        num_buckets: int = 50,
    ) -> None:
        """Initialize the toxicity analyzer.

        Args:
            bucket_size: Volume per VPIN bucket.
            num_buckets: Number of rolling buckets.
        """
        self.bucket_size = bucket_size
        self.num_buckets = num_buckets
        self.volume_buckets: list[float] = []  # buy-sell imbalance per bucket
        self.current_bucket_volume: float = 0.0
        self.current_bucket_buy: float = 0.0
        self.current_bucket_sell: float = 0.0
        self.history: list[ToxicityAssessment] = []

    # ------------------------------------------------------------------
    # Main Entry Point
    # ------------------------------------------------------------------

    def score(
        self,
        vpin: float,
    ) -> float:
        """Compute normalized toxicity score from VPIN value.

        Args:
            vpin: Raw VPIN value (typically 0–1).

        Returns:
            Normalized toxicity score (0–1).
        """
        return min(1.0, max(0.0, vpin))

    def feed_trade(
        self,
        volume: float,
        is_buy_initiated: bool,
    ) -> None:
        """Feed a single trade into the VPIN calculation.

        Args:
            volume: Trade volume.
            is_buy_initiated: Whether the trade was buyer-initiated.
        """
        self.current_bucket_volume += volume
        if is_buy_initiated:
            self.current_bucket_buy += volume
        else:
            self.current_bucket_sell += volume

        # Check if bucket is full
        if self.current_bucket_volume >= self.bucket_size:
            imbalance = abs(self.current_bucket_buy - self.current_bucket_sell)
            self.volume_buckets.append(imbalance)

            # Rotate: keep only num_buckets
            while len(self.volume_buckets) > self.num_buckets:
                self.volume_buckets.pop(0)

            # Reset current bucket
            self.current_bucket_volume = 0.0
            self.current_bucket_buy = 0.0
            self.current_bucket_sell = 0.0

    def calculate_vpin(self) -> float:
        """Calculate current VPIN value.

        VPIN = average(bucket_imbalance) / bucket_size

        Returns:
            Current VPIN value (0–1).
        """
        if not self.volume_buckets:
            return 0.0

        avg_imbalance = sum(self.volume_buckets) / len(self.volume_buckets)
        vpin = avg_imbalance / self.bucket_size
        return min(1.0, max(0.0, vpin))

    def assess(
        self,
        trades: Optional[list[dict[str, Any]]] = None,
    ) -> ToxicityAssessment:
        """Generate full toxicity assessment.

        Args:
            trades: Optional list of recent trades to feed first.

        Returns:
            ToxicityAssessment with VPIN, toxicity level, and execution guidance.
        """
        # Feed trades if provided
        if trades:
            for t in trades:
                volume = t.get("volume", 0.0)
                is_buy = t.get("is_buy_initiated", t.get("aggressor", "") == "buy")
                self.feed_trade(volume, is_buy)

        vpin = self.calculate_vpin()
        toxicity = self.score(vpin)

        # Classify
        level = ToxicityLevel.LOW
        for lvl, threshold in sorted(
            self.TOXICITY_THRESHOLDS.items(),
            key=lambda x: x[1],
        ):
            if toxicity >= threshold:
                level = lvl

        # Adverse selection
        if toxicity >= 0.7:
            adverse = AdverseSelection.SEVERE
        elif toxicity >= 0.5:
            adverse = AdverseSelection.SIGNIFICANT
        elif toxicity >= 0.3:
            adverse = AdverseSelection.NOTICEABLE
        else:
            adverse = AdverseSelection.NEGLIGIBLE

        # Execution risk premium (bps)
        execution_risk = toxicity * 20.0  # Up to 20bps risk premium

        # Urgency: invert toxicity
        urgency = self.URGENCY_MAP.get(level.value, 0.5)

        # Total classified volume
        buy_classified = sum(
            b for b in self.volume_buckets
        ) * 0.5 + self.current_bucket_buy
        sell_classified = sum(
            b for b in self.volume_buckets
        ) * 0.5 + self.current_bucket_sell

        assessment = ToxicityAssessment(
            vpin=vpin,
            toxicity_score=toxicity,
            toxicity_level=level,
            adverse_selection=adverse,
            execution_risk=execution_risk,
            recommended_urgency=urgency,
            buy_volume_classified=buy_classified,
            sell_volume_classified=sell_classified,
            volume_bucket_count=len(self.volume_buckets),
        )

        self.history.append(assessment)
        return assessment

    # ------------------------------------------------------------------
    # Execution Advice
    # ------------------------------------------------------------------

    def execution_advice(
        self,
        assessment: Optional[ToxicityAssessment] = None,
    ) -> dict[str, Any]:
        """Generate execution strategy advice based on toxicity.

        Args:
            assessment: Specific assessment (default: latest).

        Returns:
            Dict with execution recommendations.
        """
        assessment = assessment or (self.history[-1] if self.history else None)
        if not assessment:
            return {"strategy": "unknown", "reason": "no_data"}

        level = assessment.toxicity_level

        advice = {
            ToxicityLevel.LOW: {
                "strategy": "aggressive",
                "participation_rate": 0.30,
                "max_order_size_pct": 0.10,
                "reason": "Low toxicity: safe for aggressive execution",
            },
            ToxicityLevel.MODERATE: {
                "strategy": "balanced",
                "participation_rate": 0.15,
                "max_order_size_pct": 0.05,
                "reason": "Moderate toxicity: use balanced execution",
            },
            ToxicityLevel.HIGH: {
                "strategy": "passive",
                "participation_rate": 0.05,
                "max_order_size_pct": 0.02,
                "reason": "High toxicity: switch to passive/patient execution",
            },
            ToxicityLevel.EXTREME: {
                "strategy": "defensive",
                "participation_rate": 0.01,
                "max_order_size_pct": 0.01,
                "reason": "Extreme toxicity: minimize market footprint",
            },
        }

        return {
            **advice[level],
            "vpin": round(assessment.vpin, 4),
            "execution_risk_bps": round(assessment.execution_risk, 2),
        }

    # ------------------------------------------------------------------
    # Convenience Methods
    # ------------------------------------------------------------------

    def quick_assess(
        self,
        vpin: float,
    ) -> dict[str, Any]:
        """Quick toxicity assessment from VPIN value.

        Args:
            vpin: VPIN value (0–1).

        Returns:
            Dict with toxicity score and level.
        """
        assessment = self.assess()
        return {
            "vpin": round(vpin, 4),
            "toxicity_score": round(self.score(vpin), 4),
            "toxicity_level": assessment.toxicity_level.value,
            "is_toxic": self.score(vpin) > 0.5,
        }

    def last_result(self) -> Optional[ToxicityAssessment]:
        """Return the most recent assessment."""
        return self.history[-1] if self.history else None

    def clear(self) -> None:
        """Reset VPIN state."""
        self.volume_buckets.clear()
        self.current_bucket_volume = 0.0
        self.current_bucket_buy = 0.0
        self.current_bucket_sell = 0.0
        self.history.clear()
