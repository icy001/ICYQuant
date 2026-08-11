"""
Strategy version management.

Handles semantic versioning, version comparison, compatibility checks,
and rollback tracking for production strategies.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class VersionBump(str, Enum):
    """Version bump type."""

    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"


@dataclass(order=True)
class StrategyVersion:
    """Semantic version for strategy packages."""

    major: int
    minor: int
    patch: int
    prerelease: Optional[str] = None
    build: Optional[str] = None

    @classmethod
    def parse(cls, version_str: str) -> StrategyVersion:
        """Parse a version string into a StrategyVersion.

        Supports formats:
            - 1.0.0
            - 1.0.0-alpha.1
            - 1.0.0+build.123
            - 1.0.0-alpha.1+build.123
        """
        pattern = re.compile(
            r"^(?P<major>\d+)"
            r"\.(?P<minor>\d+)"
            r"\.(?P<patch>\d+)"
            r"(?:-(?P<prerelease>[0-9A-Za-z.-]+))?"
            r"(?:\+(?P<build>[0-9A-Za-z.-]+))?$"
        )
        match = pattern.match(version_str.strip())
        if not match:
            raise ValueError(f"Invalid version string: {version_str}")

        return cls(
            major=int(match.group("major")),
            minor=int(match.group("minor")),
            patch=int(match.group("patch")),
            prerelease=match.group("prerelease"),
            build=match.group("build"),
        )

    def bump(self, bump_type: VersionBump) -> StrategyVersion:
        """Return a new version with the specified component bumped."""
        major, minor, patch = self.major, self.minor, self.patch
        if bump_type == VersionBump.MAJOR:
            return StrategyVersion(major + 1, 0, 0)
        elif bump_type == VersionBump.MINOR:
            return StrategyVersion(major, minor + 1, 0)
        else:
            return StrategyVersion(major, minor, patch + 1)

    def is_compatible_with(self, other: StrategyVersion) -> bool:
        """Check if this version's major matches (compatible API)."""
        return self.major == other.major

    @property
    def is_prerelease(self) -> bool:
        return self.prerelease is not None

    @property
    def is_stable(self) -> bool:
        return self.prerelease is None and self.major > 0

    def __str__(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            base += f"-{self.prerelease}"
        if self.build:
            base += f"+{self.build}"
        return base

    def __repr__(self) -> str:
        return f"StrategyVersion({self})"


@dataclass
class VersionEntry:
    """A versioned entry in the strategy registry."""

    strategy_id: str
    version: StrategyVersion
    changelog: str = ""
    author: str = "unknown"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = False
    is_canary: bool = False
    canary_pct: float = 0.0
    deployment_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "version": str(self.version),
            "changelog": self.changelog,
            "author": self.author,
            "created_at": self.created_at.isoformat(),
            "is_active": self.is_active,
            "is_canary": self.is_canary,
            "canary_pct": self.canary_pct,
        }


@dataclass
class VersionHistory:
    """Complete version history for a strategy."""

    strategy_id: str
    versions: List[VersionEntry] = field(default_factory=list)
    last_rollback: Optional[Dict[str, Any]] = None

    @property
    def active_version(self) -> Optional[VersionEntry]:
        for v in self.versions:
            if v.is_active and not v.is_canary:
                return v
        return None

    @property
    def canary_version(self) -> Optional[VersionEntry]:
        for v in self.versions:
            if v.is_canary:
                return v
        return None

    @property
    def latest_version(self) -> Optional[VersionEntry]:
        if not self.versions:
            return None
        return sorted(self.versions, key=lambda v: v.version, reverse=True)[0]

    def add_version(self, entry: VersionEntry) -> None:
        self.versions.append(entry)
        if entry.is_active and not entry.is_canary:
            for v in self.versions:
                if v != entry and v.is_active and not v.is_canary:
                    v.is_active = False

    def get_version(self, version: StrategyVersion) -> Optional[VersionEntry]:
        for v in self.versions:
            if v.version == version:
                return v
        return None

    def get_rollback_target(
        self,
        steps: int = 1,
    ) -> Optional[VersionEntry]:
        """Get a version to roll back to (n steps back in stable versions)."""
        stable = sorted(
            [v for v in self.versions if v.version.is_stable],
            key=lambda v: v.version,
            reverse=True,
        )
        if len(stable) > steps:
            return stable[steps]
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "versions": [v.to_dict() for v in self.versions],
            "active_version": str(self.active_version.version) if self.active_version else None,
            "canary_version": str(self.canary_version.version) if self.canary_version else None,
            "latest_version": str(self.latest_version.version) if self.latest_version else None,
            "last_rollback": self.last_rollback,
        }
