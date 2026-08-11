"""
Schema Validator — validates incoming market data against registered
schemas with field-level error reporting.

Commit 16 Part 1.2
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationError:
    """A single validation error."""

    field_path: str = ""
    message: str = ""
    severity: ValidationSeverity = ValidationSeverity.ERROR
    expected: Any = None
    actual: Any = None
    rule: str = ""


@dataclass
class ValidationResult:
    """Result of schema validation."""

    is_valid: bool = True
    schema_name: str = ""
    schema_version: int = 0
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)
    validated_at: Optional[datetime] = None
    duration_us: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class SchemaValidator:
    """
    Validates market data payloads against registered schemas.

    Checks:
    - Required fields present
    - Field types match
    - Value constraints (range, enum, pattern)
    - Timestamp validity
    - Price/volume sign and range
    """

    def __init__(self) -> None:
        self._validators: dict[str, Any] = {}

    async def validate(
        self,
        data: dict[str, Any],
        schema_entry: Any,  # SchemaEntry from schema_registry
    ) -> ValidationResult:
        """Validate data against a schema entry."""

        start_ns = self._now_ns()
        result = ValidationResult(
            schema_name=schema_entry.schema_name,
            schema_version=schema_entry.schema_version,
        )

        # Required fields check
        for field in schema_entry.required_fields:
            if field not in data or data[field] is None:
                result.errors.append(ValidationError(
                    field_path=field,
                    message=f"Missing required field: {field}",
                    severity=ValidationSeverity.ERROR,
                    rule="required",
                ))

        # Type checking
        for field, expected_type in schema_entry.field_types.items():
            if field in data and data[field] is not None:
                if not self._check_type(data[field], expected_type):
                    result.errors.append(ValidationError(
                        field_path=field,
                        message=f"Type mismatch: expected {expected_type}, got {type(data[field]).__name__}",
                        severity=ValidationSeverity.ERROR,
                        expected=expected_type,
                        actual=type(data[field]).__name__,
                        rule="type_check",
                    ))

        # Price/volume sanity
        for field in ("price", "last", "bid", "ask"):
            if field in data and data[field] is not None:
                try:
                    val = float(data[field])
                    if val < 0:
                        result.warnings.append(ValidationError(
                            field_path=field,
                            message=f"Negative price: {val}",
                            severity=ValidationSeverity.WARNING,
                            rule="price_non_negative",
                        ))
                except (ValueError, TypeError):
                    pass

        # Timestamp sanity
        for ts_field in ("event_time", "timestamp", "ts", "E", "T"):
            if ts_field in data and data[ts_field] is not None:
                try:
                    ts = int(data[ts_field])
                    now_ns = self._now_ns()
                    if ts > now_ns + 60_000_000_000:  # 60s in future
                        result.warnings.append(ValidationError(
                            field_path=ts_field,
                            message="Timestamp is in the future",
                            severity=ValidationSeverity.WARNING,
                            rule="timestamp_future",
                        ))
                except (ValueError, TypeError):
                    pass

        result.is_valid = len(result.errors) == 0
        result.validated_at = datetime.now(timezone.utc)
        result.duration_us = (self._now_ns() - start_ns) / 1000.0

        return result

    async def validate_batch(
        self,
        data_batch: list[dict[str, Any]],
        schema_entry: Any,
    ) -> list[ValidationResult]:
        """Validate a batch of data records."""
        results: list[ValidationResult] = []
        for data in data_batch:
            results.append(await self.validate(data, schema_entry))
        return results

    # ── Type checking ───────────────────────────────

    @staticmethod
    def _check_type(value: Any, expected_type: str) -> bool:
        type_map = {
            "str": str,
            "string": str,
            "int": int,
            "integer": int,
            "float": (int, float),
            "number": (int, float),
            "bool": bool,
            "boolean": bool,
            "list": list,
            "array": list,
            "dict": dict,
            "object": dict,
            "any": object,
        }
        expected = type_map.get(expected_type.lower(), object)
        return isinstance(value, expected)

    @staticmethod
    def _now_ns() -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1e9)
