"""
Service health models.
"""

from __future__ import annotations

from dataclasses import dataclass

from enum import Enum


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


@dataclass(
    frozen=True,
)
class HealthCheck:
    __slots__ = (
        "service",
        "status",
        "message",
    )
    service: str
    status: HealthStatus
    message: str


def healthy(
    service: str,
    message: str = "ok",
):
    return HealthCheck(
        service=service,
        status=HealthStatus.HEALTHY,
        message=message,
    )


def unhealthy(
    service: str,
    message: str,
):
    return HealthCheck(
        service=service,
        status=HealthStatus.UNHEALTHY,
        message=message,
    )