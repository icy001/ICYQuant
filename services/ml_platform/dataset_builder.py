"""
ICYQuant Dataset Builder - Build point-in-time correct training datasets.

Combines features, labels, and metadata into reproducible training datasets.
Every dataset records exactly what features, labels, time range, universe,
filters, and code version were used.

    Features
       +
    Labels
       +
    Time
       +
    Universe
       +
    Filters
       ↓
    Training Dataset × Reproducibility Metadata
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .training_dataset import DatasetMetadata, TrainingDataset

logger = logging.getLogger(__name__)


@dataclass
class DatasetBuildConfig:
    """Configuration for building a training dataset."""

    # Features
    feature_ids: List[str] = field(default_factory=list)
    feature_view_id: Optional[str] = None

    # Labels
    label_type: str = "regression"
    label_horizon: str = "5d"
    label_config: Dict[str, Any] = field(default_factory=dict)

    # Data scope
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    universe: List[str] = field(default_factory=list)
    universe_filter: Optional[str] = None  # e.g. "market_cap > 1e9"

    # Splits (chronological)
    train_ratio: float = 0.6
    val_ratio: float = 0.2
    test_ratio: float = 0.2

    # Quality
    min_non_null_ratio: float = 0.8
    max_sample_weight: float = 10.0

    # Output
    output_format: str = "pandas"


@dataclass
class BuildReport:
    """Report for a dataset build operation."""

    dataset_id: str = ""
    success: bool = True

    # Build statistics
    feature_count: int = 0
    entity_count: int = 0
    total_rows: int = 0
    valid_rows: int = 0
    dropped_rows: int = 0
    null_dropped: int = 0
    filter_dropped: int = 0

    # Timing
    build_time_seconds: float = 0.0
    feature_retrieval_time: float = 0.0
    label_computation_time: float = 0.0

    # Quality
    final_null_ratio: float = 0.0
    label_distribution: Dict[str, Any] = field(default_factory=dict)

    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class DatasetBuilder:
    """Builds reproducible, point-in-time correct training datasets.

    Orchestrates:
    1. Feature retrieval from offline store (point-in-time)
    2. Label computation via label engine
    3. Entity universe filtering
    4. Time-based train/val/test splitting
    5. Null handling and quality checks
    6. Metadata recording for full reproducibility
    """

    def __init__(
        self,
        offline_store: Optional[Any] = None,
        label_engine: Optional[Any] = None,
        sample_generator: Optional[Any] = None,
    ) -> None:
        self._offline_store = offline_store
        self._label_engine = label_engine
        self._sample_generator = sample_generator

    async def build(self, config: DatasetBuildConfig) -> TrainingDataset:
        """Build a training dataset from configuration.

        This is the main entry point for creating ML-ready datasets.
        """
        import time
        t0 = time.time()

        report = BuildReport()

        try:
            # Step 1: Retrieve features (point-in-time)
            features = await self._retrieve_features(config, report)

            # Step 2: Compute labels
            labels = await self._compute_labels(config, features, report)

            # Step 3: Apply filters
            filtered = await self._apply_filters(config, features, labels, report)

            # Step 4: Create metadata
            metadata = self._build_metadata(config, report)

            # Step 5: Create dataset
            dataset = TrainingDataset(metadata=metadata, data=features, labels=labels)

            report.dataset_id = dataset.dataset_id
            report.build_time_seconds = time.time() - t0
            report.success = True

            logger.info("Dataset built: %s (%d features, %d rows, %.2fs)",
                         dataset.dataset_id, report.feature_count, report.total_rows, report.build_time_seconds)

            return dataset

        except Exception as exc:
            report.success = False
            report.errors.append(str(exc))
            logger.exception("Dataset build failed: %s", exc)
            raise

    # -- Build Steps --

    async def _retrieve_features(self, config: DatasetBuildConfig, report: BuildReport) -> Any:
        """Retrieve feature values from offline store with point-in-time correctness."""
        t0 = __import__('time').time()
        report.feature_retrieval_time = __import__('time').time() - t0
        return None  # placeholder

    async def _compute_labels(
        self, config: DatasetBuildConfig, features: Any, report: BuildReport,
    ) -> Any:
        """Compute training labels."""
        t0 = __import__('time').time()
        report.label_computation_time = __import__('time').time() - t0
        return None  # placeholder

    async def _apply_filters(
        self, config: DatasetBuildConfig, features: Any, labels: Any, report: BuildReport,
    ) -> Any:
        """Apply universe and quality filters."""
        return features

    def _build_metadata(self, config: DatasetBuildConfig, report: BuildReport) -> DatasetMetadata:
        """Build comprehensive dataset metadata."""
        total_days = 0
        if config.start_date and config.end_date:
            total_days = (config.end_date - config.start_date).days

        train_days = int(total_days * config.train_ratio)
        val_days = int(total_days * config.val_ratio)

        return DatasetMetadata(
            feature_ids=config.feature_ids,
            feature_count=len(config.feature_ids),
            label_type=config.label_type,
            label_horizon=config.label_horizon,
            start_date=config.start_date,
            end_date=config.end_date,
            entity_ids=config.universe,
            entity_count=len(config.universe),
            row_count=report.total_rows,
            feature_dim=len(config.feature_ids),
            null_ratio=report.final_null_ratio,
            train_start=config.start_date,
            train_end=config.start_date + __import__('datetime').timedelta(days=train_days) if config.start_date else None,
            val_start=config.start_date + __import__('datetime').timedelta(days=train_days) if config.start_date else None,
            val_end=config.start_date + __import__('datetime').timedelta(days=train_days + val_days) if config.start_date else None,
            test_start=config.start_date + __import__('datetime').timedelta(days=train_days + val_days) if config.start_date else None,
            test_end=config.end_date,
            filters=[],
            description=f"Training dataset with {len(config.feature_ids)} features, {config.label_type} labels ({config.label_horizon})",
        )
