"""
Environment metadata.

Provides unified metadata about the current
environment, including environment name,
profile, version, hostname, and container info.
"""

from __future__ import annotations

import platform
import socket
from datetime import datetime
from typing import Any, Dict, Optional

from .discovery import EnvironmentDiscovery


class EnvironmentMetadata:
    """
    Unified environment metadata.

    Collects and provides metadata about the
    current runtime environment, including:
    - Environment name and profile
    - Application version
    - Hostname and platform
    - Container ID (if in container)
    - Kubernetes namespace (if in K8s)
    - CI/CD provider (if in CI)

    Usage:
        metadata = EnvironmentMetadata()
        info = metadata.collect()
    """

    def __init__(
        self,
        discovery: Optional[EnvironmentDiscovery] = None,
    ) -> None:
        """
        Initialize metadata collector.

        Args:
            discovery: EnvironmentDiscovery instance.
        """
        self._discovery = discovery or EnvironmentDiscovery()
        self._collected: Optional[Dict[str, Any]] = None

    def collect(
        self,
        environment: Optional[str] = None,
        profile: Optional[str] = None,
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Collect environment metadata.

        Args:
            environment: Environment name (auto-detected if None).
            profile: Active profile name.
            version: Application version.

        Returns:
            Dictionary of metadata.
        """
        discovery_info = self._discovery.detect_all()

        self._collected = {
            "timestamp": datetime.utcnow().isoformat(),
            "environment": environment or self._detect_environment(),
            "profile": profile or "",
            "version": version or "",
            "hostname": discovery_info.get("hostname", ""),
            "platform": discovery_info.get("platform", ""),
            "container_id": discovery_info.get("container_id"),
            "is_docker": discovery_info.get("is_docker", False),
            "is_kubernetes": discovery_info.get("is_kubernetes", False),
            "ci_provider": discovery_info.get("ci_provider"),
            "kubernetes_namespace": self._get_kubernetes_namespace(),
            "python_version": platform.python_version(),
            "os": platform.system(),
            "machine": platform.machine(),
        }

        return self._collected

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Get a metadata value.

        Args:
            key: Metadata key.
            default: Default value if not found.

        Returns:
            Metadata value.
        """
        if self._collected is None:
            self.collect()
        return self._collected.get(key, default)

    def get_all(
        self,
    ) -> Dict[str, Any]:
        """Get all collected metadata."""
        if self._collected is None:
            self.collect()
        return dict(self._collected)

    def _detect_environment(
        self,
    ) -> str:
        """Auto-detect environment name."""
        env_vars = ["ICYQUANT_ENV", "APP_ENV", "ENVIRONMENT"]
        for var in env_vars:
            value = os.environ.get(var)
            if value:
                return value
        return "development"

    def _get_kubernetes_namespace(
        self,
    ) -> Optional[str]:
        """Get Kubernetes namespace if available."""
        # Try service account namespace
        sa_namespace = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
        try:
            with open(sa_namespace, "r") as f:
                return f.read().strip()
        except (FileNotFoundError, PermissionError):
            pass

        return None


# Need to import os here for _detect_environment
import os  # noqa: E402
