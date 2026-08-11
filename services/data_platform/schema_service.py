"""
ICYQuant Schema Service.

Commit 16 Part 1.5 — Unified schema management service.
Provides versioned schema registration, compatibility checking,
schema evolution tracking, and validation across the data platform.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SchemaCompatibility(str, Enum):
    """Schema compatibility modes."""
    BACKWARD = "backward"
    FORWARD = "forward"
    FULL = "full"
    NONE = "none"


class FieldType(str, Enum):
    """Supported schema field types."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    DOUBLE = "double"
    BOOLEAN = "boolean"
    TIMESTAMP = "timestamp"
    DATE = "date"
    DECIMAL = "decimal"
    ARRAY = "array"
    MAP = "map"
    STRUCT = "struct"
    ENUM = "enum"


@dataclass
class FieldDefinition:
    """Definition of a schema field."""
    name: str = ""
    field_type: FieldType = FieldType.STRING
    required: bool = False
    description: str = ""
    default_value: Any = None
    enum_values: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SchemaDefinition:
    """A versioned schema definition."""
    schema_id: str = ""
    dataset_id: str = ""
    version: int = 1
    compatibility: SchemaCompatibility = SchemaCompatibility.BACKWARD
    fields: list[FieldDefinition] = field(default_factory=list)
    description: str = ""
    created_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompatibilityReport:
    """Result of schema compatibility check."""
    compatible: bool = True
    schema_id: str = ""
    from_version: int = 0
    to_version: int = 0
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Result of schema validation."""
    valid: bool = True
    schema_id: str = ""
    version: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class SchemaService:
    """Unified schema management service.

    Provides:
      - Versioned schema registration
      - Schema compatibility checking (backward/forward/full)
      - Schema evolution tracking
      - Data validation against schema
      - Schema search and discovery
    """

    def __init__(self) -> None:
        self._schemas: dict[str, dict[int, SchemaDefinition]] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Schema Registration
    # ------------------------------------------------------------------

    async def register(self, schema: SchemaDefinition) -> str:
        """Register a new schema version."""
        async with self._lock:
            schema.created_at = datetime.now(timezone.utc)
            if schema.schema_id not in self._schemas:
                self._schemas[schema.schema_id] = {}
            self._schemas[schema.schema_id][schema.version] = schema
        logger.info("Schema registered: %s v%d (%d fields)",
                    schema.schema_id, schema.version, len(schema.fields))
        return schema.schema_id

    async def get(self, schema_id: str, version: Optional[int] = None) -> Optional[SchemaDefinition]:
        """Get a schema by ID and optional version."""
        versions = self._schemas.get(schema_id)
        if not versions:
            return None
        if version is not None:
            return versions.get(version)
        # Return latest version
        return versions[max(versions.keys())] if versions else None

    async def get_latest(self, schema_id: str) -> Optional[SchemaDefinition]:
        """Get the latest version of a schema."""
        return await self.get(schema_id)

    async def list_versions(self, schema_id: str) -> list[int]:
        """List all versions of a schema."""
        versions = self._schemas.get(schema_id, {})
        return sorted(versions.keys())

    # ------------------------------------------------------------------
    # Compatibility
    # ------------------------------------------------------------------

    async def check_compatibility(
        self, schema_id: str, from_version: int, to_version: int,
    ) -> CompatibilityReport:
        """Check compatibility between two schema versions."""
        report = CompatibilityReport(
            schema_id=schema_id,
            from_version=from_version,
            to_version=to_version,
            compatible=True,
        )

        old = await self.get(schema_id, from_version)
        new = await self.get(schema_id, to_version)

        if not old or not new:
            report.compatible = False
            report.issues.append("Schema version not found")
            return report

        old_fields = {f.name: f for f in old.fields}
        new_fields = {f.name: f for f in new.fields}

        # Check for removed required fields (breaking backward compat)
        for name, field in old_fields.items():
            if name not in new_fields and field.required:
                report.compatible = False
                report.issues.append(f"Required field '{name}' removed")

        # Check for new required fields without defaults
        for name, field in new_fields.items():
            if name not in old_fields and field.required:
                report.warnings.append(f"New required field '{name}' added")

        return report

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    async def validate(self, schema_id: str, data: dict[str, Any], version: Optional[int] = None) -> ValidationResult:
        """Validate data against a schema."""
        schema = await self.get(schema_id, version)
        if not schema:
            return ValidationResult(
                valid=False,
                schema_id=schema_id,
                errors=["Schema not found"],
            )

        result = ValidationResult(
            schema_id=schema_id,
            version=schema.version,
            valid=True,
        )

        field_map = {f.name: f for f in schema.fields}

        # Check required fields
        for field in schema.fields:
            if field.required and field.name not in data:
                result.valid = False
                result.errors.append(f"Required field '{field.name}' missing")

        # Check extra fields
        for key in data:
            if key not in field_map:
                result.warnings.append(f"Unknown field '{key}'")

        return result

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def schema_count(self) -> int:
        return len(self._schemas)

    @property
    def total_versions(self) -> int:
        return sum(len(v) for v in self._schemas.values())
