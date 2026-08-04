"""
Environment diagnostics.

Provides diagnostic snapshots of the current
environment configuration for debugging and
monitoring purposes.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict, Optional

from .discovery import EnvironmentDiscovery
from .environment.manager import EnvironmentManager
from .metadata import EnvironmentMetadata


class EnvironmentDiagnostics:
    """
    Environment diagnostics.

    Collects diagnostic information about the
    current environment configuration, including
    detection results, active profile, and
    effective configuration.

    Usage:
        diagnostics = EnvironmentDiagnostics()
        snapshot = await diagnostics.snapshot()
    """

    def __init__(
        self,
        manager: Optional[EnvironmentManager] = None,
        discovery: Optional[EnvironmentDiscovery] = None,
        metadata: Optional[EnvironmentMetadata] = None,
    ) -> None:
        """
        Initialize diagnostics.

        Args:
            manager: EnvironmentManager instance.
            discovery: EnvironmentDiscovery instance.
            metadata: EnvironmentMetadata instance.
        """
        self._manager = manager or EnvironmentManager()
        self._discovery = discovery or EnvironmentDiscovery()
        self._metadata = metadata or EnvironmentMetadata()

    async def snapshot(
        self,
    ) -> Dict[str, Any]:
        """
        Capture a diagnostic snapshot.

        Returns:
            Dictionary with diagnostic information.
        """
        # Ensure profiles are initialized
        self._manager.init_standard_profiles()

        # Auto-detect
        env_name = self._manager.auto_detect()

        # Resolve effective configuration
        try:
            effective = self._manager.resolve()
            effective_vars = effective.effective
        except Exception:
            effective_vars = {}

        # Collect metadata
        metadata = self._metadata.collect(
            environment=env_name,
            profile=self._manager.active_profile_name,
        )

        # Discovery info
        discovery_info = self._discovery.detect_all()

        # Detection log
        detection_log = self._manager.detector.get_detection_log()

        return {
            "environment": env_name,
            "profile": self._manager.active_profile_name,
            "metadata": metadata,
            "discovery": discovery_info,
            "detection_log": detection_log,
            "effective_config": effective_vars,
            "profile_status": self._manager.get_status(),
            "validator_errors": self._manager.validate(),
        }

    def get_quick_status(
        self,
    ) -> Dict[str, Any]:
        """Get a quick status without full resolution."""
        discovery_info = self._discovery.detect_all()
        metadata = self._metadata.collect()

        return {
            "environment": metadata.get("environment"),
            "profile": metadata.get("profile"),
            "is_docker": discovery_info.get("is_docker", False),
            "is_kubernetes": discovery_info.get("is_kubernetes", False),
            "ci_provider": discovery_info.get("ci_provider"),
            "hostname": discovery_info.get("hostname", ""),
            "container_id": discovery_info.get("container_id"),
        }

    def validate_profiles(
        self,
    ) -> Dict[str, list]:
        """Validate all registered profiles."""
        self._manager.init_standard_profiles()
        return self._manager.validate()


class ConfigurationDiagnostics:
    """
    Platform-level configuration diagnostics.

    Collects comprehensive diagnostic information
    from all configuration platform components.

    Usage:
        diag = ConfigurationDiagnostics()
        snapshot = await diag.snapshot()
    """

    def __init__(
        self,
        config_manager: Optional[Any] = None,
        env_manager: Optional[Any] = None,
        dynamic_manager: Optional[Any] = None,
    ) -> None:
        self._config_manager = config_manager
        self._env_manager = env_manager
        self._dynamic_manager = dynamic_manager

    async def snapshot(
        self,
    ) -> Dict[str, Any]:
        """
        Capture a platform-wide diagnostic snapshot.

        Returns:
            Diagnostic snapshot dictionary.
        """
        result: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Static config status
        if self._config_manager:
            try:
                result["config_manager"] = self._config_manager.get_stats()
            except Exception:
                result["config_manager"] = {"error": "unavailable"}

        # Environment status
        if self._env_manager:
            try:
                result["environment"] = self._env_manager.get_status()
            except Exception:
                result["environment"] = {"error": "unavailable"}

        # Dynamic config status
        if self._dynamic_manager:
            try:
                result["dynamic"] = self._dynamic_manager.get_status()
            except Exception:
                result["dynamic"] = {"error": "unavailable"}

        # Overall health
        result["healthy"] = all(
            "error" not in v for v in result.values() if isinstance(v, dict)
        )

        return result

    def get_quick_status(
        self,
    ) -> Dict[str, Any]:
        """Get a quick status without full resolution."""
        status: Dict[str, Any] = {}

        if self._config_manager:
            try:
                status["items"] = self._config_manager.item_count
                status["version"] = self._config_manager.snapshot_version
            except Exception:
                pass

        if self._env_manager:
            try:
                status["environment"] = self._env_manager.active_profile_name
            except Exception:
                pass

        if self._dynamic_manager:
            try:
                snap = self._dynamic_manager.current_snapshot
                status["snapshot_version"] = snap.version if snap else 0
            except Exception:
                pass

        return status
