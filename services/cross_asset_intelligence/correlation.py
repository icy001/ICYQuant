"""Correlation Engine.

Computes dynamic, rolling, and regime-based correlations across
asset classes. Supports multiple correlation methods and detects
correlation breakdowns (diversification failures) during crises.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .relationship import AssetRelationship, RelationshipType, AssetClass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CorrelationMethod(str, Enum):
    """Correlation computation method."""

    PEARSON = "pearson"
    SPEARMAN = "spearman"
    ROLLING = "rolling"
    DYNAMIC = "dynamic"
    REGIME = "regime"


class CorrelationRegime(str, Enum):
    """Correlation regime classification."""

    NORMAL = "normal"
    CRISIS_CONVERGENCE = "crisis_convergence"
    DECOUPLING = "decoupling"
    INVERSE = "inverse"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class CorrelationResult:
    """Result of cross-asset correlation analysis.

    Attributes:
        pairs: List of asset pair correlations.
        average_correlation: Average across all pairs.
        correlation_regime: Overall correlation regime.
        diversification_score: Portfolio diversification quality.
        description: Human-readable summary.
        confidence: Analysis confidence.
        timestamp: Analysis timestamp.
    """

    pairs: list[AssetRelationship] = field(default_factory=list)
    average_correlation: float = 0.0
    correlation_regime: CorrelationRegime = CorrelationRegime.NORMAL
    diversification_score: float = 0.5
    description: str = ""
    confidence: float = 0.5
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_diversified(self) -> bool:
        return self.diversification_score >= 0.6

    @property
    def is_crisis(self) -> bool:
        return self.correlation_regime == CorrelationRegime.CRISIS_CONVERGENCE

    @property
    def crisis_convergence_risk(self) -> float:
        """Risk that correlations go to 1 during market stress."""
        if self.correlation_regime == CorrelationRegime.CRISIS_CONVERGENCE:
            return 0.8
        elif self.correlation_regime == CorrelationRegime.DECOUPLING:
            return 0.3
        return 0.1 if self.average_correlation < 0.5 else 0.4


class CorrelationEngine:
    """Computes and analyzes cross-asset correlations.

    Supports multiple correlation methods (Pearson, Spearman, rolling,
    dynamic weighting) and detects correlation regimes including crisis
    convergence when diversification breaks down.

    Attributes:
        price_histories: Per-asset price histories.
        method: Default correlation method.
        window: Rolling window size.
        regime_window: Window for regime detection.
    """

    def __init__(self) -> None:
        self.price_histories: dict[str, list[float]] = {}
        self.method: CorrelationMethod = CorrelationMethod.PEARSON
        self.window: int = 60
        self.regime_window: int = 20
        self._correlation_cache: dict[str, float] = {}

    # --- Price Management ---

    def add_price(self, asset: str, price: float) -> None:
        """Add a price data point for an asset.

        Args:
            asset: Asset identifier.
            price: Current price.
        """
        if asset not in self.price_histories:
            self.price_histories[asset] = []
        self.price_histories[asset].append(price)
        if len(self.price_histories[asset]) > 500:
            self.price_histories[asset] = self.price_histories[asset][-500:]

    def add_prices(self, prices: dict[str, float]) -> None:
        """Add prices for multiple assets at once.

        Args:
            prices: Dict of asset -> price.
        """
        for asset, price in prices.items():
            self.add_price(asset, price)

    # --- Correlation Computation ---

    def compute(self, asset_a: str, asset_b: str,
                method: CorrelationMethod | None = None) -> float:
        """Compute correlation between two assets.

        Args:
            asset_a: First asset identifier.
            asset_b: Second asset identifier.
            method: Correlation method (defaults to self.method).

        Returns:
            Correlation coefficient [-1.0, 1.0].
        """
        m = method or self.method
        returns_a = self._get_returns(asset_a)
        returns_b = self._get_returns(asset_b)

        if not returns_a or not returns_b:
            return 0.0

        # Align lengths
        min_len = min(len(returns_a), len(returns_b))
        ra = returns_a[-min_len:]
        rb = returns_b[-min_len:]

        if len(ra) < 3:
            return 0.0

        if m == CorrelationMethod.PEARSON:
            return self._pearson(ra, rb)
        elif m == CorrelationMethod.SPEARMAN:
            return self._spearman(ra, rb)
        elif m == CorrelationMethod.DYNAMIC:
            return self._dynamic_correlation(ra, rb)
        return self._pearson(ra, rb)

    def compute_matrix(self, assets: list[str]) -> dict[tuple[str, str], float]:
        """Compute correlation matrix for a set of assets.

        Args:
            assets: List of asset identifiers.

        Returns:
            Dict mapping (asset_a, asset_b) -> correlation.
        """
        matrix: dict[tuple[str, str], float] = {}
        for i, a in enumerate(assets):
            for b in assets[i + 1:]:
                corr = self.compute(a, b)
                matrix[(a, b)] = corr
                matrix[(b, a)] = corr
                self._correlation_cache[f"{a}|{b}"] = corr
        return matrix

    def compute_relationship(self, asset_a: str, asset_b: str,
                              class_a: AssetClass | None = None,
                              class_b: AssetClass | None = None) -> AssetRelationship:
        """Compute full relationship between two assets.

        Args:
            asset_a: First asset identifier.
            asset_b: Second asset identifier.
            class_a: Asset class of asset_a.
            class_b: Asset class of asset_b.

        Returns:
            AssetRelationship with correlation and classification.
        """
        corr = self.compute(asset_a, asset_b)
        rel_type = self._classify_relationship(corr)
        confidence = self._correlation_confidence(asset_a, asset_b, corr)

        return AssetRelationship(
            asset_a=asset_a,
            asset_b=asset_b,
            correlation=corr,
            relationship_type=rel_type,
            confidence=confidence,
            window=self.window,
            class_a=class_a,
            class_b=class_b,
        )

    # --- Rolling & Regime Analysis ---

    def compute_rolling(self, asset_a: str, asset_b: str,
                        window: int | None = None) -> list[float]:
        """Compute rolling correlation series.

        Args:
            asset_a: First asset.
            asset_b: Second asset.
            window: Rolling window size.

        Returns:
            List of rolling correlation values.
        """
        w = window or self.regime_window
        returns_a = self._get_returns(asset_a)
        returns_b = self._get_returns(asset_b)

        if len(returns_a) < w or len(returns_b) < w:
            return []

        min_len = min(len(returns_a), len(returns_b))
        ra = returns_a[-min_len:]
        rb = returns_b[-min_len:]

        rolling: list[float] = []
        for i in range(w, len(ra) + 1):
            corr = self._pearson(ra[i - w:i], rb[i - w:i])
            rolling.append(corr)
        return rolling

    def detect_regime(self, asset_a: str, asset_b: str) -> CorrelationRegime:
        """Detect correlation regime between two assets.

        Args:
            asset_a: First asset.
            asset_b: Second asset.

        Returns:
            Current correlation regime.
        """
        rolling = self.compute_rolling(asset_a, asset_b)
        if len(rolling) < 5:
            return CorrelationRegime.NORMAL

        current = rolling[-1]
        avg = sum(rolling) / len(rolling)
        trend = self._trend_slope(rolling[-10:]) if len(rolling) >= 10 else 0.0

        # Crisis convergence: correlation spiking above 0.7
        if current > 0.7 and current > avg + 0.2:
            return CorrelationRegime.CRISIS_CONVERGENCE

        # Decoupling: correlation dropping toward/through 0
        if current < 0.2 and trend < 0 and avg > 0.3:
            return CorrelationRegime.DECOUPLING

        # Inverse: strong negative correlation
        if current < -0.5:
            return CorrelationRegime.INVERSE

        return CorrelationRegime.NORMAL

    def analyze(self) -> CorrelationResult:
        """Run full correlation analysis across all tracked assets.

        Returns:
            CorrelationResult with pairs, averages, and regime analysis.
        """
        assets = list(self.price_histories.keys())
        if len(assets) < 2:
            return CorrelationResult(
                pairs=[],
                average_correlation=0.0,
                correlation_regime=CorrelationRegime.NORMAL,
                diversification_score=0.5,
                description="Insufficient assets for correlation analysis",
                confidence=0.2,
            )

        pairs: list[AssetRelationship] = []
        correlations: list[float] = []

        for i, a in enumerate(assets):
            for b in assets[i + 1:]:
                rel = self.compute_relationship(a, b)
                pairs.append(rel)
                correlations.append(rel.correlation)

        avg_corr = sum(correlations) / len(correlations) if correlations else 0.0
        regime = self._determine_overall_regime(correlations)
        div_score = self._compute_diversification_score(pairs, avg_corr)
        confidence = self._compute_matrix_confidence(assets, pairs)
        description = self._generate_matrix_description(assets, pairs, avg_corr, regime, div_score)

        return CorrelationResult(
            pairs=pairs,
            average_correlation=avg_corr,
            correlation_regime=regime,
            diversification_score=div_score,
            description=description,
            confidence=confidence,
        )

    # --- Matrix Analysis ---

    def get_average_correlation(self) -> float:
        """Get average correlation across all asset pairs."""
        assets = list(self.price_histories.keys())
        if len(assets) < 2:
            return 0.0
        corrs: list[float] = []
        for i, a in enumerate(assets):
            for b in assets[i + 1:]:
                corrs.append(self.compute(a, b))
        return sum(corrs) / len(corrs) if corrs else 0.0

    def find_highest_correlated(self, asset: str) -> tuple[str, float] | None:
        """Find the asset most correlated to target.

        Args:
            asset: Target asset.

        Returns:
            Tuple of (asset_id, correlation) or None.
        """
        assets = [a for a in self.price_histories if a != asset]
        if not assets:
            return None
        best = max(assets, key=lambda a: abs(self.compute(asset, a)))
        corr = self.compute(asset, best)
        return (best, corr)

    def find_lowest_correlated(self, asset: str) -> tuple[str, float] | None:
        """Find the best diversifier (lowest correlation) for an asset.

        Args:
            asset: Target asset.

        Returns:
            Tuple of (asset_id, correlation) or None.
        """
        assets = [a for a in self.price_histories if a != asset]
        if not assets:
            return None
        best = min(assets, key=lambda a: abs(self.compute(asset, a)))
        corr = self.compute(asset, best)
        return (best, corr)

    def get_hedge_candidates(self, asset: str, min_neg: float = -0.3) -> list[tuple[str, float]]:
        """Find assets with negative correlation to target.

        Args:
            asset: Target asset to hedge.
            min_neg: Minimum negative correlation threshold.

        Returns:
            List of (asset_id, correlation) sorted by most negative.
        """
        candidates: list[tuple[str, float]] = []
        for other in self.price_histories:
            if other == asset:
                continue
            corr = self.compute(asset, other)
            if corr <= min_neg:
                candidates.append((other, corr))
        candidates.sort(key=lambda x: x[1])
        return candidates

    # --- Internal ---

    def _get_returns(self, asset: str) -> list[float]:
        prices = self.price_histories.get(asset, [])
        if len(prices) < 2:
            return []
        returns: list[float] = []
        for i in range(1, len(prices)):
            if prices[i - 1] == 0:
                continue
            returns.append((prices[i] - prices[i - 1]) / prices[i - 1])
        return returns

    def _pearson(self, x: list[float], y: list[float]) -> float:
        n = len(x)
        if n < 3:
            return 0.0
        mx = sum(x) / n
        my = sum(y) / n
        cov = 0.0
        var_x = 0.0
        var_y = 0.0
        for i in range(n):
            dx = x[i] - mx
            dy = y[i] - my
            cov += dx * dy
            var_x += dx * dx
            var_y += dy * dy
        if var_x == 0 or var_y == 0:
            return 0.0
        corr = cov / math.sqrt(var_x * var_y)
        return max(-1.0, min(1.0, corr))

    def _spearman(self, x: list[float], y: list[float]) -> float:
        def _rank(vals: list[float]) -> list[float]:
            sorted_pairs = sorted(enumerate(vals), key=lambda p: p[1])
            ranks = [0.0] * len(vals)
            for rank, (idx, _) in enumerate(sorted_pairs):
                ranks[idx] = float(rank)
            return ranks
        return self._pearson(_rank(x), _rank(y))

    def _dynamic_correlation(self, x: list[float], y: list[float]) -> float:
        """Exponentially-weighted dynamic correlation."""
        n = len(x)
        if n < 3:
            return 0.0
        decay = 0.94
        weights = [decay ** (n - 1 - i) for i in range(n)]
        w_total = sum(weights)
        wmx = sum(weights[i] * x[i] for i in range(n)) / w_total
        wmy = sum(weights[i] * y[i] for i in range(n)) / w_total
        cov = 0.0
        var_x = 0.0
        var_y = 0.0
        for i in range(n):
            dx = x[i] - wmx
            dy = y[i] - wmy
            cov += weights[i] * dx * dy
            var_x += weights[i] * dx * dx
            var_y += weights[i] * dy * dy
        if var_x == 0 or var_y == 0:
            return 0.0
        cov /= w_total
        var_x /= w_total
        var_y /= w_total
        corr = cov / math.sqrt(var_x * var_y)
        return max(-1.0, min(1.0, corr))

    def _classify_relationship(self, corr: float) -> RelationshipType:
        if corr >= 0.8:
            return RelationshipType.STRONG_POSITIVE
        elif corr >= 0.5:
            return RelationshipType.MODERATE_POSITIVE
        elif corr >= 0.1:
            return RelationshipType.WEAK_POSITIVE
        elif corr <= -0.8:
            return RelationshipType.STRONG_NEGATIVE
        elif corr <= -0.5:
            return RelationshipType.MODERATE_NEGATIVE
        elif corr <= -0.1:
            return RelationshipType.WEAK_NEGATIVE
        return RelationshipType.UNCORRELATED

    def _correlation_confidence(self, asset_a: str, asset_b: str, corr: float) -> float:
        confidence = 0.3
        abs_corr = abs(corr)
        if abs_corr > 0.7:
            confidence += 0.3
        elif abs_corr > 0.3:
            confidence += 0.15
        hist_a = self.price_histories.get(asset_a, [])
        if len(hist_a) > self.window:
            confidence += 0.2
        elif len(hist_a) > 30:
            confidence += 0.1
        return min(1.0, confidence)

    def _trend_slope(self, values: list[float]) -> float:
        n = len(values)
        if n < 2:
            return 0.0
        mx = (n - 1) / 2.0
        my = sum(values) / n
        cov_xy = 0.0
        var_x = 0.0
        for i in range(n):
            dx = i - mx
            dy = values[i] - my
            cov_xy += dx * dy
            var_x += dx * dx
        return cov_xy / var_x if var_x > 0 else 0.0

    def _determine_overall_regime(self, correlations: list[float]) -> CorrelationRegime:
        if not correlations:
            return CorrelationRegime.NORMAL
        avg = sum(correlations) / len(correlations)
        above_07 = sum(1 for c in correlations if c > 0.7)
        if above_07 / len(correlations) > 0.5:
            return CorrelationRegime.CRISIS_CONVERGENCE
        if avg > 0.6:
            return CorrelationRegime.CRISIS_CONVERGENCE
        if avg < -0.3:
            return CorrelationRegime.INVERSE
        negatives = sum(1 for c in correlations if c < 0)
        if negatives / len(correlations) > 0.5:
            return CorrelationRegime.DECOUPLING
        return CorrelationRegime.NORMAL

    def _compute_diversification_score(self, pairs: list[AssetRelationship],
                                        avg_corr: float) -> float:
        if not pairs:
            return 0.3
        # Lower average correlation = better diversification
        score = 1.0 - avg_corr
        # Penalize if many strong positive correlations
        strong = sum(1 for p in pairs if p.is_strong and p.is_positive)
        score -= 0.1 * (strong / len(pairs))
        # Reward negative correlations
        negatives = sum(1 for p in pairs if p.is_negative)
        score += 0.15 * (negatives / len(pairs))
        return max(0.0, min(1.0, score))

    def _compute_matrix_confidence(self, assets: list[str],
                                     pairs: list[AssetRelationship]) -> float:
        confidence = 0.3
        if len(assets) >= 5:
            confidence += 0.15
        min_history = min(
            (len(self.price_histories.get(a, [])) for a in assets),
            default=0,
        )
        if min_history > self.window:
            confidence += 0.25
        elif min_history > 30:
            confidence += 0.1
        if pairs:
            confident_pairs = sum(1 for p in pairs if p.confidence > 0.5)
            confidence += 0.15 * (confident_pairs / len(pairs))
        return min(1.0, confidence)

    def _generate_matrix_description(self, assets: list[str],
                                       pairs: list[AssetRelationship],
                                       avg_corr: float,
                                       regime: CorrelationRegime,
                                       div_score: float) -> str:
        context = {
            CorrelationRegime.NORMAL: "Normal diversification",
            CorrelationRegime.CRISIS_CONVERGENCE: "⚠ Crisis convergence - diversification failing",
            CorrelationRegime.DECOUPLING: "Asset decoupling detected",
            CorrelationRegime.INVERSE: "Inverse correlations dominate",
        }
        return (f"{len(assets)} assets, {len(pairs)} pairs | "
                f"Corr={avg_corr:.2f} | "
                f"{context.get(regime, 'Unknown')} | "
                f"Diversification={div_score:.2f}")

    def clear(self) -> None:
        self.price_histories.clear()
        self._correlation_cache.clear()
