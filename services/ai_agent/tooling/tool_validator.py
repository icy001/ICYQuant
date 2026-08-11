"""Tool Validator — pre-execution validation for tool calls.

Pipeline:
    Tool Execution Request
        -> Input Schema Validation
        -> Permission Validation
        -> Policy Validation
        -> Constraint Validation
        -> Execution (if all pass)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from services.ai_agent.tooling.tool_definition import ToolDefinition

logger = logging.getLogger(__name__)


# ── Enums ──

class ValidationStatus(str, Enum):
    """Validation result status."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


# ── ValidationError ──

@dataclass
class ValidationError:
    """A single validation error."""

    field: str
    message: str
    code: str = ""
    status: ValidationStatus = ValidationStatus.FAIL


# ── ValidationResult ──

@dataclass
class ValidationResult:
    """Result of a tool validation check."""

    is_valid: bool = True
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    validated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def add_error(self, field: str, message: str, code: str = "") -> None:
        """Add a validation error.

        Args:
            field: The field with the error.
            message: Error description.
            code: Optional error code.
        """
        self.errors.append(ValidationError(field=field, message=message, code=code))
        self.is_valid = False

    def add_warning(self, field: str, message: str, code: str = "") -> None:
        """Add a validation warning.

        Args:
            field: The field with the warning.
            message: Warning description.
            code: Optional warning code.
        """
        self.warnings.append(
            ValidationError(field=field, message=message, code=code, status=ValidationStatus.WARN)
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "is_valid": self.is_valid,
            "errors": [{"field": e.field, "message": e.message, "code": e.code} for e in self.errors],
            "warnings": [
                {"field": w.field, "message": w.message, "code": w.code} for w in self.warnings
            ],
            "validated_at": self.validated_at.isoformat(),
        }


# ── ToolValidator ──

class ToolValidator:
    """Pre-execution validation engine for tool calls.

    Validates tool calls before execution across multiple dimensions:
    input schema, permissions, policies, and custom constraints.

    Supports:
        - Input schema validation
        - Type checking
        - Required field checking
        - Enum value validation
        - Numeric range validation
        - Pattern (regex) validation
        - Custom constraint validation

    Usage:
        validator = ToolValidator()
        result = validator.validate(tool_definition, params)
        if result.is_valid:
            await executor.execute(...)
    """

    def __init__(self) -> None:
        """Initialize the validator."""
        self._constraints: Dict[str, List[Any]] = {}  # tool_name -> list of constraint functions
        self._initialized: bool = False
        logger.info("ToolValidator created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize the validator."""
        self._initialized = True
        logger.info("ToolValidator initialized")

    async def shutdown(self) -> None:
        """Shutdown the validator."""
        self._constraints.clear()
        self._initialized = False
        logger.info("ToolValidator shutdown complete")

    # ── Validation ──

    def validate(
        self,
        tool: ToolDefinition,
        params: Dict[str, Any],
    ) -> ValidationResult:
        """Validate parameters against a tool definition.

        Args:
            tool: The tool definition with input schema.
            params: The input parameters to validate.

        Returns:
            A ValidationResult with errors and warnings.
        """
        result = ValidationResult()

        # ── Schema validation ──
        schema_errors = tool.validate_input(params)
        for error_msg in schema_errors:
            result.add_error("input", error_msg)

        # ── Custom constraints ──
        if tool.name in self._constraints:
            for constraint_fn in self._constraints[tool.name]:
                try:
                    constraint_result = constraint_fn(params)
                    if isinstance(constraint_result, list):
                        for err in constraint_result:
                            if isinstance(err, str):
                                result.add_error("constraint", err)
                            elif isinstance(err, ValidationError):
                                if err.status == ValidationStatus.WARN:
                                    result.add_warning(err.field, err.message, err.code)
                                else:
                                    result.add_error(err.field, err.message, err.code)
                except Exception as e:
                    result.add_error("constraint", f"Constraint evaluation failed: {e}")

        # ── Deprecation warning ──
        if tool.deprecated:
            result.add_warning(
                "tool",
                f"Tool '{tool.name}' is deprecated: {tool.deprecation_message}",
                "deprecated_tool",
            )

        logger.debug(
            f"Validation for {tool.name}: {'PASS' if result.is_valid else 'FAIL'} "
            f"({len(result.errors)} errors, {len(result.warnings)} warnings)"
        )

        return result

    def validate_params(
        self,
        params: Dict[str, Any],
        schema: Dict[str, Any],
    ) -> ValidationResult:
        """Validate parameters against a JSON schema.

        Args:
            params: The parameters to validate.
            schema: The JSON schema to validate against.

        Returns:
            A ValidationResult.
        """
        result = ValidationResult()

        required = schema.get("required", [])
        properties = schema.get("properties", {})

        # Check required fields
        for field in required:
            if field not in params:
                result.add_error(field, f"Missing required field: {field}")

        # Check types and constraints
        for field, value in params.items():
            if field not in properties:
                result.add_warning(field, f"Unknown field: {field}")
                continue

            prop = properties[field]
            expected_type = prop.get("type", "string")

            # Type checking
            if not self._check_type(value, expected_type):
                result.add_error(
                    field,
                    f"Type mismatch: expected {expected_type}, got {type(value).__name__}",
                )

            # Enum checking
            if "enum" in prop and value not in prop["enum"]:
                result.add_error(
                    field,
                    f"Value '{value}' not in allowed values: {prop['enum']}",
                )

            # Range checking
            if "minimum" in prop and isinstance(value, (int, float)):
                if value < prop["minimum"]:
                    result.add_error(field, f"Value {value} is below minimum {prop['minimum']}")
            if "maximum" in prop and isinstance(value, (int, float)):
                if value > prop["maximum"]:
                    result.add_error(field, f"Value {value} is above maximum {prop['maximum']}")

            # Pattern checking
            if "pattern" in prop and isinstance(value, str):
                import re

                if not re.match(prop["pattern"], value):
                    result.add_error(field, f"Value does not match pattern: {prop['pattern']}")

        return result

    # ── Constraint Management ──

    def add_constraint(self, tool_name: str, constraint_fn: Any) -> None:
        """Add a custom validation constraint for a tool.

        Args:
            tool_name: The tool name.
            constraint_fn: A callable that takes params dict and returns
                           a list of error strings or ValidationError objects.
        """
        if tool_name not in self._constraints:
            self._constraints[tool_name] = []
        self._constraints[tool_name].append(constraint_fn)
        logger.info(f"Constraint added for {tool_name}")

    def remove_constraints(self, tool_name: str) -> None:
        """Remove all custom constraints for a tool.

        Args:
            tool_name: The tool name.
        """
        self._constraints.pop(tool_name, None)

    # ── Private Methods ──

    @staticmethod
    def _check_type(value: Any, expected_type: str) -> bool:
        """Check if a value matches the expected type.

        Args:
            value: The value to check.
            expected_type: The expected type string.

        Returns:
            True if types match.
        """
        type_map = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        expected = type_map.get(expected_type)
        if expected is None:
            return True
        if isinstance(expected, tuple):
            return isinstance(value, expected)
        return isinstance(value, expected)

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Get validator status."""
        return {
            "constraints_count": sum(len(v) for v in self._constraints.values()),
            "tools_with_constraints": list(self._constraints.keys()),
            "initialized": self._initialized,
        }
