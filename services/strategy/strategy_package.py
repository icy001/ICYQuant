"""
Strategy package model and loader.

Represents a distributable strategy package containing manifest,
source code, configuration, and test resources.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .strategy_manifest import StrategyManifest
from .strategy_version import StrategyVersion

logger = logging.getLogger(__name__)


class PackageFormat(str, Enum):
    """Supported package formats."""

    LOCAL = "local"
    """Local directory or file."""

    GIT = "git"
    """Git repository."""

    ARTIFACT = "artifact"
    """Artifact repository (e.g. Nexus, Artifactory)."""

    REMOTE_REGISTRY = "remote_registry"
    """Remote strategy registry."""


@dataclass
class PackageSource:
    """Source location for a strategy package."""

    format: PackageFormat
    location: str
    """URI or path to the package."""

    credentials: Optional[Dict[str, str]] = None
    """Optional credentials for protected sources."""

    ref: Optional[str] = None
    """Git ref (branch, tag, commit) for git sources."""

    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "format": self.format.value,
            "location": self.location,
            "ref": self.ref,
        }


@dataclass
class StrategyPackage:
    """A complete strategy package for distribution and deployment."""

    manifest: StrategyManifest
    source: Optional[PackageSource] = None

    # Package content (loaded on demand)
    _code: Optional[str] = None
    _config: Optional[Dict[str, Any]] = None
    _test_resources: Optional[List[Dict[str, Any]]] = None

    loaded_at: Optional[datetime] = None
    checksum: str = ""
    size_bytes: int = 0

    # Lifecycle
    is_signed: bool = False
    signature: str = ""
    _validated: bool = False
    validation_errors: List[str] = field(default_factory=list)

    @property
    def package_id(self) -> str:
        return f"{self.manifest.name}@{self.manifest.version}"

    @property
    def version(self) -> StrategyVersion:
        return StrategyVersion.parse(self.manifest.version)

    @property
    def is_validated(self) -> bool:
        return self._validated

    def mark_validated(self) -> None:
        self._validated = True

    def mark_loaded(self) -> None:
        self.loaded_at = datetime.now(timezone.utc)

    def add_validation_error(self, error: str) -> None:
        self.validation_errors.append(error)
        self._validated = False

    def to_summary(self) -> Dict[str, Any]:
        return {
            "package_id": self.package_id,
            "name": self.manifest.name,
            "version": self.manifest.version,
            "author": self.manifest.author,
            "description": self.manifest.description,
            "validated": self._validated,
            "validation_errors": self.validation_errors,
            "is_signed": self.is_signed,
            "size_bytes": self.size_bytes,
            "loaded_at": self.loaded_at.isoformat() if self.loaded_at else None,
            "source": self.source.to_dict() if self.source else None,
        }
