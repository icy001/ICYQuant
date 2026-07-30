"""Feature Store configuration module.

Provides centralized configuration for the Enterprise Feature Store,
covering storage backends, validation rules, monitoring thresholds,
and online/offline store settings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class StorageBackend(str, Enum):
    """Supported storage backends for feature data."""

    LOCAL = "local"
    S3 = "s3"
    MINIO = "minio"
    REDIS = "redis"
    MEMORY = "memory"


class ValidationMode(str, Enum):
    """Validation strictness levels."""

    STRICT = "strict"   # fail on any violation
    WARN = "warn"       # log warnings, continue
    RELAXED = "relaxed"  # skip non-critical checks


class DriftMethod(str, Enum):
    """Supported drift detection methods."""

    KS_TEST = "ks_test"
    PSI = "psi"
    WASSERSTEIN = "wasserstein"
    JS_DIVERGENCE = "js_divergence"


@dataclass
class FeatureStoreConfig:
    """Enterprise Feature Store configuration.

    Attributes:
        offline_backend: Storage backend for offline (historical) features.
        online_backend: Storage backend for online (real-time) features.
        metadata_backend: Storage backend for metadata and registry.
        redis_host: Redis host for online store.
        redis_port: Redis port for online store.
        redis_db: Redis database index.
        object_storage_endpoint: S3/MinIO endpoint URL.
        object_storage_bucket: Object storage bucket name.
        object_storage_prefix: Object storage key prefix.
        local_offline_path: Local filesystem path for offline store.
        validation_mode: Default validation strictness.
        max_versions_per_feature: Maximum retained versions per feature.
        drift_check_interval_hours: How often to run drift checks.
        drift_threshold_psi: PSI threshold for drift alert.
        drift_threshold_ks: KS test p-value threshold.
        enable_auto_validation: Auto-validate features on register.
        enable_lineage_tracking: Track feature lineage graph.
        enable_monitoring: Enable drift/data quality monitoring.
        alert_webhook_url: Webhook URL for drift alerts.
        alert_email: Email for drift alert notifications.
    """

    # ---- Storage ----
    offline_backend: StorageBackend = StorageBackend.LOCAL
    online_backend: StorageBackend = StorageBackend.MEMORY
    metadata_backend: StorageBackend = StorageBackend.MEMORY

    # Redis (online store)
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # Object storage (offline store)
    object_storage_endpoint: str = ""
    object_storage_bucket: str = "icyquant-features"
    object_storage_prefix: str = "features/"

    # Local
    local_offline_path: str = "data/features/offline"

    # ---- Validation ----
    validation_mode: ValidationMode = ValidationMode.STRICT
    max_versions_per_feature: int = 50

    # ---- Monitoring ----
    drift_check_interval_hours: int = 24
    drift_threshold_psi: float = 0.25
    drift_threshold_ks: float = 0.05
    enable_auto_validation: bool = True
    enable_lineage_tracking: bool = True
    enable_monitoring: bool = True

    # ---- Alerting ----
    alert_webhook_url: str = ""
    alert_email: str = ""

    # ---- Defaults ----
    default_owner: str = "research"
    default_frequency: str = "1d"

    # ---- Feature Store metadata ----
    metadata: Dict[str, str] = field(default_factory=dict)

    # ---- Extension config ----
    extra: Dict[str, object] = field(default_factory=dict)  # type: ignore[arg-type]
