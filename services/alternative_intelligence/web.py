"""Web Intelligence Engine — monitors website traffic, search trends, product rankings, hiring data."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .record import (
    AlternativeFeature,
    AlternativeRecord,
    SignalStrength,
    WebMetric,
)


# ---------------------------------------------------------------------------
# Metric type configuration
# ---------------------------------------------------------------------------

_METRIC_CONFIG: dict[str, dict] = {
    "website_traffic": {
        "description": "Website visitor traffic volume",
        "positive_direction": "up",  # more traffic → positive
        "z_scale": 2.0,
    },
    "search_trend": {
        "description": "Search volume trend (e.g., Google Trends)",
        "positive_direction": "up",
        "z_scale": 2.5,
    },
    "product_rank": {
        "description": "Product ranking in marketplace / app store",
        "positive_direction": "up",  # higher rank → better
        "z_scale": 1.5,
    },
    "hiring": {
        "description": "Job posting count / hiring activity",
        "positive_direction": "up",  # more hiring → growth signal
        "z_scale": 1.8,
    },
    "app_downloads": {
        "description": "App download volume",
        "positive_direction": "up",
        "z_scale": 2.2,
    },
    "page_views": {
        "description": "Page view count on key pages",
        "positive_direction": "up",
        "z_scale": 1.5,
    },
    "bounce_rate": {
        "description": "Website bounce rate",
        "positive_direction": "down",  # lower bounce → better engagement
        "z_scale": 1.0,
    },
    "time_on_site": {
        "description": "Average time spent on site",
        "positive_direction": "up",
        "z_scale": 1.0,
    },
}


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class WebIntelligenceResult:
    """Result of web intelligence analysis."""

    metric_type: str = ""
    current_value: float = 0.0
    change_pct: float = 0.0
    direction: str = "neutral"  # up, down, neutral
    signal_strength: SignalStrength = SignalStrength.NEUTRAL
    confidence: float = 0.5
    summary: str = ""
    features: list[AlternativeFeature] = field(default_factory=list)

    @property
    def is_growth_signal(self) -> bool:
        return self.direction == "up" and self.signal_strength in (
            SignalStrength.STRONG, SignalStrength.MODERATE
        )

    @property
    def is_decline_signal(self) -> bool:
        return self.direction == "down" and self.signal_strength in (
            SignalStrength.STRONG, SignalStrength.MODERATE
        )


@dataclass
class AssetWebProfile:
    """Aggregated web intelligence for a specific asset."""

    asset_tag: str
    metrics: dict[str, WebIntelligenceResult] = field(default_factory=dict)
    growth_score: float = 0.0  # composite growth score [0, 1]
    momentum: str = "neutral"  # accelerating, decelerating, stable
    features: list[AlternativeFeature] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class WebIntelligenceEngine:
    """Analyzes web-based alternative data for business intelligence signals.

    Capabilities:
    - Website traffic analysis
    - Search trend monitoring
    - Product ranking tracking
    - Hiring data analysis
    - App download monitoring
    - Composite growth scoring
    """

    def __init__(self) -> None:
        self._results: list[WebIntelligenceResult] = []
        self._asset_data: dict[str, list[WebMetric]] = defaultdict(list)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, data: WebMetric | AlternativeRecord | dict) -> WebIntelligenceResult:
        """Analyze a web metric and return structured intelligence."""
        if isinstance(data, WebMetric):
            metric_type = data.metric_type
            value = data.value
            change_pct = data.change_pct
            tags = data.asset_tags
        elif isinstance(data, AlternativeRecord):
            metric_type = data.metadata.get("metric_type", "unknown")
            value = float(data.metadata.get("value", 0))
            change_pct = float(data.metadata.get("change_pct", 0))
            tags = data.asset_tags
        elif isinstance(data, dict):
            metric_type = data.get("metric_type", "unknown")
            value = float(data.get("value", 0))
            change_pct = float(data.get("change_pct", 0))
            tags = data.get("asset_tags", [])
        else:
            metric_type = "unknown"
            value = 0.0
            change_pct = 0.0
            tags = []

        # Determine direction and signal
        direction = self._classify_direction(metric_type, change_pct)
        signal_strength = self._classify_signal(change_pct)
        confidence = self._estimate_confidence(metric_type, change_pct)

        # Features
        features = self._generate_features(metric_type, value, change_pct, tags)

        result = WebIntelligenceResult(
            metric_type=metric_type,
            current_value=value,
            change_pct=change_pct,
            direction=direction,
            signal_strength=signal_strength,
            confidence=confidence,
            summary=(
                f"{metric_type}: {value:.1f} "
                f"(Δ{change_pct:+.1f}%) → {direction} signal, {signal_strength.value}"
            ),
            features=features,
        )
        self._results.append(result)

        # Track per asset
        for tag in tags:
            if isinstance(data, WebMetric):
                self._asset_data[tag].append(data)

        return result

    def analyze_batch(
        self, metrics: list[WebMetric | AlternativeRecord | dict]
    ) -> list[WebIntelligenceResult]:
        """Analyze a batch of web metrics."""
        return [self.analyze(m) for m in metrics]

    def get_asset_profile(self, asset_tag: str) -> AssetWebProfile:
        """Get aggregated web intelligence profile for an asset."""
        metrics = self._asset_data.get(asset_tag, [])
        if not metrics:
            return AssetWebProfile(asset_tag=asset_tag)

        # Analyze all metrics for this asset
        results: dict[str, list[WebIntelligenceResult]] = defaultdict(list)
        for m in metrics:
            r = self.analyze(m)
            results[r.metric_type].append(r)

        # Aggregate per metric type (take latest)
        aggregated: dict[str, WebIntelligenceResult] = {}
        for mtype, mresults in results.items():
            aggregated[mtype] = mresults[-1]

        # Composite growth score
        growth_score = self._compute_growth_score(list(aggregated.values()))
        momentum = self._compute_momentum(list(aggregated.values()))

        # Features
        features = self._generate_asset_features(asset_tag, aggregated, growth_score)

        return AssetWebProfile(
            asset_tag=asset_tag,
            metrics=aggregated,
            growth_score=growth_score,
            momentum=momentum,
            features=features,
        )

    def get_growth_leaders(self) -> list[tuple[str, float]]:
        """Get assets ranked by growth score."""
        scored: list[tuple[str, float]] = []
        for tag in self._asset_data:
            profile = self.get_asset_profile(tag)
            scored.append((tag, profile.growth_score))
        return sorted(scored, key=lambda x: x[1], reverse=True)

    @property
    def history(self) -> list[WebIntelligenceResult]:
        return list(self._results)

    def clear(self) -> None:
        self._results.clear()
        self._asset_data.clear()

    # ------------------------------------------------------------------
    # Internal: Direction & Signal Classification
    # ------------------------------------------------------------------

    def _classify_direction(self, metric_type: str, change_pct: float) -> str:
        """Classify metric direction as up/down/neutral."""
        if abs(change_pct) < 0.5:
            return "neutral"

        config = _METRIC_CONFIG.get(metric_type, {"positive_direction": "up"})
        is_positive = change_pct > 0
        pos_dir = config["positive_direction"]

        if pos_dir == "down":
            is_positive = not is_positive

        return "up" if is_positive else "down"

    def _classify_signal(self, change_pct: float) -> SignalStrength:
        """Classify the signal strength based on change magnitude."""
        abs_change = abs(change_pct)
        if abs_change >= 20:
            return SignalStrength.STRONG
        elif abs_change >= 5:
            return SignalStrength.MODERATE
        elif abs_change >= 1:
            return SignalStrength.WEAK
        return SignalStrength.NEUTRAL

    def _estimate_confidence(self, metric_type: str, change_pct: float) -> float:
        """Estimate confidence in the web intelligence signal."""
        abs_change = abs(change_pct)

        # Larger changes → more confident
        change_factor = min(0.3, abs_change / 50.0)

        # Known metric types have higher base confidence
        base = 0.5 if metric_type in _METRIC_CONFIG else 0.35

        return min(0.9, base + change_factor)

    def _compute_growth_score(self, results: list[WebIntelligenceResult]) -> float:
        """Compute composite growth score [0, 1] from multiple web metrics."""
        if not results:
            return 0.0

        scores: list[float] = []
        for r in results:
            config = _METRIC_CONFIG.get(r.metric_type, {})
            pos_dir = config.get("positive_direction", "up")
            scale = config.get("z_scale", 1.0)

            # Map change to [0, 1]
            if pos_dir == "down":
                raw = -r.change_pct
            else:
                raw = r.change_pct

            # Sigmoid-like mapping
            normalized = 1.0 / (1.0 + max(0, 5.0 - raw * 0.5)) if raw > 0 else max(0, 0.5 + raw * 0.02)
            scores.append(normalized)

        return sum(scores) / len(scores)

    def _compute_momentum(self, results: list[WebIntelligenceResult]) -> str:
        """Determine if metrics are accelerating, decelerating, or stable."""
        directions = [r.direction for r in results]
        up_count = directions.count("up")
        down_count = directions.count("down")

        if up_count > len(directions) * 0.6:
            return "accelerating"
        elif down_count > len(directions) * 0.6:
            return "decelerating"
        return "stable"

    # ------------------------------------------------------------------
    # Internal: Feature Generation
    # ------------------------------------------------------------------

    def _generate_features(
        self,
        metric_type: str,
        value: float,
        change_pct: float,
        tags: list[str],
    ) -> list[AlternativeFeature]:
        """Generate alpha features from web metrics."""
        features: list[AlternativeFeature] = []

        for tag in tags:
            signal = self._classify_signal(change_pct)
            features.append(
                AlternativeFeature(
                    name=f"web_{metric_type}_{tag}",
                    value=change_pct,
                    category="web",
                    asset_tag=tag,
                    z_score=change_pct / 10.0,  # approx normalization
                    signal_strength=signal,
                )
            )

        return features

    def _generate_asset_features(
        self,
        asset_tag: str,
        metrics: dict[str, WebIntelligenceResult],
        growth_score: float,
    ) -> list[AlternativeFeature]:
        """Generate asset-level features."""
        features: list[AlternativeFeature] = []

        # Composite growth feature
        signal = (
            SignalStrength.STRONG
            if growth_score > 0.7
            else SignalStrength.MODERATE
            if growth_score > 0.5
            else SignalStrength.WEAK
        )
        features.append(
            AlternativeFeature(
                name=f"web_growth_composite_{asset_tag}",
                value=growth_score,
                category="web",
                asset_tag=asset_tag,
                z_score=(growth_score - 0.5) * 3.0,
                signal_strength=signal,
            )
        )

        return features
