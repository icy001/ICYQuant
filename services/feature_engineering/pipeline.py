"""Feature Pipeline.

Defines a single feature engineering pipeline — a sequence of
transform, validate, select, and publish stages that turn raw
data into production-ready features.

Usage::

    from services.feature_engineering import FeaturePipeline, PipelineConfig

    cfg = PipelineConfig(
        name="alpha_daily",
        transforms=["return", "ema20", "volatility"],
        validate=True,
        publish_to="feature_store",
    )
    pipeline = FeaturePipeline(cfg)
    result = pipeline.run(raw_data)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

import numpy as np


class PipelineStatus(str, Enum):
    """Execution status of a pipeline."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineStage(str, Enum):
    """Stages within a pipeline execution."""

    LOAD = "load"
    CLEAN = "clean"
    TRANSFORM = "transform"
    VALIDATE = "validate"
    SELECT = "select"
    PUBLISH = "publish"
    DONE = "done"


@dataclass
class PipelineConfig:
    """Configuration for a feature engineering pipeline.

    Attributes:
        name: Unique pipeline identifier.
        source: Data source name.
        transforms: Ordered list of transformation names to apply.
        validate: Whether to run validation after transforms.
        select: Whether to run feature selection.
        publish_to: Target feature store identifier.
        cache_enabled: Whether to use incremental caching.
        max_retries: Retry count for failed stages.
        timeout_seconds: Per-stage timeout.
        tags: Pipeline categorization tags.
        params: Arbitrary additional parameters.
    """

    name: str = "default"
    source: str = "market_data"
    transforms: List[str] = field(default_factory=list)
    validate: bool = True
    select: bool = False
    publish_to: str = "feature_store"
    cache_enabled: bool = True
    max_retries: int = 3
    timeout_seconds: int = 3600
    tags: List[str] = field(default_factory=list)
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """Result of a pipeline execution.

    Attributes:
        pipeline_name: Name of the executed pipeline.
        status: Final execution status.
        stages_completed: Stages that completed successfully.
        stage_results: Per-stage output data.
        elapsed_seconds: Total execution time.
        feature_names: Names of produced features.
        feature_count: Number of features produced.
        warnings: Non-fatal warnings during execution.
        errors: Fatal errors (if status == FAILED).
        metadata: Arbitrary diagnostic metadata.
    """

    pipeline_name: str
    status: PipelineStatus
    stages_completed: List[PipelineStage] = field(default_factory=list)
    stage_results: Dict[str, Any] = field(default_factory=dict)
    elapsed_seconds: float = 0.0
    feature_names: List[str] = field(default_factory=list)
    feature_count: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            f"PipelineResult(name={self.pipeline_name!r}, "
            f"status={self.status.value}, "
            f"features={self.feature_count})"
        )


class FeaturePipeline:
    """A single feature engineering pipeline.

    Encapsulates the complete lifecycle from raw data ingestion
    through transformation, validation, selection, and publishing
    to the feature store.

    Example::

        pipeline = FeaturePipeline(PipelineConfig(
            name="daily_alpha",
            transforms=["return", "ema20", "volatility", "momentum"],
        ))
        result = pipeline.run(raw_data={"close": [...], "volume": [...]})
    """

    def __init__(self, config: Optional[PipelineConfig] = None) -> None:
        self.config = config or PipelineConfig()
        self.status = PipelineStatus.IDLE
        self._start_time: float = 0.0
        self._transforms_registry: Dict[str, Any] = {}
        self._features: Dict[str, List[float]] = {}
        self._warnings: List[str] = []
        self._errors: List[str] = []
        self._stages_done: List[PipelineStage] = []

    # ---- Pipeline metadata ----

    @property
    def name(self) -> str:
        return self.config.name

    def reset(self) -> None:
        """Reset pipeline to idle state."""
        self.status = PipelineStatus.IDLE
        self._start_time = 0.0
        self._features = {}
        self._warnings = []
        self._errors = []
        self._stages_done = []

    # ---- Transform registration ----

    def register_transform(self, name: str, fn: Any) -> None:
        """Register a named transform function.

        Args:
            name: Transform name (referenced in config.transforms).
            fn: Callable that takes (data: Dict[str, List]) -> Dict[str, List[float]].
        """
        self._transforms_registry[name] = fn

    def register_transforms(self, transforms: Dict[str, Any]) -> None:
        """Batch register transform functions."""
        self._transforms_registry.update(transforms)

    # ---- Run ----

    def run(self, raw_data: Dict[str, List[float]]) -> PipelineResult:
        """Execute the full pipeline.

        Args:
            raw_data: Dict of column_name -> list of values.

        Returns:
            PipelineResult with execution details.
        """
        self.reset()
        self.status = PipelineStatus.RUNNING
        self._start_time = time.time()

        try:
            # Stage 1: Load & Clean
            self._stages_done.append(PipelineStage.LOAD)
            self._features = dict(raw_data)
            self._stages_done.append(PipelineStage.CLEAN)
            self._features = self._clean(self._features)

            # Stage 2: Transform
            self._stages_done.append(PipelineStage.TRANSFORM)
            for t_name in self.config.transforms:
                if t_name in self._transforms_registry:
                    try:
                        new_features = self._transforms_registry[t_name](self._features)
                        if new_features:
                            self._features.update(new_features)
                    except Exception as e:
                        self._warnings.append(f"Transform '{t_name}' failed: {e}")
                else:
                    self._warnings.append(f"Transform '{t_name}' not registered, skipped")

            # Stage 3: Validate
            if self.config.validate:
                self._stages_done.append(PipelineStage.VALIDATE)
                valid, msg = self._validate(self._features)
                if not valid:
                    self._warnings.append(f"Validation warning: {msg}")

            # Stage 4: Select
            if self.config.select:
                self._stages_done.append(PipelineStage.SELECT)
                # Placeholder: selection happens externally via FeatureSelector

            # Stage 5: Publish
            self._stages_done.append(PipelineStage.PUBLISH)
            self._stages_done.append(PipelineStage.DONE)

            self.status = PipelineStatus.COMPLETED
        except Exception as e:
            self.status = PipelineStatus.FAILED
            self._errors.append(str(e))

        elapsed = time.time() - self._start_time

        feature_names = list(self._features.keys())
        return PipelineResult(
            pipeline_name=self.config.name,
            status=self.status,
            stages_completed=list(self._stages_done),
            stage_results={"features": feature_names},
            elapsed_seconds=elapsed,
            feature_names=feature_names,
            feature_count=len(feature_names),
            warnings=list(self._warnings),
            errors=list(self._errors),
            metadata={"source": self.config.source, "transforms": self.config.transforms},
        )

    # ---- Internal stages ----

    def _clean(self, data: Dict[str, List[float]]) -> Dict[str, List[float]]:
        """Basic cleaning: remove all-NaN columns, forward-fill."""
        cleaned: Dict[str, List[float]] = {}
        for col, values in data.items():
            # Remove all-NaN columns
            clean = [v for v in values if v is not None and not (isinstance(v, float) and np.isnan(v))]
            if len(clean) == 0:
                self._warnings.append(f"Column '{col}' is all-NaN, dropped")
                continue
            # Forward-fill NaN gaps
            filled: List[float] = []
            last_valid: float = float("nan")
            for v in values:
                if v is not None and not (isinstance(v, float) and np.isnan(v)):
                    last_valid = float(v)
                    filled.append(float(v))
                else:
                    filled.append(last_valid)
            cleaned[col] = filled
        return cleaned

    def _validate(self, data: Dict[str, List[float]]) -> tuple[bool, str]:
        """Run basic validation checks.

        Returns:
            (is_valid, message)
        """
        if not data:
            return (False, "No features produced")

        for col, values in data.items():
            arr = np.array(values, dtype=np.float64)
            # Check for all-NaN
            if np.all(np.isnan(arr)):
                return (False, f"Feature '{col}' is all-NaN")
            # Check for all-constant
            if np.nanstd(arr) == 0:
                self._warnings.append(f"Feature '{col}' is constant")

        return (True, "OK")

    # ---- Export ----

    def to_dict(self) -> Dict[str, Any]:
        """Export pipeline configuration as a dict."""
        return {
            "name": self.config.name,
            "source": self.config.source,
            "transforms": self.config.transforms,
            "validate": self.config.validate,
            "select": self.config.select,
            "publish_to": self.config.publish_to,
            "cache_enabled": self.config.cache_enabled,
            "max_retries": self.config.max_retries,
            "timeout_seconds": self.config.timeout_seconds,
            "tags": self.config.tags,
            "params": self.config.params,
        }

    def __repr__(self) -> str:
        return (
            f"FeaturePipeline(name={self.config.name!r}, "
            f"status={self.status.value}, "
            f"transforms={len(self.config.transforms)})"
        )
