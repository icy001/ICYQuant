"""Version Compatibility Manager for the Service Mesh Platform.

Provides ``VersionCompatibilityManager`` for managing mesh
version compatibility including mixed version support and
rolling migration.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from .telemetry import PlatformTelemetry
from .metrics import PlatformMetrics

logger = logging.getLogger(__name__)


class CompatibilityLevel(str, Enum):
    """Level of version compatibility."""

    FULL = "full"
    PARTIAL = "partial"
    NONE = "none"


class MeshVersion:
    """Represents a mesh version with capabilities."""

    def __init__(
        self,
        version: str,
        capabilities: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.version = version
        self.capabilities = capabilities or {}

    def supports(self, capability: str) -> bool:
        return self.capabilities.get(capability, False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "capabilities": self.capabilities,
        }


class CompatibilityMatrix:
    """Matrix defining compatibility between versions."""

    def __init__(self) -> None:
        self._matrix: Dict[str, Dict[str, CompatibilityLevel]] = {}

    def set_compatibility(
        self,
        version_a: str,
        version_b: str,
        level: CompatibilityLevel,
    ) -> None:
        if version_a not in self._matrix:
            self._matrix[version_a] = {}
        self._matrix[version_a][version_b] = level

    def get_compatibility(
        self, version_a: str, version_b: str
    ) -> CompatibilityLevel:
        direct = self._matrix.get(version_a, {}).get(version_b)
        if direct:
            return direct
        reverse = self._matrix.get(version_b, {}).get(version_a)
        if reverse:
            return reverse
        return CompatibilityLevel.NONE

    def to_dict(self) -> Dict[str, Any]:
        return {
            va: {
                vb: level.value
                for vb, level in vb_dict.items()
            }
            for va, vb_dict in self._matrix.items()
        }


class VersionCompatibilityManager:
    """Manages version compatibility for the service mesh."""

    def __init__(
        self,
        telemetry: Optional[PlatformTelemetry] = None,
        metrics: Optional[PlatformMetrics] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._telemetry = telemetry or PlatformTelemetry()
        self._metrics = metrics or PlatformMetrics()
        self._known_versions: Dict[str, MeshVersion] = {}
        self._matrix = CompatibilityMatrix()
        self._current_version = "0.4.0"
        self._mixed_mode = False
        self._migration_in_progress = False
        self._register_default_versions()

    def _register_default_versions(self) -> None:
        v030 = MeshVersion(
            "0.3.0",
            {
                "traffic_management": True,
                "security": True,
                "observability": True,
                "plugin_sdk": False,
                "control_api": False,
                "rolling_upgrade": False,
            },
        )
        v040 = MeshVersion(
            "0.4.0",
            {
                "traffic_management": True,
                "security": True,
                "observability": True,
                "plugin_sdk": True,
                "control_api": True,
                "rolling_upgrade": True,
                "cluster": True,
                "snapshot_restore": True,
            },
        )

        self._known_versions["0.3.0"] = v030
        self._known_versions["0.4.0"] = v040

        # Set compatibility
        self._matrix.set_compatibility(
            "0.3.0", "0.3.0", CompatibilityLevel.FULL
        )
        self._matrix.set_compatibility(
            "0.4.0", "0.4.0", CompatibilityLevel.FULL
        )
        self._matrix.set_compatibility(
            "0.3.0", "0.4.0", CompatibilityLevel.PARTIAL
        )

    def register_version(
        self,
        version: str,
        capabilities: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._known_versions[version] = MeshVersion(
            version, capabilities
        )

    def set_compatibility(
        self,
        version_a: str,
        version_b: str,
        level: CompatibilityLevel,
    ) -> None:
        self._matrix.set_compatibility(
            version_a, version_b, level
        )

    def get_version(
        self, version: str
    ) -> Optional[MeshVersion]:
        return self._known_versions.get(version)

    def get_current_version(self) -> str:
        return self._current_version

    def set_current_version(self, version: str) -> None:
        self._current_version = version

    def check_compatibility(
        self,
        version_a: str,
        version_b: str,
    ) -> Dict[str, Any]:
        """Check compatibility between two versions."""
        level = self._matrix.get_compatibility(
            version_a, version_b
        )
        va = self._known_versions.get(version_a)
        vb = self._known_versions.get(version_b)

        shared_capabilities = []
        if va and vb:
            for cap in va.capabilities:
                if vb.supports(cap):
                    shared_capabilities.append(cap)

        return {
            "version_a": version_a,
            "version_b": version_b,
            "compatibility_level": level.value,
            "shared_capabilities": shared_capabilities,
            "version_a_capabilities": (
                va.capabilities if va else {}
            ),
            "version_b_capabilities": (
                vb.capabilities if vb else {}
            ),
        }

    def enable_mixed_mode(self) -> Dict[str, Any]:
        """Enable mixed version mode."""
        self._mixed_mode = True
        self._telemetry.log_platform_event(
            "mixed_mode_enabled", "compatibility",
        )
        return {"success": True, "mixed_mode": True}

    def disable_mixed_mode(self) -> Dict[str, Any]:
        """Disable mixed version mode."""
        self._mixed_mode = False
        self._telemetry.log_platform_event(
            "mixed_mode_disabled", "compatibility",
        )
        return {"success": True, "mixed_mode": False}

    def start_rolling_migration(
        self,
        source_version: str,
        target_version: str,
    ) -> Dict[str, Any]:
        """Start a rolling migration."""
        if self._migration_in_progress:
            return {
                "success": False,
                "error": "Migration already in progress",
            }

        compatibility = self.check_compatibility(
            source_version, target_version
        )
        level = compatibility.get("compatibility_level")
        if level == CompatibilityLevel.NONE.value:
            return {
                "success": False,
                "error": "No compatibility between versions",
            }

        self._migration_in_progress = True
        self._telemetry.log_platform_event(
            "migration_started",
            "compatibility",
            {"source": source_version,
             "target": target_version},
        )

        return {
            "success": True,
            "source_version": source_version,
            "target_version": target_version,
            "compatibility": level,
            "shared_capabilities": (
                compatibility.get("shared_capabilities", [])
            ),
        }

    def complete_rolling_migration(
        self, target_version: str
    ) -> Dict[str, Any]:
        """Complete a rolling migration."""
        self._migration_in_progress = False
        self._current_version = target_version
        self._mixed_mode = False

        self._telemetry.log_platform_event(
            "migration_completed",
            "compatibility",
            {"target": target_version},
        )
        return {
            "success": True,
            "current_version": target_version,
        }

    def list_known_versions(self) -> List[Dict[str, Any]]:
        return [
            v.to_dict() for v in self._known_versions.values()
        ]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "current_version": self._current_version,
                "known_versions": list(self._known_versions.keys()),
                "mixed_mode": self._mixed_mode,
                "migration_in_progress": self._migration_in_progress,
                "matrix_size": len(self._matrix._matrix),
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"VersionCompatibilityManager("
                f"current={self._current_version}, "
                f"versions={len(self._known_versions)})"
            )
