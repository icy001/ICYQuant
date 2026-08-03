"""
Kafka configuration.

Production Kafka configuration with
security, timeouts, and performance tuning.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class KafkaConfig(BaseModel):
    """
    Kafka configuration.

    Encapsulates broker connection, security protocol,
    and producer/consumer performance parameters
    with sensible production defaults.
    """

    bootstrap_servers: List[str]

    client_id: str = "icyquant"

    security_protocol: str = "PLAINTEXT"

    sasl_mechanism: Optional[str] = None

    sasl_username: Optional[str] = None

    sasl_password: Optional[str] = None

    request_timeout_ms: int = Field(
        default=30000,
        ge=1000,
        description="Request timeout in milliseconds",
    )

    session_timeout_ms: int = Field(
        default=45000,
        ge=5000,
        description="Session timeout in milliseconds",
    )

    heartbeat_interval_ms: int = Field(
        default=3000,
        ge=500,
        description="Heartbeat interval in milliseconds",
    )

    max_batch_size: int = Field(
        default=16384,
        ge=1024,
        description="Maximum batch size in bytes",
    )

    # Producer settings
    linger_ms: int = Field(
        default=10,
        ge=0,
        description="Linger time in milliseconds",
    )

    acks: str = "all"

    retries: int = Field(
        default=5,
        ge=0,
        description="Number of retries",
    )

    retry_backoff_ms: int = Field(
        default=500,
        ge=100,
        description="Retry backoff in milliseconds",
    )

    max_request_size: int = Field(
        default=1048576,
        ge=1024,
        description="Maximum request size in bytes",
    )

    delivery_timeout_ms: int = Field(
        default=120000,
        ge=10000,
        description="Delivery timeout in milliseconds",
    )

    # Consumer settings
    group_id: str = "icyquant"

    auto_offset_reset: str = "earliest"

    enable_auto_commit: bool = False

    max_poll_records: int = Field(
        default=500,
        ge=1,
        description="Max records per poll",
    )

    fetch_max_bytes: int = Field(
        default=52428800,
        ge=1024,
        description="Max fetch bytes per request",
    )

    max_partition_fetch_bytes: int = Field(
        default=1048576,
        ge=1024,
        description="Max bytes per partition",
    )

    consumer_timeout_ms: int = Field(
        default=1000,
        ge=100,
        description="Consumer poll timeout in ms",
    )

    max_poll_interval_ms: int = Field(
        default=300000,
        ge=10000,
        description="Max poll interval in ms",
    )

    compression_type: str = "lz4"

    enable_idempotence: bool = True
