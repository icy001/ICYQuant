"""
Object storage configuration.

Defines the configuration model for object storage
providers (MinIO, S3, Azure Blob, GCS) with
multi-cloud support and performance tuning.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class StorageConfig(BaseModel):
    """
    Object storage configuration.

    Supports multiple cloud providers with
    provider-specific settings and shared
    connection/performance parameters.

    Attributes:
        provider: Cloud provider name (minio, aws, azure, gcs, local).
        endpoint: Service endpoint URL.
        access_key: Access key / client ID.
        secret_key: Secret key / client secret.
        bucket: Default bucket name.
        region: Cloud region (optional).
        secure: Use TLS/HTTPS connection.
        multipart_threshold: Size threshold for multipart uploads (bytes).
        multipart_chunk_size: Chunk size for multipart uploads (bytes).
        connect_timeout: Connection timeout in seconds.
        read_timeout: Read timeout in seconds.
    """

    provider: str = Field(
        default="minio",
        description=(
            "Cloud provider: minio, aws, azure, gcs, local"
        ),
    )

    endpoint: str = Field(
        default="localhost:9000",
        description="Service endpoint URL",
    )

    access_key: str = Field(
        default="",
        description="Access key / client ID",
    )

    secret_key: str = Field(
        default="",
        description="Secret key / client secret",
    )

    bucket: str = Field(
        default="icyquant",
        description="Default bucket name",
    )

    region: Optional[str] = Field(
        default=None,
        description="Cloud region",
    )

    secure: bool = Field(
        default=True,
        description="Use TLS/HTTPS connection",
    )

    multipart_threshold: int = Field(
        default=64 * 1024 * 1024,
        ge=1024 * 1024,
        description="Multipart upload threshold in bytes (64MB)",
    )

    multipart_chunk_size: int = Field(
        default=16 * 1024 * 1024,
        ge=1024 * 1024,
        description="Multipart chunk size in bytes (16MB)",
    )

    connect_timeout: int = Field(
        default=10,
        ge=1,
        description="Connection timeout in seconds",
    )

    read_timeout: int = Field(
        default=120,
        ge=10,
        description="Read timeout in seconds",
    )

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True

    def to_provider_dict(
        self,
    ) -> dict:
        """
        Convert to provider-specific dictionary.

        Returns:
            Configuration dictionary for provider SDK.
        """

        return {
            "endpoint": self.endpoint,
            "access_key": self.access_key,
            "secret_key": self.secret_key,
            "bucket": self.bucket,
            "region": self.region,
            "secure": self.secure,
            "connect_timeout": self.connect_timeout,
            "read_timeout": self.read_timeout,
        }
