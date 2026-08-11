"""
Schema Registry — centralized schema management with versioning,
compatibility checking, and evolution support.

Commit 16 Part 1.4
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CompatibilityLevel(str, Enum):
    NONE = "none"
    BACKWARD = "backward"
    FORWARD = "forward"
    FULL = "full"
    BACKWARD_TRANSITIVE = "backward_transitive"
    FORWARD_TRANSITIVE = "forward_transitive"
    FULL_TRANSITIVE = "full_transitive"


@dataclass
class SchemaVersion:
    """A specific version of a schema."""
    version_id: int
    schema: dict[str, Any]
    fingerprint: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.fingerprint:
            schema_str = json.dumps(self.schema, sort_keys=True)
            self.fingerprint = hashlib.sha256(schema_str.encode()).hexdigest()[:16]


@dataclass
class SchemaEntry:
    """A registered schema with version history."""
    subject: str
    versions: list[SchemaVersion] = field(default_factory=list)
    compatibility: CompatibilityLevel = CompatibilityLevel.BACKWARD
    latest_version_id: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def latest_schema(self) -> Optional[SchemaVersion]:
        return self.versions[-1] if self.versions else None


class SchemaRegistry:
    """
    Centralized schema registry for the streaming platform.

    Manages schema versions, compatibility checking, and evolution
    across all topics and event types.

    Features:
    - Schema registration and versioning
    - Multiple compatibility levels
    - Fingerprint-based schema identification
    - Schema evolution validation
    - Topic-to-schema binding

    Usage::

        registry = SchemaRegistry()
        await registry.initialize()
        entry = await registry.register("market.tick", tick_schema)
        is_compat = await registry.check_compatibility("market.tick", new_schema)
    """

    def __init__(self) -> None:
        self._schemas: dict[str, SchemaEntry] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the schema registry."""
        logger.info("SchemaRegistry initialized.")

    async def register(
        self,
        subject: str,
        schema: dict[str, Any],
        *,
        compatibility: CompatibilityLevel = CompatibilityLevel.BACKWARD,
        metadata: Optional[dict[str, Any]] = None,
    ) -> SchemaEntry:
        """Register a new schema or a new version."""
        async with self._lock:
            if subject not in self._schemas:
                entry = SchemaEntry(subject=subject, compatibility=compatibility)
                self._schemas[subject] = entry
            else:
                entry = self._schemas[subject]

            version_id = entry.latest_version_id + 1
            version = SchemaVersion(
                version_id=version_id,
                schema=schema,
                metadata=metadata or {},
            )

            # Check compatibility with previous version
            if entry.versions:
                prev = entry.versions[-1]
                is_compat = self._check_compatibility(
                    prev.schema, schema, entry.compatibility,
                )
                if not is_compat:
                    raise ValueError(
                        f"Schema version {version_id} for '{subject}' "
                        f"violates {entry.compatibility.value} compatibility"
                    )

            entry.versions.append(version)
            entry.latest_version_id = version_id
            entry.updated_at = datetime.now(timezone.utc)

            logger.info(
                "Schema registered: %s v%d (fingerprint: %s)",
                subject, version_id, version.fingerprint,
            )
            return entry

    def _check_compatibility(
        self,
        old_schema: dict[str, Any],
        new_schema: dict[str, Any],
        level: CompatibilityLevel,
    ) -> bool:
        """Check schema compatibility between versions."""
        if level == CompatibilityLevel.NONE:
            return True

        old_fields = set(old_schema.get("fields", {}).keys()) if isinstance(old_schema, dict) else set()
        new_fields = set(new_schema.get("fields", {}).keys()) if isinstance(new_schema, dict) else set()

        if level in (CompatibilityLevel.BACKWARD, CompatibilityLevel.BACKWARD_TRANSITIVE):
            # New schema must be able to read old data: no field removal
            removed = old_fields - new_fields
            if removed:
                logger.warning(
                    "Backward compatibility violation: removed fields %s", removed,
                )
                return False

        if level in (CompatibilityLevel.FORWARD, CompatibilityLevel.FORWARD_TRANSITIVE):
            # Old schema must be able to read new data: no required new fields
            added = new_fields - old_fields
            required_new = {
                f for f in added
                if new_schema.get("fields", {}).get(f, {}).get("required", False)
            }
            if required_new:
                logger.warning(
                    "Forward compatibility violation: new required fields %s", required_new,
                )
                return False

        if level in (CompatibilityLevel.FULL, CompatibilityLevel.FULL_TRANSITIVE):
            return self._check_compatibility(
                old_schema, new_schema, CompatibilityLevel.BACKWARD,
            ) and self._check_compatibility(
                old_schema, new_schema, CompatibilityLevel.FORWARD,
            )

        return True

    async def check_compatibility(
        self, subject: str, new_schema: dict[str, Any]
    ) -> bool:
        """Check if a new schema is compatible with the latest version."""
        entry = self._schemas.get(subject)
        if entry is None or not entry.versions:
            return True

        latest = entry.versions[-1]
        return self._check_compatibility(
            latest.schema, new_schema, entry.compatibility,
        )

    async def get_schema(
        self, subject: str, version_id: Optional[int] = None
    ) -> Optional[SchemaVersion]:
        """Get a schema by subject and optional version."""
        entry = self._schemas.get(subject)
        if entry is None:
            return None

        if version_id is not None:
            for v in entry.versions:
                if v.version_id == version_id:
                    return v
            return None

        return entry.latest_schema

    async def get_by_fingerprint(
        self, subject: str, fingerprint: str
    ) -> Optional[SchemaVersion]:
        """Find a schema version by fingerprint."""
        entry = self._schemas.get(subject)
        if entry is None:
            return None

        for v in entry.versions:
            if v.fingerprint == fingerprint:
                return v
        return None

    async def list_subjects(self) -> list[str]:
        """List all registered schema subjects."""
        return list(self._schemas.keys())

    async def list_versions(self, subject: str) -> list[int]:
        """List all version IDs for a subject."""
        entry = self._schemas.get(subject)
        if entry is None:
            return []
        return [v.version_id for v in entry.versions]

    async def delete_subject(self, subject: str) -> bool:
        """Delete all versions of a subject."""
        async with self._lock:
            if subject in self._schemas:
                del self._schemas[subject]
                return True
        return False

    async def summary(self) -> dict[str, Any]:
        """Get schema registry summary."""
        return {
            "total_subjects": len(self._schemas),
            "subjects": {
                subject: {
                    "versions": entry.latest_version_id,
                    "compatibility": entry.compatibility.value,
                    "latest_fingerprint": entry.latest_schema.fingerprint if entry.latest_schema else None,
                }
                for subject, entry in self._schemas.items()
            },
        }
