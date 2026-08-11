"""
Schema Registry — versioned registry for market data schemas with
forward/backward compatibility checks.

Commit 16 Part 1.2
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CompatibilityLevel(str, Enum):
    """Schema compatibility levels (inspired by Confluent Schema Registry)."""

    NONE = "none"           # No compatibility checks
    BACKWARD = "backward"   # New schema can read old data
    FORWARD = "forward"     # Old schema can read new data
    FULL = "full"           # Both backward and forward
    BACKWARD_TRANSITIVE = "backward_transitive"
    FORWARD_TRANSITIVE = "forward_transitive"
    FULL_TRANSITIVE = "full_transitive"


@dataclass
class SchemaEntry:
    """A versioned schema entry."""

    schema_id: str = ""
    schema_name: str = ""
    schema_version: int = 1
    schema_type: str = "json"           # json, avro, protobuf, custom
    schema_definition: dict[str, Any] = field(default_factory=dict)
    compatibility: CompatibilityLevel = CompatibilityLevel.BACKWARD

    required_fields: list[str] = field(default_factory=list)
    optional_fields: list[str] = field(default_factory=list)
    field_types: dict[str, str] = field(default_factory=dict)

    description: str = ""
    created_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class SchemaRegistry:
    """
    Registry for market data schemas with version management.

    Supports schema evolution with compatibility checks, ensuring
    that schema changes don't break downstream consumers.
    """

    def __init__(self) -> None:
        self._schemas: dict[str, dict[int, SchemaEntry]] = {}
        self._latest: dict[str, int] = {}

    async def initialize(self) -> None:
        logger.info("SchemaRegistry initialized with %d schema families", len(self._schemas))

    # ── Registration ───────────────────────────────

    async def register_schema(
        self, entry: SchemaEntry, compatibility: Optional[CompatibilityLevel] = None
    ) -> SchemaEntry:
        """Register a new schema version."""
        name = entry.schema_name

        if name not in self._schemas:
            self._schemas[name] = {}

        # Auto-increment version
        if name in self._latest:
            entry.schema_version = self._latest[name] + 1

        # Compatibility check
        if compatibility:
            await self._check_compatibility(name, entry, compatibility)

        entry.created_at = datetime.now(timezone.utc)
        self._schemas[name][entry.schema_version] = entry
        self._latest[name] = entry.schema_version

        logger.info("Registered schema %s v%d (compat: %s)",
                     name, entry.schema_version, entry.compatibility.value)
        return entry

    async def get_schema(self, schema_name: str, version: Optional[int] = None) -> Optional[SchemaEntry]:
        """Get a schema by name and optionally version. Returns latest if no version."""
        versions = self._schemas.get(schema_name, {})
        if not versions:
            return None
        if version is not None:
            return versions.get(version)
        return versions.get(self._latest.get(schema_name, 0))

    async def get_latest_version(self, schema_name: str) -> int:
        """Get the latest version number for a schema."""
        return self._latest.get(schema_name, 0)

    async def list_schemas(self) -> list[str]:
        """List all registered schema names."""
        return list(self._schemas.keys())

    async def get_version_history(self, schema_name: str) -> list[SchemaEntry]:
        """Get all versions of a schema, sorted by version."""
        versions = self._schemas.get(schema_name, {})
        return sorted(versions.values(), key=lambda e: e.schema_version)

    # ── Compatibility ──────────────────────────────

    async def _check_compatibility(
        self, schema_name: str, new_entry: SchemaEntry, level: CompatibilityLevel
    ) -> None:
        """Verify schema compatibility."""
        latest = await self.get_schema(schema_name)
        if latest is None:
            return

        if level == CompatibilityLevel.NONE:
            return

        if level in (CompatibilityLevel.BACKWARD, CompatibilityLevel.FULL,
                     CompatibilityLevel.BACKWARD_TRANSITIVE, CompatibilityLevel.FULL_TRANSITIVE):
            # Check that new schema doesn't drop required fields
            removed = set(latest.required_fields) - set(new_entry.required_fields)
            if removed:
                raise ValueError(
                    f"Backward compatibility violation: removed required fields {removed}"
                )

        if level in (CompatibilityLevel.FORWARD, CompatibilityLevel.FULL,
                     CompatibilityLevel.FORWARD_TRANSITIVE, CompatibilityLevel.FULL_TRANSITIVE):
            # Check that new schema doesn't add required fields
            added = set(new_entry.required_fields) - set(latest.required_fields)
            if added:
                raise ValueError(
                    f"Forward compatibility violation: added required fields {added}"
                )

    async def set_default_compatibility(
        self, schema_name: str, level: CompatibilityLevel
    ) -> None:
        """Set the default compatibility level for a schema family."""
        versions = self._schemas.get(schema_name, {})
        for entry in versions.values():
            entry.compatibility = level

    @property
    def schema_count(self) -> int:
        return sum(len(v) for v in self._schemas.values())

    @property
    def family_count(self) -> int:
        return len(self._schemas)


# Type aliases for __init__.py compatibility
SchemaDefinition = SchemaEntry
SchemaVersion = int
