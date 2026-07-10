"""
Observability runtime settings.
"""

from __future__ import annotations

from dataclasses import dataclass

import os


@dataclass(
    frozen=True,
)
class ObservabilitySettings:
    __slots__ = (
        "service_name",
        "environment",
        "log_level",
        "tracing_enabled",
        "metrics_enabled",
    )
    service_name: str
    environment: str
    log_level: str
    tracing_enabled: bool
    metrics_enabled: bool


def load_settings() -> ObservabilitySettings:
    return ObservabilitySettings(
        service_name=os.getenv(
            "SERVICE_NAME",
            "icyquant",
        ),
        environment=os.getenv(
            "ENVIRONMENT",
            "development",
        ),
        log_level=os.getenv(
            "LOG_LEVEL",
            "INFO",
        ),
        tracing_enabled=(
            os.getenv(
                "TRACE_ENABLED",
                "true",
            )
            .lower()
            ==
            "true"
        ),
        metrics_enabled=(
            os.getenv(
                "METRICS_ENABLED",
                "true",
            )
            .lower()
            ==
            "true"
        ),
    )