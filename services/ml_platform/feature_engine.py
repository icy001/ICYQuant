"""
ICYQuant Feature Engine - Core feature computation engine.

Executes feature definitions against raw data sources to produce
computed features. Supports multiple computation modes:
- Rolling window transformations
- Cross-sectional computations
- Time-series features
- Custom formula evaluation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from .feature_definition import FeatureDefinition
from .feature_registry import FeatureFrequency, NullPolicy, OutlierPolicy

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Computation Modes
# ---------------------------------------------------------------------------


@dataclass
class ComputeRequest:
    """A request to compute a set of features."""

    request_id: str = field(default_factory=lambda: uuid4().hex[:12])
    feature_definitions: List[FeatureDefinition] = field(default_factory=list)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    entity_ids: List[str] = field(default_factory=list)  # symbols, instruments
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComputeResult:
    """Result of a feature computation."""

    request_id: str = ""
    feature_id: str = ""
    success: bool = True
    values: Optional[Any] = None     # computed feature values
    error: Optional[str] = None
    computation_time_seconds: float = 0.0
    rows_computed: int = 0
    null_count: int = 0
    null_ratio: float = 0.0


# ---------------------------------------------------------------------------
# Feature Engine
# ---------------------------------------------------------------------------


class FeatureEngine:
    """Core feature computation engine.

    Takes feature definitions and raw data, applies transformations,
    handles null/outlier policies, and produces validated feature values.
    """

    def __init__(self) -> None:
        self._transform_registry: Dict[str, Callable] = {}
        self._register_builtin_transforms()

    def _register_builtin_transforms(self) -> None:
        """Register built-in transformation functions."""
        self._transform_registry["rolling"] = self._transform_rolling
        self._transform_registry["cross_sectional"] = self._transform_cross_sectional
        self._transform_registry["time_series"] = self._transform_time_series
        self._transform_registry["element_wise"] = self._transform_element_wise

    # -- Computation --

    async def compute(self, request: ComputeRequest) -> List[ComputeResult]:
        """Compute all features in a request."""
        results: List[ComputeResult] = []
        for feature_def in request.feature_definitions:
            result = await self._compute_feature(feature_def, request)
            results.append(result)
        return results

    async def compute_single(self, feature_def: FeatureDefinition, request: ComputeRequest) -> ComputeResult:
        """Compute a single feature."""
        return await self._compute_feature(feature_def, request)

    async def _compute_feature(self, feature_def: FeatureDefinition, request: ComputeRequest) -> ComputeResult:
        """Compute a single feature from its definition."""
        import time
        t0 = time.time()

        result = ComputeResult(
            request_id=request.request_id,
            feature_id=feature_def.name,
        )

        try:
            # Select transformation function
            transform_fn = self._transform_registry.get(
                feature_def.transform_type,
                self._transform_element_wise,
            )

            # Apply transformation
            values = await transform_fn(feature_def, request)

            # Apply null policy
            values = self._apply_null_policy(values, feature_def.null_policy, feature_def.null_fill_value)

            # Apply outlier policy
            values = self._apply_outlier_policy(
                values,
                feature_def.outlier_policy,
                feature_def.outlier_lower_pct,
                feature_def.outlier_upper_pct,
            )

            # Validate constraints
            values = self._apply_constraints(
                values,
                feature_def.min_value,
                feature_def.max_value,
                feature_def.allow_nan,
                feature_def.allow_inf,
            )

            result.values = values
            result.success = True

        except Exception as exc:
            result.success = False
            result.error = str(exc)
            logger.exception("Feature computation failed for %s: %s", feature_def.name, exc)

        finally:
            result.computation_time_seconds = time.time() - t0

        return result

    # -- Transform Functions --

    async def _transform_rolling(self, feature_def: FeatureDefinition, request: ComputeRequest) -> Any:
        """Rolling window transformation (momentum, volatility, MA, etc.)."""
        window = feature_def.lookback_window
        logger.debug("Rolling transform: %s (window=%d)", feature_def.name, window)
        return None  # placeholder - actual data computation in production

    async def _transform_cross_sectional(self, feature_def: FeatureDefinition, request: ComputeRequest) -> Any:
        """Cross-sectional transformation (rank, z-score within groups)."""
        groups = feature_def.group_by_columns
        logger.debug("Cross-sectional transform: %s (groups=%s)", feature_def.name, groups)
        return None

    async def _transform_time_series(self, feature_def: FeatureDefinition, request: ComputeRequest) -> Any:
        """Time-series transformation (lag, diff, ewma, etc.)."""
        logger.debug("Time-series transform: %s", feature_def.name)
        return None

    async def _transform_element_wise(self, feature_def: FeatureDefinition, request: ComputeRequest) -> Any:
        """Element-wise transformation (ratio, log, binary ops)."""
        logger.debug("Element-wise transform: %s", feature_def.name)
        return None

    # -- Policy Application --

    def _apply_null_policy(self, values: Any, policy: NullPolicy, fill_value: Optional[float]) -> Any:
        """Apply null handling policy to computed values."""
        # Placeholder - actual null handling in production
        return values

    def _apply_outlier_policy(
        self, values: Any, policy: OutlierPolicy, lower_pct: float, upper_pct: float
    ) -> Any:
        """Apply outlier handling policy."""
        # Placeholder - actual outlier handling in production
        return values

    def _apply_constraints(
        self, values: Any, min_val: Optional[float], max_val: Optional[float],
        allow_nan: bool, allow_inf: bool,
    ) -> Any:
        """Apply value constraints."""
        # Placeholder - actual constraint enforcement in production
        return values

    # -- Bulk Operations --

    async def compute_feature_group(
        self, feature_definitions: List[FeatureDefinition], entity_ids: List[str],
    ) -> Dict[str, List[ComputeResult]]:
        """Compute a group of features for a set of entities."""
        results: Dict[str, List[ComputeResult]] = {}

        for entity_id in entity_ids:
            request = ComputeRequest(
                feature_definitions=feature_definitions,
                entity_ids=[entity_id],
            )
            results[entity_id] = await self.compute(request)

        return results
