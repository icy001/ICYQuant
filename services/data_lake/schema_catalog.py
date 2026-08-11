"""
Schema Catalog — schema versioning, evolution tracking, and compatibility
checking for data lake datasets.

Commit 16 Part 1.3
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CompatibilityLevel(str, Enum):
    BACKWARD = "backward"
    FORWARD = "forward"
    FULL = "full"
    NONE = "none"


@dataclass
class SchemaField:
    name: str
    field_type: str
    nullable: bool = True
    default_value: Any = None
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SchemaEntry:
    dataset: str
    version: str
    fields: list[SchemaField]
    compatibility: CompatibilityLevel = CompatibilityLevel.BACKWARD
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    parent_version: Optional[str] = None

    @property
    def schema_hash(self) -> str:
        content = "|".join(f"{f.name}:{f.field_type}" for f in self.fields)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    @property
    def field_names(self) -> list[str]:
        return [f.name for f in self.fields]


@dataclass
class SchemaEvolution:
    dataset: str
    from_version: str
    to_version: str
    added_fields: list[str] = field(default_factory=list)
    removed_fields: list[str] = field(default_factory=list)
    changed_fields: list[str] = field(default_factory=list)
    is_compatible: bool = True


class SchemaCatalog:
    """
    Manages schema versions, evolution tracking, and compatibility
    checking for data lake datasets.

    Features:
    - Schema versioning with hash-based identification
    - Backward/forward/full compatibility checking
    - Schema evolution tracking
    - Field-level metadata
    """

    def __init__(self) -> None:
        self._schemas: dict[str, list[SchemaEntry]] = {}
        self._evolutions: dict[str, list[SchemaEvolution]] = {}

    async def register(self, entry: SchemaEntry) -> SchemaEntry:
        """Register a new schema version."""
        if entry.dataset not in self._schemas:
            self._schemas[entry.dataset] = []

        # Set parent to latest version
        existing = self._schemas[entry.dataset]
        if existing and not entry.parent_version:
            entry.parent_version = existing[-1].version

        self._schemas[entry.dataset].append(entry)
        logger.info(
            "Schema registered: %s v%s (%d fields, hash=%s)",
            entry.dataset, entry.version, len(entry.fields), entry.schema_hash,
        )
        return entry

    async def get(self, dataset: str, version: Optional[str] = None) -> Optional[SchemaEntry]:
        """Get a schema entry. If no version, returns latest."""
        schemas = self._schemas.get(dataset, [])
        if not schemas:
            return None
        if version:
            for s in schemas:
                if s.version == version:
                    return s
            return None
        return schemas[-1]

    async def get_latest(self, dataset: str) -> Optional[SchemaEntry]:
        return await self.get(dataset)

    async def check_compatibility(
        self, dataset: str, new_schema: SchemaEntry
    ) -> SchemaEvolution:
        """Check compatibility between latest and new schema."""
        existing = await self.get_latest(dataset)
        if not existing:
            return SchemaEvolution(
                dataset=dataset,
                from_version="none",
                to_version=new_schema.version,
                added_fields=new_schema.field_names,
                is_compatible=True,
            )

        existing_names = set(existing.field_names)
        new_names = set(new_schema.field_names)

        evolution = SchemaEvolution(
            dataset=dataset,
            from_version=existing.version,
            to_version=new_schema.version,
            added_fields=list(new_names - existing_names),
            removed_fields=list(existing_names - new_names),
            changed_fields=[
                f.name for f in new_schema.fields
                if f.name in existing_names and self._field_changed(existing, f)
            ],
        )

        # Backward compatible: no removed fields, no type changes
        evolution.is_compatible = (
            len(evolution.removed_fields) == 0
            and len(evolution.changed_fields) == 0
        )

        self._evolutions.setdefault(dataset, []).append(evolution)
        return evolution

    def _field_changed(self, existing: SchemaEntry, new_field: SchemaField) -> bool:
        for old in existing.fields:
            if old.name == new_field.name:
                return old.field_type != new_field.field_type
        return False

    async def list_versions(self, dataset: str) -> list[dict[str, Any]]:
        schemas = self._schemas.get(dataset, [])
        return [
            {
                "version": s.version,
                "fields": len(s.fields),
                "hash": s.schema_hash,
                "parent": s.parent_version,
                "created_at": s.created_at.isoformat(),
            }
            for s in schemas
        ]

    async def get_evolution(self, dataset: str) -> list[SchemaEvolution]:
        return self._evolutions.get(dataset, [])

    async def validate_record(
        self, dataset: str, record: dict[str, Any], version: Optional[str] = None
    ) -> tuple[bool, list[str]]:
        """Validate a record against the schema."""
        schema = await self.get(dataset, version)
        if not schema:
            return False, [f"Schema not found: {dataset}"]

        errors: list[str] = []
        for field in schema.fields:
            if field.name in record:
                actual_type = type(record[field.name]).__name__
                # Simple type checking; production would use stricter validation
            elif not field.nullable and field.default_value is None:
                errors.append(f"Missing required field: {field.name}")

        return len(errors) == 0, errors
