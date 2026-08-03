"""
OpenTelemetry resource management.

Defines the resource attributes for
the ICYQuant service, following OpenTelemetry
semantic conventions for standard attribute
naming.

Resource attributes:
- service.name: Service name
- service.version: Service version
- service.instance.id: Instance ID
- service.namespace: Service namespace
- deployment.environment: Deployment environment
- host.name: Hostname
- host.arch: CPU architecture
- process.pid: Process ID
"""

from __future__ import annotations

import os
import platform
import socket
from typing import Any, Dict, Optional

try:
    from opentelemetry.sdk.resources import Resource
except ImportError:
    Resource = None


# Default resource attributes
DEFAULT_ATTRIBUTES = {
    "service.name": "icyquant",
    "service.version": "0.4.0-alpha2",
    "service.namespace": "trading",
    "deployment.environment": "development",
}


def build_resource(
    service_name: str = "icyquant",
    service_version: str = "0.4.0-alpha2",
    environment: str = "development",
    namespace: str = "trading",
    attributes: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Build an OpenTelemetry Resource with standard attributes.

    Args:
        service_name: Service name.
        service_version: Service version.
        environment: Deployment environment.
        namespace: Service namespace.
        attributes: Additional resource attributes.

    Returns:
        OpenTelemetry Resource instance or dict fallback.
    """

    attrs = {
        "service.name": service_name,
        "service.version": service_version,
        "service.namespace": namespace,
        "deployment.environment": environment,
        "host.name": socket.gethostname(),
        "host.arch": platform.machine(),
        "process.pid": os.getpid(),
    }

    # Add optional instance ID
    instance_id = os.environ.get("HOSTNAME") or socket.gethostname()
    attrs["service.instance.id"] = f"{instance_id}-{os.getpid()}"

    if attributes:
        attrs.update(attributes)

    if Resource is not None:
        return Resource.create(attrs)
    return attrs


def get_default_attributes(
    service_name: str = "icyquant",
    environment: str = "development",
) -> Dict[str, Any]:
    """
    Get default resource attributes without creating a Resource.

    Args:
        service_name: Service name.
        environment: Deployment environment.

    Returns:
        Dictionary of resource attributes.
    """

    return {
        "service.name": service_name,
        "service.version": "0.4.0-alpha2",
        "service.namespace": "trading",
        "deployment.environment": environment,
        "host.name": socket.gethostname(),
        "host.arch": platform.machine(),
        "process.pid": os.getpid(),
    }
