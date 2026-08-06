"""Feature Engineering — institutional feature generation from market data.

Supports::

    Price Feature, Volume Feature, Volatility Feature,
    Fundamental Feature, Alternative Feature, Custom Feature

All features are generated through a unified pipeline for consistency.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .factor_context import FactorContext

logger = logging.getLogger(__name__)


class FeatureType(str, Enum):
    """Supported feature categories."""

    PRICE = "price"
    VOLUME = "volume"
    VOLATILITY = "volatility"
    FUNDAMENTAL = "fundamental"
    ALTERNATIVE = "alternative"
    CUSTOM = "custom"


@dataclass
class PriceFeature:
    """Price-derived features: momentum, reversal, trend, etc."""

    name: str
    lookback: int = 20
    method: str = "momentum"  # momentum, reversal, breakout, ma_cross
    params: Dict[str, Any] = field(default_factory=dict)

    def compute(self, prices: List[float]) -> float:
        if self.method == "momentum":
            if len(prices) < 2:
                return 0.0
            return (prices[-1] / prices[0] - 1) if prices[0] != 0 else 0.0
        elif self.method == "reversal":
            if len(prices) < 2:
                return 0.0
            return (prices[0] / prices[-1] - 1) if prices[-1] != 0 else 0.0
        return 0.0


@dataclass
class VolumeFeature:
    """Volume-derived features: volume ratio, VWAP deviation, turnover."""

    name: str
    lookback: int = 20
    method: str = "volume_ratio"
    params: Dict[str, Any] = field(default_factory=dict)

    def compute(self, volumes: List[float]) -> float:
        if self.method == "volume_ratio":
            if len(volumes) < 2:
                return 0.0
            avg_vol = sum(volumes[:-1]) / max(len(volumes) - 1, 1)
            return (volumes[-1] / avg_vol - 1) if avg_vol > 0 else 0.0
        return 0.0


@dataclass
class VolatilityFeature:
    """Volatility-derived features: historical vol, GARCH, ATR, beta."""

    name: str
    lookback: int = 20
    method: str = "historical_vol"
    params: Dict[str, Any] = field(default_factory=dict)

    def compute(self, returns: List[float]) -> float:
        if self.method == "historical_vol":
            if len(returns) < 2:
                return 0.0
            mean_r = sum(returns) / len(returns)
            variance = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
            return variance ** 0.5
        return 0.0


@dataclass
class FundamentalFeature:
    """Fundamental-derived features: PE, PB, ROE, growth, quality scores."""

    name: str
    field: str = ""  # e.g., pe_ttm, pb, roe, revenue_growth
    params: Dict[str, Any] = field(default_factory=dict)

    def compute(self, values: Dict[str, float]) -> float:
        return values.get(self.field, 0.0)


@dataclass
class AlternativeFeature:
    """Alternative data features: sentiment, news, ESG, satellite, etc."""

    name: str
    source: str = ""  # e.g., news_sentiment, social_media, satellite
    params: Dict[str, Any] = field(default_factory=dict)

    def compute(self, data: Any) -> float:
        return float(data) if data is not None else 0.0


@dataclass
class CustomFeature:
    """User-defined custom features with arbitrary computation."""

    name: str
    compute_fn: Optional[Callable] = None
    params: Dict[str, Any] = field(default_factory=dict)

    def compute(self, data: Any) -> float:
        if self.compute_fn:
            return float(self.compute_fn(data, **self.params))
        return 0.0


class FeatureEngine:
    """Institutional feature generation engine.

    Generates features from raw market data through a unified pipeline:
    1. Define feature specifications
    2. Load required data
    3. Compute feature values
    4. Validate and output

    Usage::

        engine = FeatureEngine()
        feature = PriceFeature(name="momentum_20d", lookback=20, method="momentum")
        value = feature.compute(prices)
    """

    def __init__(
        self,
        context: Optional[FactorContext] = None,
    ) -> None:
        self._context = context or FactorContext()
        self._feature_specs: Dict[str, Any] = {}
        self._generated_count: int = 0

    @property
    def generated_count(self) -> int:
        return self._generated_count

    def register_feature(self, name: str, feature: Any) -> None:
        """Register a feature specification."""
        self._feature_specs[name] = feature
        logger.debug("Registered feature: %s", name)

    def get_feature(self, name: str) -> Optional[Any]:
        return self._feature_specs.get(name)

    def list_features(self) -> List[str]:
        return list(self._feature_specs.keys())

    def create_price_feature(
        self,
        name: str,
        lookback: int = 20,
        method: str = "momentum",
        **params,
    ) -> PriceFeature:
        feature = PriceFeature(name=name, lookback=lookback, method=method, params=params)
        self.register_feature(name, feature)
        return feature

    def create_volume_feature(
        self,
        name: str,
        lookback: int = 20,
        method: str = "volume_ratio",
        **params,
    ) -> VolumeFeature:
        feature = VolumeFeature(name=name, lookback=lookback, method=method, params=params)
        self.register_feature(name, feature)
        return feature

    def create_volatility_feature(
        self,
        name: str,
        lookback: int = 20,
        method: str = "historical_vol",
        **params,
    ) -> VolatilityFeature:
        feature = VolatilityFeature(name=name, lookback=lookback, method=method, params=params)
        self.register_feature(name, feature)
        return feature

    def create_fundamental_feature(
        self,
        name: str,
        field: str = "",
        **params,
    ) -> FundamentalFeature:
        feature = FundamentalFeature(name=name, field=field, params=params)
        self.register_feature(name, feature)
        return feature

    def create_alternative_feature(
        self,
        name: str,
        source: str = "",
        **params,
    ) -> AlternativeFeature:
        feature = AlternativeFeature(name=name, source=source, params=params)
        self.register_feature(name, feature)
        return feature

    def create_custom_feature(
        self,
        name: str,
        compute_fn: Optional[Callable] = None,
        **params,
    ) -> CustomFeature:
        feature = CustomFeature(name=name, compute_fn=compute_fn, params=params)
        self.register_feature(name, feature)
        return feature

    async def generate_features(
        self,
        feature_names: List[str],
        data: Dict[str, Any],
    ) -> Dict[str, float]:
        """Generate feature values from data for given feature specifications."""
        results: Dict[str, float] = {}
        for name in feature_names:
            spec = self._feature_specs.get(name)
            if spec is None:
                logger.warning("Feature not found: %s", name)
                results[name] = 0.0
                continue
            try:
                if isinstance(spec, PriceFeature):
                    prices = data.get("prices", data.get(name, []))
                    results[name] = spec.compute(prices)
                elif isinstance(spec, VolumeFeature):
                    volumes = data.get("volumes", data.get(name, []))
                    results[name] = spec.compute(volumes)
                elif isinstance(spec, VolatilityFeature):
                    returns = data.get("returns", data.get(name, []))
                    results[name] = spec.compute(returns)
                elif isinstance(spec, FundamentalFeature):
                    values = data.get("fundamentals", data.get(name, {}))
                    results[name] = spec.compute(values)
                elif isinstance(spec, AlternativeFeature):
                    raw = data.get("alternative", data.get(name))
                    results[name] = spec.compute(raw)
                elif isinstance(spec, CustomFeature):
                    raw = data.get(name)
                    results[name] = spec.compute(raw)
            except Exception as exc:
                logger.error("Feature %s computation failed: %s", name, exc)
                results[name] = 0.0

        self._generated_count += len(results)
        return results

    def feature_types_summary(self) -> Dict[str, int]:
        """Count features by type."""
        counts: Dict[str, int] = {}
        for spec in self._feature_specs.values():
            if isinstance(spec, PriceFeature):
                counts["price"] = counts.get("price", 0) + 1
            elif isinstance(spec, VolumeFeature):
                counts["volume"] = counts.get("volume", 0) + 1
            elif isinstance(spec, VolatilityFeature):
                counts["volatility"] = counts.get("volatility", 0) + 1
            elif isinstance(spec, FundamentalFeature):
                counts["fundamental"] = counts.get("fundamental", 0) + 1
            elif isinstance(spec, AlternativeFeature):
                counts["alternative"] = counts.get("alternative", 0) + 1
            elif isinstance(spec, CustomFeature):
                counts["custom"] = counts.get("custom", 0) + 1
        return counts
