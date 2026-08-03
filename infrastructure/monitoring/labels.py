"""
Standard metric labels.

Defines the canonical label set for
all ICYQuant metrics, ensuring consistent
dimensioning across the platform for
Grafana aggregation and analysis.

Usage:
    from infrastructure.monitoring.labels import (
        STANDARD_LABELS,
        build_default_labels,
    )

    labels = build_default_labels(
        service="trading",
        module="orders",
    )
"""

from __future__ import annotations

import os
import socket
from typing import Dict, Optional, Tuple


# Canonical label keys for all metrics
STANDARD_LABELS: Tuple[str, ...] = (
    "service",
    "module",
    "instance",
    "environment",
    "host",
    "region",
)

# Label descriptions for documentation
LABEL_DESCRIPTIONS: Dict[str, str] = {
    "service": "Service name (e.g., trading, research, risk)",
    "module": "Module name (e.g., database, redis, kafka)",
    "instance": "Service instance ID",
    "environment": "Deployment environment (dev, staging, prod)",
    "host": "Hostname or instance identifier",
    "region": "Cloud region (e.g., us-east-1)",
}


def get_hostname(
) -> str:
    """
    Get current hostname.

    Returns:
        Hostname string.
    """

    try:
        return socket.gethostname()
    except Exception:
        return "unknown"


def get_pid(
) -> int:
    """
    Get current process ID.

    Returns:
        Process ID.
    """

    return os.getpid()


def build_default_labels(
    service: str = "icyquant",
    module: str = "",
    environment: str = "development",
    region: str = "us-east-1",
    extra: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Build default metric labels.

    Creates a standardized label dictionary
    that should be applied to all metrics
    produced by a component.

    Args:
        service: Service name.
        module: Module name (empty for platform-level).
        environment: Deployment environment.
        region: Cloud region.
        extra: Additional custom labels.

    Returns:
        Label dictionary ready for metric creation.
    """

    labels: Dict[str, str] = {
        "service": service,
        "module": module,
        "instance": f"{get_hostname()}-{get_pid()}",
        "environment": environment,
        "host": get_hostname(),
        "region": region,
    }

    if extra:
        for k, v in extra.items():
            if k in STANDARD_LABELS:
                labels[k] = v
            else:
                # Non-standard labels pass through
                labels[k] = v

    return labels


def validate_labels(
    labels: Dict[str, str],
    allow_extra: bool = True,
) -> Tuple[bool, list]:
    """
    Validate label keys against the standard set.

    Args:
        labels: Labels to validate.
        allow_extra: Allow non-standard label keys.

    Returns:
        Tuple of (valid, list of issues).
    """

    issues = []
    valid = True

    for key in labels:
        if key not in STANDARD_LABELS and not allow_extra:
            issues.append(
                f"Non-standard label key: {key}"
            )
            valid = False

    return valid, issues
