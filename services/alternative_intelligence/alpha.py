"""Alternative Alpha Discovery — converts alternative data features into tradable alpha signals."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .record import (
    AlphaCandidate,
    AlternativeFeature,
    SignalStrength,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Category weights for alpha generation
_CATEGORY_WEIGHTS: dict[str, float] = {
    "news": 0.25,
    "social": 0.20,
    "web": 0.20,
    "satellite": 0.20,
    "supply_chain": 0.15,
    "fusion": 0.30,  # fusion features get extra weight
}

# Minimum Z-score thresholds
_Z_THRESHOLDS: dict[str, float] = {
    "news": 0.5,
    "social": 0.6,
    "web": 0.4,
    "satellite": 0.4,
    "supply_chain": 0.5,
}


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class AlphaDiscoveryResult:
    """Result of alternative alpha discovery for a set of features."""

    candidates: list[AlphaCandidate] = field(default_factory=list)
    total_features_processed: int = 0
    actionable_candidates: int = 0
    by_asset: dict[str, list[AlphaCandidate]] = field(default_factory=dict)
    by_category: dict[str, list[AlphaCandidate]] = field(default_factory=dict)
    top_signals: list[AlphaCandidate] = field(default_factory=list)

    @property
    def has_actionable(self) -> bool:
        return self.actionable_candidates > 0


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class AlternativeAlphaDiscovery:
    """Converts alternative data features into alpha candidates for the alpha research engine.

    Pipeline:
    Raw Data → Feature → Alpha Candidate → Trading Signal

    Capabilities:
    - Feature-to-alpha transformation
    - Category-weighted scoring
    - Z-score normalization and thresholding
    - Signal decay modeling
    - Information coefficient estimation
    - Asset-level alpha aggregation
    """

    def __init__(self) -> None:
        self._history: list[AlphaDiscoveryResult] = []
        self._candidate_tracker: dict[str, list[AlphaCandidate]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, features: list[AlternativeFeature]) -> AlphaDiscoveryResult:
        """Generate alpha candidates from a list of alternative features."""
        candidates: list[AlphaCandidate] = []

        for feature in features:
            candidate = self._feature_to_candidate(feature)
            if candidate:
                candidates.append(candidate)

        # Sort by confidence descending
        candidates.sort(key=lambda c: (c.confidence * abs(c.alpha_score)), reverse=True)

        # Group by asset
        by_asset: dict[str, list[AlphaCandidate]] = defaultdict(list)
        for c in candidates:
            if c.feature.asset_tag:
                by_asset[c.feature.asset_tag].append(c)

        # Group by category
        by_category: dict[str, list[AlphaCandidate]] = defaultdict(list)
        for c in candidates:
            by_category[c.feature.category].append(c)

        # Track history
        for c in candidates:
            if c.feature.asset_tag:
                self._candidate_tracker[c.feature.asset_tag].append(c)

        actionable = [c for c in candidates if c.is_actionable]

        result = AlphaDiscoveryResult(
            candidates=candidates,
            total_features_processed=len(features),
            actionable_candidates=len(actionable),
            by_asset=dict(by_asset),
            by_category=dict(by_category),
            top_signals=actionable[:20],
        )
        self._history.append(result)

        return result

    def generate_from_multi_source(
        self,
        news_features: list[AlternativeFeature] | None = None,
        social_features: list[AlternativeFeature] | None = None,
        web_features: list[AlternativeFeature] | None = None,
        satellite_features: list[AlternativeFeature] | None = None,
    ) -> AlphaDiscoveryResult:
        """Generate alpha from multiple alternative data sources."""
        all_features: list[AlternativeFeature] = []
        for features in [news_features, social_features, web_features, satellite_features]:
            if features:
                all_features.extend(features)
        return self.generate(all_features)

    def get_asset_alpha_history(self, asset_tag: str) -> list[AlphaCandidate]:
        """Get historical alpha candidates for a specific asset."""
        return self._candidate_tracker.get(asset_tag, [])

    def get_top_assets(self, limit: int = 10) -> list[tuple[str, float]]:
        """Get assets ranked by average alpha score."""
        scores: dict[str, list[float]] = defaultdict(list)
        for asset, candidates in self._candidate_tracker.items():
            for c in candidates:
                scores[asset].append(c.alpha_score * c.confidence)

        avg_scores = [
            (asset, sum(s) / len(s)) for asset, s in scores.items()
        ]
        return sorted(avg_scores, key=lambda x: abs(x[1]), reverse=True)[:limit]

    @property
    def history(self) -> list[AlphaDiscoveryResult]:
        return list(self._history)

    def clear(self) -> None:
        self._history.clear()
        self._candidate_tracker.clear()

    # ------------------------------------------------------------------
    # Internal: Feature → Candidate Transformation
    # ------------------------------------------------------------------

    def _feature_to_candidate(self, feature: AlternativeFeature) -> AlphaCandidate | None:
        """Transform a single feature into an alpha candidate."""
        category = feature.category
        weight = _CATEGORY_WEIGHTS.get(category, 0.1)
        threshold = _Z_THRESHOLDS.get(category, 0.3)

        # Skip weak signals
        if abs(feature.z_score) < threshold:
            return None

        # Alpha score: z_score normalized and weighted
        alpha_score = self._sigmoid_transform(feature.z_score) * weight

        # Confidence from signal strength
        confidence = self._signal_to_confidence(feature.signal_strength)

        # Sharpe estimate based on z_score and category
        sharpe = abs(feature.z_score) * 0.5 * weight

        # IC estimate: correlation proxy from signal strength
        ic = {
            SignalStrength.STRONG: 0.08,
            SignalStrength.MODERATE: 0.04,
            SignalStrength.WEAK: 0.02,
            SignalStrength.NEUTRAL: 0.005,
            SignalStrength.CONTRARIAN: 0.03,
        }.get(feature.signal_strength, 0.02)

        # Decay half-life: news decays fast, satellite decays slow
        decay = {
            "news": 1.5,
            "social": 1.0,
            "web": 3.0,
            "satellite": 7.0,
            "supply_chain": 5.0,
        }.get(category, 2.0)

        return AlphaCandidate(
            feature=feature,
            alpha_score=round(alpha_score, 4),
            confidence=round(confidence, 3),
            sharpe_estimate=round(sharpe, 3),
            information_coefficient=round(ic, 4),
            decay_half_life=decay,
        )

    def _sigmoid_transform(self, z_score: float) -> float:
        """Transform z-score to [-1, 1] alpha score using sigmoid."""
        # 2 * sigmoid(z) - 1 maps to [-1, 1]
        import math
        try:
            sig = 1.0 / (1.0 + math.exp(-z_score))
            return 2.0 * sig - 1.0
        except OverflowError:
            return 1.0 if z_score > 0 else -1.0

    def _signal_to_confidence(self, signal: SignalStrength) -> float:
        """Map signal strength to confidence value."""
        return {
            SignalStrength.STRONG: 0.85,
            SignalStrength.MODERATE: 0.60,
            SignalStrength.WEAK: 0.35,
            SignalStrength.NEUTRAL: 0.20,
            SignalStrength.CONTRARIAN: 0.50,
        }.get(signal, 0.3)
