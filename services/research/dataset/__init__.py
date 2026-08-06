"""Dataset Management — unified data registration, versioning, and quality."""

from .dataset_manager import DatasetManager, DatasetManagerState
from .dataset_registry import DatasetRegistry
from .dataset_catalog import DatasetCatalog, CatalogEntry
from .dataset_loader import DatasetLoader, LoadStrategy
from .dataset_schema import DatasetSchema, ColumnSchema
from .dataset_validator import DatasetValidator, ValidationRule, ValidationReport
from .dataset_version import DatasetVersion
from .dataset_snapshot import DatasetSnapshot, SnapshotType
from .dataset_partition import DatasetPartition, PartitionStrategy
from .dataset_cache import DatasetCache, CacheBackend, CacheEntry
from .dataset_profile import DatasetProfile
from .dataset_statistics import DatasetStatistics, ColumnStatistics
from .dataset_quality import DatasetQuality, QualityCheck, QualityReport

__all__ = [
    "DatasetManager",
    "DatasetManagerState",
    "DatasetRegistry",
    "DatasetCatalog",
    "CatalogEntry",
    "DatasetLoader",
    "LoadStrategy",
    "DatasetSchema",
    "ColumnSchema",
    "DatasetValidator",
    "ValidationRule",
    "ValidationReport",
    "DatasetVersion",
    "DatasetSnapshot",
    "SnapshotType",
    "DatasetPartition",
    "PartitionStrategy",
    "DatasetCache",
    "CacheBackend",
    "CacheEntry",
    "DatasetProfile",
    "DatasetStatistics",
    "ColumnStatistics",
    "DatasetQuality",
    "QualityCheck",
    "QualityReport",
]
