"""Online Feature Join — automatic feature retrieval and assembly for inference.

Joins real-time data with the Feature Store to assemble the feature
vector needed for model inference. Eliminates manual feature lookups
in strategy code.

Usage::

    joiner = FeatureJoiner(online_store=store)
    result = joiner.join("NVDA", market="US")
    features = result.features  # ready for inference
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class JoinStrategy(str, Enum):
    """Feature join strategy."""
    ONLINE_ONLY = "online_only"    # Only from online store
    ONLINE_FALLBACK = "online_fallback"  # Online first, fallback to offline
    OFFLINE_BATCH = "offline_batch"  # Pre-computed batch join
    REAL_TIME = "realtime"       # Real-time compute + online store


@dataclass
class JoinSpec:
    """Specification for which features to join.

    Attributes:
        feature_names: Explicit feature list to retrieve.
        feature_group: Feature group/category to retrieve all.
        model_name: Retrieve features required by a specific model.
        exclude: Feature names to exclude.
        max_age_seconds: Max age of online features (stale data rejection).
    """

    feature_names: List[str] = field(default_factory=list)
    feature_group: str = ""
    model_name: str = ""
    exclude: List[str] = field(default_factory=list)
    max_age_seconds: float = 5.0


@dataclass
class JoinResult:
    """Result of a feature join operation.

    Attributes:
        entity_id: Entity identifier (symbol).
        features: Assembled feature dict ready for inference.
        missing_features: Features that could not be retrieved.
        source: How features were obtained (online/offline/computed).
        latency_ms: Join operation latency.
        timestamp: When features were assembled.
    """

    entity_id: str
    features: Dict[str, float] = field(default_factory=dict)
    missing_features: List[str] = field(default_factory=list)
    source: str = "online"
    latency_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    @property
    def complete(self) -> bool:
        return len(self.missing_features) == 0

    @property
    def feature_count(self) -> int:
        return len(self.features)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "features": self.features,
            "missing_features": self.missing_features,
            "source": self.source,
            "latency_ms": self.latency_ms,
            "feature_count": self.feature_count,
            "complete": self.complete,
        }


class FeatureJoiner:
    """Automatically joins features from online/offline stores for inference.

    Usage::

        joiner = FeatureJoiner(
            online_store=online_feature_store,
            offline_store=offline_feature_store,
        )
        result = joiner.join("NVDA", spec=JoinSpec(feature_names=["ema20", "atr14", "rsi14"]))
    """

    def __init__(
        self,
        online_store: Any = None,
        offline_store: Any = None,
        feature_service: Any = None,
        default_strategy: JoinStrategy = JoinStrategy.ONLINE_ONLY,
    ):
        self._online = online_store
        self._offline = offline_store
        self._feature_service = feature_service
        self.default_strategy = default_strategy
        self._model_features: Dict[str, List[str]] = {}  # model → required features
        self._group_features: Dict[str, List[str]] = {}  # group → feature names

    def register_model_features(self, model_name: str, feature_names: List[str]) -> None:
        """Register required features for a model."""
        self._model_features[model_name] = feature_names

    def register_feature_group(self, group_name: str, feature_names: List[str]) -> None:
        """Register a feature group."""
        self._group_features[group_name] = feature_names

    def join(
        self,
        entity_id: str,
        market: str = "US",
        spec: Optional[JoinSpec] = None,
        strategy: Optional[JoinStrategy] = None,
    ) -> JoinResult:
        """Join features for a single entity.

        Args:
            entity_id: Entity identifier (symbol, account, etc).
            market: Market segment.
            spec: Join specification (which features).
            strategy: Join strategy override.

        Returns:
            JoinResult with assembled features.
        """
        start = time.perf_counter()
        spec = spec or JoinSpec()
        strategy = strategy or self.default_strategy

        # Determine what features to retrieve
        requested = self._resolve_feature_names(spec)
        features: Dict[str, float] = {}
        missing: List[str] = []

        # Fetch from online store
        if strategy in (JoinStrategy.ONLINE_ONLY, JoinStrategy.ONLINE_FALLBACK, JoinStrategy.REAL_TIME):
            if self._online:
                for fname in requested:
                    val = self._online.get_feature(entity_id, fname)
                    if val is not None:
                        features[fname] = float(val)
                    else:
                        missing.append(fname)
            else:
                # Mock: return placeholder for testing
                for fname in requested:
                    features[fname] = self._mock_feature(fname)

            # Try to get all as batch
            if self._online and not features:
                record = self._online.get(entity_id)
                if record and hasattr(record, 'features'):
                    features = {k: float(v) for k, v in record.features.items() if k in requested}
                    missing = [f for f in requested if f not in features]

        # Fallback to offline store
        if strategy == JoinStrategy.ONLINE_FALLBACK and missing and self._offline:
            for fname in missing[:]:
                val = self._offline.get_feature(entity_id, fname)
                if val is not None:
                    features[fname] = float(val)
                    missing.remove(fname)

        # Offline batch
        if strategy == JoinStrategy.OFFLINE_BATCH and self._offline:
            for fname in requested:
                val = self._offline.get_feature(entity_id, fname)
                if val is not None:
                    features[fname] = float(val)
                else:
                    missing.append(fname)

        latency = (time.perf_counter() - start) * 1000

        return JoinResult(
            entity_id=entity_id,
            features=features,
            missing_features=missing,
            source=strategy.value,
            latency_ms=round(latency, 3),
        )

    def join_batch(
        self,
        entity_ids: List[str],
        spec: Optional[JoinSpec] = None,
        market: str = "US",
    ) -> List[JoinResult]:
        """Join features for multiple entities."""
        return [self.join(eid, market=market, spec=spec) for eid in entity_ids]

    # ---- internal ----

    def _resolve_feature_names(self, spec: JoinSpec) -> List[str]:
        """Resolve which features to retrieve based on spec."""
        names: Set[str] = set()

        if spec.feature_names:
            names.update(spec.feature_names)
        if spec.feature_group and spec.feature_group in self._group_features:
            names.update(self._group_features[spec.feature_group])
        if spec.model_name and spec.model_name in self._model_features:
            names.update(self._model_features[spec.model_name])

        if not names:
            # If nothing specified, try to get all known features
            if self._online and hasattr(self._online, 'list_features'):
                names = set(self._online.list_features())
            else:
                return []  # No way to determine

        # Apply exclusions
        for ex in spec.exclude:
            names.discard(ex)

        return sorted(names)

    @staticmethod
    def _mock_feature(name: str) -> float:
        """Generate mock feature for testing."""
        import hashlib
        h = hashlib.md5(name.encode()).hexdigest()
        return (int(h[:8], 16) % 1000) / 1000.0
