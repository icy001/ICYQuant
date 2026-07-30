"""ICYQuant Enterprise Feature Store.

Enterprise-grade feature management platform providing:
    - Feature Registry & Catalog
    - Feature Versioning & Lineage
    - Feature Validation & Monitoring
    - Online / Offline dual-store architecture
    - Unified Feature Service

Usage::

    from services.feature_store import FeatureService

    svc = FeatureService()
    svc.register(feature_name="ema20", version="v1", owner="research")
    svc.publish("ema20", "v1")
"""

from services.feature_store.config import FeatureStoreConfig
from services.feature_store.registry import FeatureRegistry, FeatureDefinition
from services.feature_store.catalog import FeatureCatalog, FeatureCategory
from services.feature_store.lineage import FeatureLineage, LineageNode, LineageGraph
from services.feature_store.versioning import FeatureVersioning, FeatureVersion
from services.feature_store.validator import FeatureValidator, ValidationReport, ValidationRule
from services.feature_store.monitor import FeatureMonitor, DriftReport, DriftStatus
from services.feature_store.online_store import OnlineFeatureStore, OnlineFeatureRecord
from services.feature_store.offline_store import OfflineFeatureStore, OfflineQuery
from services.feature_store.feature_service import FeatureService

__all__ = [
    "FeatureStoreConfig",
    "FeatureRegistry",
    "FeatureDefinition",
    "FeatureCatalog",
    "FeatureCategory",
    "FeatureLineage",
    "LineageNode",
    "LineageGraph",
    "FeatureVersioning",
    "FeatureVersion",
    "FeatureValidator",
    "ValidationReport",
    "ValidationRule",
    "FeatureMonitor",
    "DriftReport",
    "DriftStatus",
    "OnlineFeatureStore",
    "OnlineFeatureRecord",
    "OfflineFeatureStore",
    "OfflineQuery",
    "FeatureService",
]
