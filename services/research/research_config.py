"""Research Configuration — centralized config for the research platform.

Supports:
* Experiment defaults
* Dataset storage backends
* Runtime execution policies
* Resource limits and quotas
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DatasetConfig:
    """Dataset subsystem configuration."""

    storage_backend: str = "local"  # local, s3, gcs, azure
    storage_path: str = "./data/datasets"
    cache_backend: str = "memory"  # memory, redis, disk
    cache_ttl_seconds: int = 3600
    max_cache_size_mb: int = 1024
    quality_checks_enabled: bool = True
    auto_snapshot_enabled: bool = True
    snapshot_retention_days: int = 90


@dataclass
class ExperimentConfig:
    """Experiment subsystem configuration."""

    max_concurrent_runs: int = 10
    default_timeout_seconds: int = 3600
    artifact_storage_path: str = "./data/artifacts"
    versioning_enabled: bool = True
    lineage_tracking_enabled: bool = True
    auto_tag_enabled: bool = True


@dataclass
class RuntimeConfig:
    """Runtime execution configuration."""

    max_workers: int = 4
    execution_timeout_seconds: int = 7200
    scheduler_integration_enabled: bool = True
    workflow_integration_enabled: bool = True
    retry_max_attempts: int = 3
    retry_backoff_seconds: int = 5
    resource_limits: Dict[str, Any] = field(default_factory=lambda: {
        "cpu_cores": 2,
        "memory_mb": 4096,
        "disk_mb": 10240,
    })


@dataclass
class ResearchConfig:
    """Top-level research platform configuration."""

    dataset: DatasetConfig = field(default_factory=DatasetConfig)
    experiment: ExperimentConfig = field(default_factory=ExperimentConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    environment: str = "development"  # development, staging, production
    log_level: str = "INFO"
    metrics_enabled: bool = True
    telemetry_enabled: bool = True
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResearchConfig":
        """Build config from a dictionary."""
        dataset_data = data.get("dataset", {})
        experiment_data = data.get("experiment", {})
        runtime_data = data.get("runtime", {})

        return cls(
            dataset=DatasetConfig(**dataset_data) if dataset_data else DatasetConfig(),
            experiment=ExperimentConfig(**experiment_data) if experiment_data else ExperimentConfig(),
            runtime=RuntimeConfig(**runtime_data) if runtime_data else RuntimeConfig(),
            environment=data.get("environment", "development"),
            log_level=data.get("log_level", "INFO"),
            metrics_enabled=data.get("metrics_enabled", True),
            telemetry_enabled=data.get("telemetry_enabled", True),
            extra=data.get("extra", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset": {
                "storage_backend": self.dataset.storage_backend,
                "storage_path": self.dataset.storage_path,
                "cache_backend": self.dataset.cache_backend,
                "cache_ttl_seconds": self.dataset.cache_ttl_seconds,
                "max_cache_size_mb": self.dataset.max_cache_size_mb,
                "quality_checks_enabled": self.dataset.quality_checks_enabled,
                "auto_snapshot_enabled": self.dataset.auto_snapshot_enabled,
                "snapshot_retention_days": self.dataset.snapshot_retention_days,
            },
            "experiment": {
                "max_concurrent_runs": self.experiment.max_concurrent_runs,
                "default_timeout_seconds": self.experiment.default_timeout_seconds,
                "artifact_storage_path": self.experiment.artifact_storage_path,
                "versioning_enabled": self.experiment.versioning_enabled,
                "lineage_tracking_enabled": self.experiment.lineage_tracking_enabled,
                "auto_tag_enabled": self.experiment.auto_tag_enabled,
            },
            "runtime": {
                "max_workers": self.runtime.max_workers,
                "execution_timeout_seconds": self.runtime.execution_timeout_seconds,
                "scheduler_integration_enabled": self.runtime.scheduler_integration_enabled,
                "workflow_integration_enabled": self.runtime.workflow_integration_enabled,
                "retry_max_attempts": self.runtime.retry_max_attempts,
                "retry_backoff_seconds": self.runtime.retry_backoff_seconds,
                "resource_limits": self.runtime.resource_limits,
            },
            "environment": self.environment,
            "log_level": self.log_level,
            "metrics_enabled": self.metrics_enabled,
            "telemetry_enabled": self.telemetry_enabled,
            "extra": self.extra,
        }
