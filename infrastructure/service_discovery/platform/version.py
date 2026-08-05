"""Platform version management for ICYQuant service discovery.

Provides ``PlatformVersion`` and ``PlatformVersionManager`` for
tracking platform versions, service discovery schema versions,
and rollback targeting.
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class PlatformVersion:
    """Platform version metadata.

    Tracks version information for platform snapshots, enabling
    audit trails and rollback targeting.
    """

    version: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    checksum: str = ""
    operator: str = "system"
    reason: str = ""
    source: str = "bootstrap"
    parent_version: Optional[int] = None
    description: str = ""
    schema_version: str = "1.5"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "timestamp": self.timestamp.isoformat(),
            "checksum": self.checksum,
            "operator": self.operator,
            "reason": self.reason,
            "source": self.source,
            "parent_version": self.parent_version,
            "description": self.description,
            "schema_version": self.schema_version,
        }


class PlatformVersionManager:
    """Manages platform version history.

    Provides version tracking, checksum verification,
    and rollback target lookup for platform configurations.
    """

    def __init__(self, max_history: int = 100) -> None:
        self._versions: Dict[int, PlatformVersion] = {}
        self._max_history = max_history
        self._lock = threading.Lock()
        self._current_version = 0

    def record(
        self,
        config_data: Dict[str, Any],
        operator: str = "system",
        reason: str = "",
        source: str = "bootstrap",
        parent_version: Optional[int] = None,
        description: str = "",
    ) -> PlatformVersion:
        self._current_version += 1
        checksum = self._calculate_checksum(config_data)

        version_meta = PlatformVersion(
            version=self._current_version,
            checksum=checksum,
            operator=operator,
            reason=reason,
            source=source,
            parent_version=parent_version,
            description=description,
        )

        with self._lock:
            self._versions[self._current_version] = version_meta
            if len(self._versions) > self._max_history:
                oldest = min(self._versions.keys())
                del self._versions[oldest]

        return version_meta

    def get_version(self, version: int) -> Optional[PlatformVersion]:
        with self._lock:
            return self._versions.get(version)

    def get_current(self) -> Optional[PlatformVersion]:
        return self.get_version(self._current_version)

    def get_history(self) -> List[PlatformVersion]:
        with self._lock:
            return sorted(
                self._versions.values(),
                key=lambda v: v.version,
            )

    def find_rollback_target(
        self, version: int
    ) -> Optional[PlatformVersion]:
        return self.get_version(version)

    def verify_checksum(
        self, version: int, config_data: Dict[str, Any]
    ) -> bool:
        version_meta = self.get_version(version)
        if version_meta is None:
            return False
        actual = self._calculate_checksum(config_data)
        return version_meta.checksum == actual

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "current_version": self._current_version,
                "version_count": len(self._versions),
                "max_history": self._max_history,
                "versions": [
                    v.to_dict()
                    for v in sorted(
                        self._versions.values(),
                        key=lambda v: v.version,
                    )
                ],
            }

    @staticmethod
    def _calculate_checksum(config_data: Dict[str, Any]) -> str:
        normalized = json.dumps(
            PlatformVersionManager._sort_dict(config_data),
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(normalized.encode()).hexdigest()

    @staticmethod
    def _sort_dict(
        d: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            k: PlatformVersionManager._sort_dict(v)
            if isinstance(v, dict)
            else v
            for k, v in sorted(d.items())
        }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"PlatformVersionManager(current={self._current_version}, "
                f"total={len(self._versions)})"
            )
