"""
Monitoring configuration.

Defines the configuration model for the
monitoring infrastructure, controlling
metrics collection, export, and retention
behavior across the ICYQuant platform.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class MonitoringConfig(BaseModel):
    """
    Monitoring infrastructure configuration.

    Controls the behavior of the monitoring
    layer, including collection intervals,
    export intervals, and feature flags.

    Attributes:
        enabled: Master switch for monitoring.
        namespace: Metric namespace prefix.
        collect_interval: Collection interval in seconds.
        export_interval: Export interval in seconds.
        retention_days: Metrics retention in days.
        enable_health: Enable health aggregation.
        enable_metrics: Enable metrics collection.
        labels: Default labels for all metrics.
    """

    enabled: bool = Field(
        default=True,
        description="Master switch for monitoring",
    )

    namespace: str = Field(
        default="icyquant",
        description="Metric namespace prefix",
    )

    collect_interval: int = Field(
        default=15,
        ge=1,
        description="Collection interval in seconds",
    )

    export_interval: int = Field(
        default=15,
        ge=1,
        description="Export interval in seconds",
    )

    retention_days: int = Field(
        default=30,
        ge=1,
        description="Metrics retention in days",
    )

    enable_health: bool = Field(
        default=True,
        description="Enable health aggregation",
    )

    enable_metrics: bool = Field(
        default=True,
        description="Enable metrics collection",
    )

    default_labels: dict = Field(
        default={
            "service": "icyquant",
            "environment": "development",
            "module": "monitoring",
        },
        description="Default labels for all metrics",
    )

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True
