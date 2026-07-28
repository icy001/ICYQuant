"""Alternative Data Fusion Engine — fuses alternative data signals with price and macro data."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .record import (
    AlphaCandidate,
    AlternativeFeature,
    FusionResult,
    SignalStrength,
)


# ---------------------------------------------------------------------------
# Fusion configuration
# ---------------------------------------------------------------------------

# Default component weights for multi-source fusion
_DEFAULT_WEIGHTS: dict[str, float] = {
    "traditional": 0.40,  # price-based alpha
    "macro": 0.25,        # macro intelligence alpha
    "alternative": 0.35,  # alternative data alpha
}

# Regime-specific weight adjustments
_REGIME_WEIGHTS: dict[str, dict[str, float]] = {
    "trending": {
        "traditional": 0.45,
        "macro": 0.20,
        "alternative": 0.35,
    },
    "high_volatility": {
        "traditional": 0.25,
        "macro": 0.35,
        "alternative": 0.40,
    },
    "low_volatility": {
        "traditional": 0.30,
        "macro": 0.20,
        "alternative": 0.50,
    },
    "event_driven": {
        "traditional": 0.20,
        "macro": 0.25,
        "alternative": 0.55,
    },
}

# Correlation penalty matrix (simplified)
_CORRELATION_PENALTY: float = 0.15  # penalty per overlapping signal


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class FusionReport:
    """Complete fusion report for multiple assets."""

    results: list[FusionResult] = field(default_factory=list)
    regime: str = "normal"
    weights_used: dict[str, float] = field(default_factory=dict)
    summary: str = ""

    @property
    def top_fused(self) -> list[FusionResult]:
        """Get results sorted by fused alpha magnitude."""
        return sorted(self.results, key=lambda r: abs(r.fused_alpha), reverse=True)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class AlternativeDataFusion:
    """Fuses alternative data signals with traditional price data and macro data.

    Produces multi-source alpha signals that combine:
    - Price-based alpha (momentum, mean reversion, etc.)
    - Macro regime alpha (cycle, liquidity, policy)
    - Alternative alpha (news, social, web, satellite)

    Capabilities:
    - Weighted fusion with regime-dependent weights
    - Correlation penalty for overlapping signals
    - Confidence aggregation
    - Asset-level fusion results
    """

    def __init__(self) -> None:
        self._history: list[FusionReport] = []
        self._asset_fusions: dict[str, list[FusionResult]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def combine(
        self,
        data: dict[str, dict] | None = None,
        *,
        traditional_alphas: dict[str, float] | None = None,
        macro_alphas: dict[str, float] | None = None,
        alternative_alphas: dict[str, float] | None = None,
        regime: str = "normal",
        custom_weights: dict[str, float] | None = None,
    ) -> FusionReport:
        """Combine multi-source alpha signals into fused results.

        Args:
            data: Optional dict with keys 'traditional', 'macro', 'alternative',
                  each mapping asset_tag → alpha score.
            traditional_alphas: Price-based alpha scores per asset.
            macro_alphas: Macro alpha scores per asset.
            alternative_alphas: Alternative alpha scores per asset.
            regime: Market regime for weight selection.
            custom_weights: Override default/regime weights.
        """
        # Extract from data dict if provided
        if data is not None:
            trad = data.get("traditional", {})
            macro = data.get("macro", {})
            alt = data.get("alternative", {})
        else:
            trad = traditional_alphas or {}
            macro = macro_alphas or {}
            alt = alternative_alphas or {}

        # Determine weights
        if custom_weights:
            weights = custom_weights
        else:
            weights = _REGIME_WEIGHTS.get(regime, _DEFAULT_WEIGHTS).copy()

        # Collect all assets
        all_assets: set[str] = set()
        all_assets.update(trad.keys())
        all_assets.update(macro.keys())
        all_assets.update(alt.keys())

        results: list[FusionResult] = []

        for asset in sorted(all_assets):
            t_alpha = trad.get(asset, 0.0)
            m_alpha = macro.get(asset, 0.0)
            a_alpha = alt.get(asset, 0.0)

            # Correlation penalty: if all three agree strongly, apply penalty
            # (might be overlapping information)
            penalty = 0.0
            signals = [t_alpha, m_alpha, a_alpha]
            sign_matches = sum(
                1 for i in range(len(signals))
                for j in range(i + 1, len(signals))
                if (signals[i] > 0 and signals[j] > 0) or (signals[i] < 0 and signals[j] < 0)
            )
            if sign_matches >= 2:
                # Apply penalty proportional to the strongest agreement
                max_abs = max(abs(s) for s in signals)
                penalty = _CORRELATION_PENALTY * sign_matches * max_abs

            # Weighted fusion
            fused = (
                t_alpha * weights.get("traditional", 0.4)
                + m_alpha * weights.get("macro", 0.25)
                + a_alpha * weights.get("alternative", 0.35)
            )
            fused -= penalty

            # Clamp to [-1, 1]
            fused = max(-1.0, min(1.0, fused))

            # Confidence: weighted average of signal strengths
            confidence = self._compute_fusion_confidence(
                t_alpha, m_alpha, a_alpha, weights, penalty
            )

            result = FusionResult(
                asset_tag=asset,
                traditional_alpha=round(t_alpha, 4),
                macro_alpha=round(m_alpha, 4),
                alternative_alpha=round(a_alpha, 4),
                fused_alpha=round(fused, 4),
                component_weights=weights.copy(),
                confidence=round(confidence, 3),
            )
            results.append(result)
            self._asset_fusions[asset].append(result)

        report = FusionReport(
            results=results,
            regime=regime,
            weights_used=weights,
            summary=f"Fusion for {len(results)} assets in {regime} regime: "
            f"{sum(1 for r in results if r.fused_alpha > 0.1)} bullish, "
            f"{sum(1 for r in results if r.fused_alpha < -0.1)} bearish",
        )
        self._history.append(report)

        return report

    def combine_from_candidates(
        self,
        candidates: list[AlphaCandidate],
        traditional_alphas: dict[str, float] | None = None,
        macro_alphas: dict[str, float] | None = None,
        regime: str = "normal",
    ) -> FusionReport:
        """Fuse alternative alpha candidates with traditional and macro alphas."""
        # Aggregate alternative candidates by asset
        alt_alphas: dict[str, list[float]] = defaultdict(list)
        for c in candidates:
            if c.feature.asset_tag:
                alt_alphas[c.feature.asset_tag].append(c.alpha_score)

        # Average per asset
        alternative_alphas = {
            asset: sum(scores) / len(scores)
            for asset, scores in alt_alphas.items()
        }

        return self.combine(
            traditional_alphas=traditional_alphas or {},
            macro_alphas=macro_alphas or {},
            alternative_alphas=alternative_alphas,
            regime=regime,
        )

    def get_asset_fusion_history(self, asset_tag: str) -> list[FusionResult]:
        """Get fusion history for a specific asset."""
        return self._asset_fusions.get(asset_tag, [])

    def get_latest_fusion(self, asset_tag: str) -> FusionResult | None:
        """Get the most recent fusion result for an asset."""
        history = self._asset_fusions.get(asset_tag, [])
        return history[-1] if history else None

    def get_regime_weights(self, regime: str) -> dict[str, float]:
        """Get the fusion weights for a specific regime."""
        return _REGIME_WEIGHTS.get(regime, _DEFAULT_WEIGHTS).copy()

    @property
    def history(self) -> list[FusionReport]:
        return list(self._history)

    def clear(self) -> None:
        self._history.clear()
        self._asset_fusions.clear()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _compute_fusion_confidence(
        self,
        t_alpha: float,
        m_alpha: float,
        a_alpha: float,
        weights: dict[str, float],
        penalty: float,
    ) -> float:
        """Compute overall confidence in the fused alpha."""
        # More agreement → higher confidence (before penalty)
        signals = [t_alpha, m_alpha, a_alpha]
        active_signals = sum(1 for s in signals if abs(s) > 0.05)

        if active_signals == 0:
            return 0.2

        # Average signal strength
        avg_strength = sum(abs(s) for s in signals) / 3.0

        # Base confidence
        base = 0.3 + avg_strength * 0.4

        # Boost for multi-signal agreement
        agreement_boost = (active_signals - 1) * 0.1

        # Penalty for over-correlation
        penalty_discount = penalty * 0.5

        return min(0.95, max(0.1, base + agreement_boost - penalty_discount))
