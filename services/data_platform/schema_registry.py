"""ICYQuant Schema Registry.

Centralized schema management for all data assets.
Supports:
    - Schema definition and registration
    - Versioned schemas with compatibility checks
    - Schema evolution (BACKWARD, FORWARD, FULL, NONE)
    - Validation on write/read
    - Schema discovery

Usage::

    registry = SchemaRegistry(SchemaRegistryConfig())
    registry.register("market_tick_v1", schema)
    is_compat = registry.check_compatibility("market_tick", "market_tick_v2")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from services.data_platform.config import (
    SchemaRegistryConfig,
    SchemaCompatibility,
)


# ============================================================================
# Schema Types
# ============================================================================


class FieldType(str, Enum):
    """Supported field data types."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    TIMESTAMP = "timestamp"
    DATE = "date"
    ARRAY = "array"
    MAP = "map"
    STRUCT = "struct"
    DECIMAL = "decimal"


@dataclass
class FieldDefinition:
    """Definition of a single field in a schema."""

    name: str
    field_type: FieldType
    description: str = ""
    required: bool = False
    default: Any = None
    nullable: bool = True
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "field_type": self.field_type.value,
            "description": self.description,
            "required": self.required,
            "default": self.default,
            "nullable": self.nullable,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FieldDefinition":
        return cls(
            name=d["name"],
            field_type=FieldType(d["field_type"]),
            description=d.get("description", ""),
            required=d.get("required", False),
            default=d.get("default"),
            nullable=d.get("nullable", True),
            tags=d.get("tags", []),
            metadata=d.get("metadata", {}),
        )


@dataclass
class SchemaDefinition:
    """Complete schema definition for a data asset."""

    name: str
    version: int = 1
    description: str = ""
    fields: List[FieldDefinition] = field(default_factory=list)
    primary_key: List[str] = field(default_factory=list)
    partition_keys: List[str] = field(default_factory=list)
    parent_schema: Optional[str] = None  # For schema evolution
    compatibility: SchemaCompatibility = SchemaCompatibility.BACKWARD
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    is_deprecated: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "fields": [f.to_dict() for f in self.fields],
            "primary_key": self.primary_key,
            "partition_keys": self.partition_keys,
            "parent_schema": self.parent_schema,
            "compatibility": self.compatibility.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_deprecated": self.is_deprecated,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SchemaDefinition":
        return cls(
            name=d["name"],
            version=d.get("version", 1),
            description=d.get("description", ""),
            fields=[FieldDefinition.from_dict(f) for f in d.get("fields", [])],
            primary_key=d.get("primary_key", []),
            partition_keys=d.get("partition_keys", []),
            parent_schema=d.get("parent_schema"),
            compatibility=SchemaCompatibility(d.get("compatibility", "backward")),
            created_at=datetime.fromisoformat(d["created_at"]) if "created_at" in d else datetime.utcnow(),
            updated_at=datetime.fromisoformat(d["updated_at"]) if "updated_at" in d else datetime.utcnow(),
            is_deprecated=d.get("is_deprecated", False),
            metadata=d.get("metadata", {}),
        )

    def get_field_names(self) -> List[str]:
        """Get all field names."""
        return [f.name for f in self.fields]

    def get_required_fields(self) -> List[str]:
        """Get names of required fields."""
        return [f.name for f in self.fields if f.required]


@dataclass
class CompatibilityReport:
    """Report on schema compatibility between two versions."""

    is_compatible: bool
    compatibility_mode: SchemaCompatibility
    changes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_compatible": self.is_compatible,
            "compatibility_mode": self.compatibility_mode.value,
            "changes": self.changes,
            "warnings": self.warnings,
            "errors": self.errors,
        }


@dataclass
class ValidationResult:
    """Result of validating data against a schema."""

    is_valid: bool
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    validated_count: int = 0
    failed_count: int = 0


# ============================================================================
# Schema Registry
# ============================================================================


class SchemaRegistry:
    """Centralized Schema Registry.

    Manages all data schemas with versioning, compatibility checking,
    and validation capabilities.

    Usage::

        registry = SchemaRegistry()
        registry.register("market_tick_v1", tick_schema)
        registry.evolve("market_tick", tick_v2_schema)
        result = registry.validate("market_tick", data)
    """

    def __init__(self, config: Optional[SchemaRegistryConfig] = None) -> None:
        self.config = config or SchemaRegistryConfig()
        self._schemas: Dict[str, List[SchemaDefinition]] = {}
        self._latest: Dict[str, str] = {}  # base_name → latest version key

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, name: str, schema: SchemaDefinition) -> SchemaDefinition:
        """Register a new schema.

        Args:
            name: Schema name (can include version, e.g. "tick_v1").
            schema: SchemaDefinition.

        Returns:
            Registered SchemaDefinition.

        Raises:
            ValueError: If schema name already exists.
        """
        base_name = schema.name
        if base_name not in self._schemas:
            self._schemas[base_name] = []

        # Check for duplicate version
        for existing in self._schemas[base_name]:
            if existing.version == schema.version:
                raise ValueError(
                    f"Schema '{base_name}' version {schema.version} already exists"
                )

        schema.name = base_name
        schema.created_at = datetime.utcnow()
        schema.updated_at = datetime.utcnow()
        self._schemas[base_name].append(schema)
        self._latest[base_name] = f"{base_name}_v{schema.version}"

        return schema

    def evolve(
        self,
        base_name: str,
        new_schema: SchemaDefinition,
        check_compatibility: bool = True,
    ) -> SchemaDefinition:
        """Evolve a schema to a new version.

        Creates a new version of an existing schema with compatibility
        checking against the previous version.

        Args:
            base_name: Base schema name (without version).
            new_schema: New schema definition.
            check_compatibility: Run compatibility check.

        Returns:
            The new versioned SchemaDefinition.

        Raises:
            ValueError: If base schema doesn't exist or compatibility fails.
        """
        if base_name not in self._schemas:
            raise ValueError(f"Schema '{base_name}' not found. Register first.")

        latest = self.get_latest(base_name)
        if not latest:
            raise ValueError(f"No versions found for schema '{base_name}'")

        # Set version
        new_schema.version = latest.version + 1
        new_schema.name = base_name
        new_schema.parent_schema = f"{base_name}_v{latest.version}"

        # Compatibility check
        if check_compatibility:
            report = self.check_compatibility(latest, new_schema)
            if not report.is_compatible:
                raise ValueError(
                    f"Schema evolution incompatible: {report.errors}"
                )

        return self.register(base_name, new_schema)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, name: str) -> Optional[SchemaDefinition]:
        """Get a schema by exact name (with version).

        Args:
            name: Full schema name (e.g. "tick_v1").

        Returns:
            SchemaDefinition or None.
        """
        # Parse base name and version
        base_name, version = self._parse_name(name)
        if base_name not in self._schemas:
            return None

        for schema in self._schemas[base_name]:
            if schema.version == version:
                return schema

        return None

    def get_latest(self, base_name: str) -> Optional[SchemaDefinition]:
        """Get the latest version of a schema.

        Args:
            base_name: Base schema name (without version).

        Returns:
            Latest SchemaDefinition or None.
        """
        versions = self._schemas.get(base_name, [])
        if not versions:
            return None

        return max(versions, key=lambda s: s.version)

    def get_version(self, base_name: str, version: int) -> Optional[SchemaDefinition]:
        """Get a specific version of a schema.

        Args:
            base_name: Base schema name.
            version: Version number.

        Returns:
            SchemaDefinition or None.
        """
        versions = self._schemas.get(base_name, [])
        for schema in versions:
            if schema.version == version:
                return schema
        return None

    def list_versions(self, base_name: str) -> List[SchemaDefinition]:
        """List all versions of a schema.

        Args:
            base_name: Base schema name.

        Returns:
            List of all SchemaDefinition versions, sorted by version.
        """
        versions = self._schemas.get(base_name, [])
        return sorted(versions, key=lambda s: s.version)

    def list_all(self) -> List[SchemaDefinition]:
        """List all schemas across all base names."""
        result: List[SchemaDefinition] = []
        for versions in self._schemas.values():
            result.extend(versions)
        return result

    # ------------------------------------------------------------------
    # Compatibility
    # ------------------------------------------------------------------

    def check_compatibility(
        self,
        old_schema: SchemaDefinition,
        new_schema: SchemaDefinition,
        mode: Optional[SchemaCompatibility] = None,
    ) -> CompatibilityReport:
        """Check compatibility between two schema versions.

        Args:
            old_schema: Previous schema version.
            new_schema: New schema version.
            mode: Compatibility mode (defaults to new_schema's mode).

        Returns:
            CompatibilityReport.
        """
        mode = mode or new_schema.compatibility
        report = CompatibilityReport(
            is_compatible=True,
            compatibility_mode=mode,
        )

        old_fields = {f.name: f for f in old_schema.fields}
        new_fields = {f.name: f for f in new_schema.fields}

        # Check added fields
        added = set(new_fields.keys()) - set(old_fields.keys())
        for field_name in added:
            field = new_fields[field_name]
            report.changes.append(f"Added field: {field_name} ({field.field_type.value})")

            if mode == SchemaCompatibility.BACKWARD:
                if field.required:
                    report.errors.append(
                        f"BACKWARD incompatible: new required field '{field_name}'"
                    )
                    report.is_compatible = False
                else:
                    report.warnings.append(
                        f"New optional field '{field_name}' added"
                    )

        # Check removed fields
        removed = set(old_fields.keys()) - set(new_fields.keys())
        for field_name in removed:
            report.changes.append(f"Removed field: {field_name}")

            if mode in (SchemaCompatibility.BACKWARD, SchemaCompatibility.FULL):
                report.errors.append(
                    f"{mode.value.upper()} incompatible: field '{field_name}' removed"
                )
                report.is_compatible = False

        # Check type changes
        common = set(old_fields.keys()) & set(new_fields.keys())
        for field_name in common:
            old_field = old_fields[field_name]
            new_field = new_fields[field_name]

            if old_field.field_type != new_field.field_type:
                report.changes.append(
                    f"Type change: {field_name} {old_field.field_type.value} → {new_field.field_type.value}"
                )
                report.errors.append(
                    f"Incompatible type change for field '{field_name}'"
                )
                report.is_compatible = False

            if not old_field.required and new_field.required:
                report.warnings.append(
                    f"Field '{field_name}' changed from optional to required"
                )

        return report

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(
        self,
        schema_name: str,
        data: List[Dict[str, Any]],
        version: Optional[int] = None,
    ) -> ValidationResult:
        """Validate data against a schema.

        Args:
            schema_name: Schema name (base name or versioned).
            data: List of records to validate.
            version: Specific version (defaults to latest).

        Returns:
            ValidationResult with errors and warnings.
        """
        result = ValidationResult(is_valid=True, validated_count=0, failed_count=0)

        # Resolve schema
        if version is not None:
            schema = self.get_version(schema_name, version)
        elif "_v" in schema_name:
            schema = self.get(schema_name)
        else:
            schema = self.get_latest(schema_name)

        if not schema:
            return ValidationResult(
                is_valid=False,
                errors=[{"message": f"Schema '{schema_name}' not found"}],
            )

        field_map = {f.name: f for f in schema.fields}
        required_fields = schema.get_required_fields()

        for i, record in enumerate(data):
            record_valid = True

            # Check required fields
            for req_field in required_fields:
                if req_field not in record or record[req_field] is None:
                    field_def = field_map[req_field]
                    if field_def.required:
                        result.errors.append({
                            "record": i,
                            "field": req_field,
                            "message": f"Required field '{req_field}' is missing or null",
                        })
                        record_valid = False

            # Check field types
            for field_name, value in record.items():
                if field_name not in field_map:
                    result.warnings.append({
                        "record": i,
                        "field": field_name,
                        "message": f"Unknown field '{field_name}' not in schema",
                    })
                    continue

                field_def = field_map[field_name]
                type_valid, type_error = self._check_type(value, field_def.field_type)
                if not type_valid:
                    result.errors.append({
                        "record": i,
                        "field": field_name,
                        "message": type_error,
                    })
                    record_valid = False

            if record_valid:
                result.validated_count += 1
            else:
                result.failed_count += 1

        result.is_valid = result.failed_count == 0
        return result

    def _check_type(self, value: Any, field_type: FieldType) -> Tuple[bool, str]:
        """Check if a value matches the expected field type."""
        if value is None:
            return True, ""

        type_checks = {
            FieldType.STRING: lambda v: isinstance(v, str),
            FieldType.INTEGER: lambda v: isinstance(v, int) and not isinstance(v, bool),
            FieldType.FLOAT: lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
            FieldType.BOOLEAN: lambda v: isinstance(v, bool),
            FieldType.TIMESTAMP: lambda v: isinstance(v, str),
            FieldType.DATE: lambda v: isinstance(v, str),
            FieldType.ARRAY: lambda v: isinstance(v, list),
            FieldType.MAP: lambda v: isinstance(v, dict),
            FieldType.DECIMAL: lambda v: isinstance(v, (int, float, str)),
        }

        checker = type_checks.get(field_type)
        if checker and not checker(value):
            return False, f"Expected {field_type.value}, got {type(value).__name__}"

        return True, ""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_name(self, name: str) -> Tuple[str, int]:
        """Parse a versioned schema name into (base_name, version).

        Examples:
            "tick_v1" → ("tick", 1)
            "market_bar_v3" → ("market_bar", 3)
            "simple" → ("simple", 1)
        """
        if "_v" in name:
            parts = name.rsplit("_v", 1)
            try:
                return parts[0], int(parts[1])
            except (ValueError, IndexError):
                pass
        return name, 1

    def deprecate(self, base_name: str, version: Optional[int] = None) -> bool:
        """Deprecate a schema version.

        Args:
            base_name: Base schema name.
            version: Specific version (None = all versions).

        Returns:
            True if any schema was deprecated.
        """
        versions = self._schemas.get(base_name, [])
        deprecated = False

        for schema in versions:
            if version is None or schema.version == version:
                schema.is_deprecated = True
                deprecated = True

        return deprecated

    def get_compatibility_matrix(
        self, base_name: str
    ) -> List[Dict[str, Any]]:
        """Get compatibility matrix between all versions of a schema.

        Args:
            base_name: Base schema name.

        Returns:
            List of compatibility reports between consecutive versions.
        """
        versions = self.list_versions(base_name)
        matrix: List[Dict[str, Any]] = []

        for i in range(len(versions) - 1):
            old = versions[i]
            new = versions[i + 1]
            report = self.check_compatibility(old, new)
            matrix.append({
                "from_version": old.version,
                "to_version": new.version,
                "compatible": report.is_compatible,
                "changes": report.changes,
                "errors": report.errors,
            })

        return matrix
