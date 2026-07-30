"""ML Platform configuration.

Provides centralized configuration for the ML platform,
including storage paths, scheduler settings, and runtime parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


class StorageBackend(str, Enum):
    """Supported storage backends for artifacts and metadata."""

    LOCAL = "local"
    S3 = "s3"
    MINIO = "minio"
    GCS = "gcs"
    AZURE = "azure"


class RuntimeMode(str, Enum):
    """ML runtime execution modes."""

    TRAINING = "training"
    INFERENCE = "inference"
    BATCH = "batch"
    ONLINE = "online"


class SchedulerPolicy(str, Enum):
    """Training scheduler policies."""

    FIXED_INTERVAL = "fixed_interval"  # Every N hours
    CRON = "cron"  # Cron expression
    EVENT_DRIVEN = "event_driven"  # Triggered by data events
    ADAPTIVE = "adaptive"  # ML-driven scheduling


@dataclass
class MLConfig:
    """Central configuration for the ML Platform.

    Attributes:
        storage_backend: Backend storage type for artifacts and models.
        storage_root: Root path for local storage or bucket prefix for cloud.
        artifact_ttl_days: Days before artifacts are eligible for cleanup.
        experiment_retention_days: Days before experiment records are archived.
        max_versions_per_model: Maximum tracked versions per model.
        default_framework: Default ML framework for experiments.
        scheduler_policy: Training scheduler scheduling policy.
        scheduler_cron: Cron expression when policy is CRON.
        scheduler_timezone: Timezone for cron scheduling.
        runtime_timeout_seconds: Maximum seconds for a runtime job.
        runtime_max_retries: Maximum retries for failed jobs.
        metadata_backend: Backend for metadata storage.
        registry_backend: Backend for registry storage.
        enable_lineage: Enable feature/model lineage tracking.
        enable_quality_monitoring: Enable model quality monitoring.
        tags: Global tags applied to all runs.
    """

    storage_backend: StorageBackend = StorageBackend.LOCAL
    storage_root: str = "ml_store"
    artifact_ttl_days: int = 365
    experiment_retention_days: int = 730
    max_versions_per_model: int = 50
    default_framework: str = "LightGBM"
    scheduler_policy: SchedulerPolicy = SchedulerPolicy.FIXED_INTERVAL
    scheduler_cron: str = "0 2 * * *"  # Default: 2 AM daily
    scheduler_timezone: str = "Asia/Shanghai"
    runtime_timeout_seconds: int = 3600
    runtime_max_retries: int = 3
    metadata_backend: StorageBackend = StorageBackend.LOCAL
    registry_backend: StorageBackend = StorageBackend.LOCAL
    enable_lineage: bool = True
    enable_quality_monitoring: bool = True
    tags: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        """Serialize config to a dictionary."""
        return {
            "storage_backend": self.storage_backend.value,
            "storage_root": self.storage_root,
            "artifact_ttl_days": self.artifact_ttl_days,
            "experiment_retention_days": self.experiment_retention_days,
            "max_versions_per_model": self.max_versions_per_model,
            "default_framework": self.default_framework,
            "scheduler_policy": self.scheduler_policy.value,
            "scheduler_cron": self.scheduler_cron,
            "scheduler_timezone": self.scheduler_timezone,
            "runtime_timeout_seconds": self.runtime_timeout_seconds,
            "runtime_max_retries": self.runtime_max_retries,
            "metadata_backend": self.metadata_backend.value,
            "registry_backend": self.registry_backend.value,
            "enable_lineage": self.enable_lineage,
            "enable_quality_monitoring": self.enable_quality_monitoring,
            "tags": dict(self.tags),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> MLConfig:
        """Deserialize config from a dictionary."""
        config = cls()
        if "storage_backend" in data:
            config.storage_backend = StorageBackend(str(data["storage_backend"]))
        if "storage_root" in data:
            config.storage_root = str(data["storage_root"])
        if "artifact_ttl_days" in data:
            config.artifact_ttl_days = int(data["artifact_ttl_days"])  # type: ignore[arg-type]
        if "experiment_retention_days" in data:
            config.experiment_retention_days = int(data["experiment_retention_days"])  # type: ignore[arg-type]
        if "max_versions_per_model" in data:
            config.max_versions_per_model = int(data["max_versions_per_model"])  # type: ignore[arg-type]
        if "default_framework" in data:
            config.default_framework = str(data["default_framework"])
        if "scheduler_policy" in data:
            config.scheduler_policy = SchedulerPolicy(str(data["scheduler_policy"]))
        if "scheduler_cron" in data:
            config.scheduler_cron = str(data["scheduler_cron"])
        if "scheduler_timezone" in data:
            config.scheduler_timezone = str(data["scheduler_timezone"])
        if "runtime_timeout_seconds" in data:
            config.runtime_timeout_seconds = int(data["runtime_timeout_seconds"])  # type: ignore[arg-type]
        if "runtime_max_retries" in data:
            config.runtime_max_retries = int(data["runtime_max_retries"])  # type: ignore[arg-type]
        if "metadata_backend" in data:
            config.metadata_backend = StorageBackend(str(data["metadata_backend"]))
        if "registry_backend" in data:
            config.registry_backend = StorageBackend(str(data["registry_backend"]))
        if "enable_lineage" in data:
            config.enable_lineage = bool(data["enable_lineage"])
        if "enable_quality_monitoring" in data:
            config.enable_quality_monitoring = bool(data["enable_quality_monitoring"])
        if "tags" in data:
            config.tags = dict(data["tags"])  # type: ignore[arg-type]
        return config
