"""
ICYQuant Feature Adapter — Bridges online feature store with model inference.

Ensures feature contract consistency between training and inference:
  - Feature name mapping (training names → online store names)
  - Feature validation against model's expected schema
  - Feature enrichment from online feature store
  - Missing feature handling and default filling
  - Feature version tracking
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from .online_feature_provider import OnlineFeatureProvider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums & data
# ---------------------------------------------------------------------------

class FeatureStatus(str, Enum):
    """Status of a feature in the adapter."""
    PRESENT = "present"
    MISSING = "missing"
    DEFAULTED = "defaulted"
    TRANSFORMED = "transformed"
    ENRICHED = "enriched"
    INVALID = "invalid"


@dataclass
class FeatureSchema:
    """Expected feature schema for a model."""
    model_id: str
    required_features: List[str]
    optional_features: List[str] = field(default_factory=list)
    feature_types: Dict[str, str] = field(default_factory=dict)
    default_values: Dict[str, Any] = field(default_factory=dict)
    feature_aliases: Dict[str, str] = field(default_factory=dict)  # training_name → online_name

    def get_expected_features(self) -> Set[str]:
        return set(self.required_features) | set(self.optional_features)

    def has_feature(self, name: str) -> bool:
        return name in self.required_features or name in self.optional_features


# ---------------------------------------------------------------------------
# Feature Adapter
# ---------------------------------------------------------------------------

class FeatureAdapter:
    """Bridges online feature store and model inference.

    Responsibilities:
      1. Map training-time feature names to online store names
      2. Validate input features against model schema
      3. Fetch missing features from online store
      4. Apply default values for optional features
      5. Track feature version for reproducibility

    Usage::

        adapter = FeatureAdapter(online_provider)
        adapter.register_schema("nvda_model", schema)
        enriched = await adapter.enrich("nvda_model", {"momentum_20d": 0.05})
    """

    def __init__(
        self,
        provider: "OnlineFeatureProvider",
    ):
        self.provider = provider
        self._initialized = False

        # model_id → FeatureSchema
        self._schemas: Dict[str, FeatureSchema] = {}

        # Cache of feature name mappings
        self._name_cache: Dict[str, Dict[str, str]] = {}

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("FeatureAdapter initialized")

    # ------------------------------------------------------------------
    # Schema management
    # ------------------------------------------------------------------

    def register_schema(self, schema: FeatureSchema) -> None:
        """Register expected feature schema for a model.

        This enables validation and enrichment during inference.

        Args:
            schema: Feature schema specification.
        """
        self._schemas[schema.model_id] = schema
        logger.info(
            "Schema registered: %s (%d required, %d optional features)",
            schema.model_id,
            len(schema.required_features),
            len(schema.optional_features),
        )

    def unregister_schema(self, model_id: str) -> None:
        """Remove a model's feature schema."""
        self._schemas.pop(model_id, None)
        self._name_cache.pop(model_id, None)

    def get_schema(self, model_id: str) -> Optional[FeatureSchema]:
        """Get feature schema for a model."""
        return self._schemas.get(model_id)

    # ------------------------------------------------------------------
    # Feature enrichment
    # ------------------------------------------------------------------

    async def enrich(
        self,
        model_id: str,
        features: Dict[str, Any],
        *,
        symbols: Optional[List[str]] = None,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Enrich input features with online feature store data.

        Pipeline:
          1. Map feature names (training → online)
          2. Validate required features present
          3. Fetch missing features from online store
          4. Apply defaults for missing optional features
          5. Return enriched feature dict + version info

        Args:
            model_id: Model identifier.
            features: Input feature dictionary.
            symbols: Asset symbols for online feature lookup.
            timestamp: Point-in-time for historical feature values.

        Returns:
            Dict with 'features', 'feature_version', 'status', 'missing'.
        """
        schema = self._schemas.get(model_id)
        result: Dict[str, Any] = {
            "features": dict(features),
            "feature_version": None,
            "status": {},
            "missing": [],
            "enriched_from_store": [],
            "defaulted": [],
        }

        if schema is None:
            # No schema — just try to fetch what we can from the store
            enriched = await self.provider.get_features(
                model_id=model_id,
                feature_names=list(features.keys()),
                symbols=symbols,
                timestamp=timestamp,
            )
            if enriched:
                result["features"].update(enriched.get("features", {}))
                result["feature_version"] = enriched.get("version")
            return result

        # Step 1: Apply feature name aliases
        mapped_features = self._apply_aliases(model_id, features)

        # Step 2: Check what's missing
        missing_required = []
        for feat in schema.required_features:
            if feat not in mapped_features:
                missing_required.append(feat)

        # Step 3: Fetch missing features from online store
        if missing_required:
            online_result = await self.provider.get_features(
                model_id=model_id,
                feature_names=missing_required,
                symbols=symbols,
                timestamp=timestamp,
            )
            if online_result:
                online_features = online_result.get("features", {})
                mapped_features.update(online_features)
                result["feature_version"] = online_result.get("version")
                result["enriched_from_store"] = list(online_features.keys())

        # Step 4: Apply defaults for still-missing features
        for feat in schema.required_features:
            if feat not in mapped_features:
                default = schema.default_values.get(feat)
                if default is not None:
                    mapped_features[feat] = default
                    result["defaulted"].append(feat)
                    result["status"][feat] = FeatureStatus.DEFAULTED.value
                else:
                    result["missing"].append(feat)
                    result["status"][feat] = FeatureStatus.MISSING.value
            else:
                result["status"][feat] = FeatureStatus.PRESENT.value

        # Also handle optional features
        for feat in schema.optional_features:
            if feat not in mapped_features:
                default = schema.default_values.get(feat)
                if default is not None:
                    mapped_features[feat] = default
                    result["status"][feat] = FeatureStatus.DEFAULTED.value

        # Sort features to match training order
        ordered = {}
        for feat in schema.required_features + schema.optional_features:
            if feat in mapped_features:
                ordered[feat] = mapped_features[feat]
        # Also include any extra features not in schema
        for k, v in mapped_features.items():
            if k not in ordered:
                ordered[k] = v

        result["features"] = ordered
        return result

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(
        self,
        model_id: str,
        features: Dict[str, Any],
        strict: bool = True,
    ) -> Dict[str, Any]:
        """Validate features against model schema.

        Args:
            model_id: Model identifier.
            features: Feature dictionary to validate.
            strict: If True, raise on missing required features.

        Returns:
            Validation result dict.

        Raises:
            ValueError: If strict=True and required features are missing.
        """
        schema = self._schemas.get(model_id)
        if schema is None:
            return {"valid": True, "reason": "no_schema"}

        result = {
            "valid": True,
            "model_id": model_id,
            "missing_required": [],
            "missing_optional": [],
            "extra_features": [],
            "type_mismatches": [],
        }

        # Check required features
        for feat in schema.required_features:
            if feat not in features:
                result["missing_required"].append(feat)
                result["valid"] = False

        # Check optional features
        for feat in schema.optional_features:
            if feat not in features:
                result["missing_optional"].append(feat)

        # Check extra features
        if not schema.allow_extra_features:
            expected = schema.get_expected_features()
            for feat in features:
                if feat not in expected:
                    result["extra_features"].append(feat)

        if strict and result["missing_required"]:
            raise ValueError(
                f"Missing required features for {model_id}: "
                f"{result['missing_required']}"
            )

        return result

    # ------------------------------------------------------------------
    # Feature name mapping
    # ------------------------------------------------------------------

    def _apply_aliases(
        self,
        model_id: str,
        features: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Apply feature name aliases from training names to online names."""
        schema = self._schemas.get(model_id)
        if schema is None or not schema.feature_aliases:
            return dict(features)

        mapped = {}
        for feat_name, feat_value in features.items():
            online_name = schema.feature_aliases.get(feat_name, feat_name)
            mapped[online_name] = feat_value

        return mapped

    def register_alias(
        self,
        model_id: str,
        training_name: str,
        online_name: str,
    ) -> None:
        """Register a feature name alias for a model."""
        schema = self._schemas.get(model_id)
        if schema is None:
            schema = FeatureSchema(
                model_id=model_id,
                required_features=[],
                feature_aliases={training_name: online_name},
            )
            self._schemas[model_id] = schema
        else:
            schema.feature_aliases[training_name] = online_name

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "schemas_registered": len(self._schemas),
            "models": list(self._schemas.keys()),
        }

    def __repr__(self) -> str:
        return f"FeatureAdapter(schemas={len(self._schemas)})"
