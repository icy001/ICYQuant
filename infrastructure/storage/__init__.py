"""
Object storage infrastructure.

Provides production-grade object storage
infrastructure for the ICYQuant platform,
supporting multiple cloud providers with
a unified interface for market data,
strategy artifacts, and research outputs.

v0.4.0-alpha2 Part 4.5:
- StorageBootstrap for DI integration
- StorageTracing for OpenTelemetry hooks
- Pipeline component health reporting
- Production infrastructure V1 completion
"""

from .batch import BatchTransfer
from .bootstrap import StorageBootstrap
from .cache import StorageCache
from .client import StorageClient
from .compression import ZstdCompression
from .config import StorageConfig
from .encryption import StorageEncryption
from .exceptions import (
    BucketError,
    BucketNotFoundError,
    DeleteError,
    DownloadError,
    ObjectNotFoundError,
    StorageConnectionError,
    StorageError,
    StorageTimeoutError,
    UploadError,
)
from .health import StorageHealth
from .lifecycle import LifecyclePolicy, LifecycleRule
from .local import LocalStorageProvider
from .metadata import ExtendedMetadata
from .metrics import StorageMetrics, StorageMetricsExporter
from .middleware import (
    MiddlewareContext,
    StorageMiddleware,
    cache_post_hook,
    cache_pre_hook,
    compression_pre_hook,
    encryption_pre_hook,
    metrics_post_hook,
)
from .minio import MinIOProvider
from .models import (
    BucketInfo,
    ListResult,
    ObjectMetadata,
    StorageObject,
)
from .multipart import MultipartUpload, PartInfo
from .presign import PresignedUrl
from .provider import StorageProvider
from .retry import (
    StorageRetryConfig,
    critical_retry,
    default_retry,
    lenient_retry,
    storage_retry,
)
from .s3 import S3Provider
from .serializer import (
    ObjectSerializer,
    PathSerializer,
)
from .service import StorageService
from .streaming import StorageStream
from .tracing import StorageTracing

__all__ = [
    # Bootstrap & DI
    "StorageBootstrap",
    # Client & Config
    "StorageClient",
    "StorageConfig",
    # Service
    "StorageService",
    "StorageStream",
    # Providers
    "StorageProvider",
    "MinIOProvider",
    "S3Provider",
    "LocalStorageProvider",
    # Pipeline Components
    "StorageCache",
    "ZstdCompression",
    "StorageEncryption",
    "StorageMetrics",
    "StorageMetricsExporter",
    "StorageMiddleware",
    "MiddlewareContext",
    "BatchTransfer",
    "StorageRetryConfig",
    "StorageTracing",
    # Middleware Hooks
    "compression_pre_hook",
    "encryption_pre_hook",
    "cache_pre_hook",
    "cache_post_hook",
    "metrics_post_hook",
    # Retry Presets
    "storage_retry",
    "default_retry",
    "critical_retry",
    "lenient_retry",
    # Health
    "StorageHealth",
    # Models
    "BucketInfo",
    "ListResult",
    "ObjectMetadata",
    "StorageObject",
    "ExtendedMetadata",
    # Multipart
    "MultipartUpload",
    "PartInfo",
    # Presigned
    "PresignedUrl",
    # Lifecycle
    "LifecycleRule",
    "LifecyclePolicy",
    # Serializer
    "ObjectSerializer",
    "PathSerializer",
    # Exceptions
    "StorageError",
    "StorageConnectionError",
    "StorageTimeoutError",
    "UploadError",
    "DownloadError",
    "DeleteError",
    "BucketError",
    "ObjectNotFoundError",
    "BucketNotFoundError",
]