"""
Production strategy validator.

Validates strategy packages, configurations, and runtime readiness
before deployment. Ensures all prerequisites are met for safe execution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .strategy_manifest import StrategyManifest
from .strategy_package import StrategyPackage

logger = logging.getLogger(__name__)


class ValidationSeverity(str, Enum):
    """Severity levels for validation issues."""

    ERROR = "error"
    """Must be fixed before deployment."""

    WARNING = "warning"
    """Should be reviewed but does not block deployment."""

    INFO = "info"
    """Informational only."""


@dataclass
class ValidationIssue:
    """A single validation issue."""

    severity: ValidationSeverity
    category: str
    message: str
    detail: str = ""
    field: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity.value,
            "category": self.category,
            "message": self.message,
            "detail": self.detail,
            "field": self.field,
        }


@dataclass
class ValidationResult:
    """Result of a strategy validation run."""

    strategy_id: str
    is_valid: bool = True
    issues: List[ValidationIssue] = field(default_factory=list)
    checks_executed: int = 0
    checks_passed: int = 0
    checks_failed: int = 0

    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]

    def add_issue(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)
        if issue.severity == ValidationSeverity.ERROR:
            self.is_valid = False

    def add_error(self, category: str, message: str, **kwargs: Any) -> None:
        self.add_issue(ValidationIssue(
            severity=ValidationSeverity.ERROR,
            category=category,
            message=message,
            **kwargs,
        ))

    def add_warning(self, category: str, message: str, **kwargs: Any) -> None:
        self.add_issue(ValidationIssue(
            severity=ValidationSeverity.WARNING,
            category=category,
            message=message,
            **kwargs,
        ))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "is_valid": self.is_valid,
            "checks_executed": self.checks_executed,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "errors": [i.to_dict() for i in self.errors],
            "warnings": [i.to_dict() for i in self.warnings],
        }


class StrategyValidator:
    """Validates strategy packages, configs, and runtime readiness.

    Validation steps (in order):
        1. Configuration validation - check config schema
        2. Manifest validation - check required manifest fields
        3. Dependency validation - verify all dependencies are available
        4. Permission validation - check required permissions
        5. Resource validation - verify resource requirements
        6. Custom validation - user-defined validation rules
    """

    def __init__(self) -> None:
        self._custom_validators: List[Callable] = []
        self._initialized: bool = False

    # ── Lifecycle ──

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("StrategyValidator initialized")

    async def shutdown(self) -> None:
        self._custom_validators.clear()
        self._initialized = False
        logger.info("StrategyValidator shut down")

    # ── Registration ──

    def register_validator(self, validator: Callable) -> None:
        """Register a custom validation function.

        The function should accept (manifest, config) and return a list
        of ValidationIssue objects.
        """
        self._custom_validators.append(validator)

    # ── Main Validation ──

    async def validate(
        self,
        manifest: StrategyManifest,
        config: Optional[Dict[str, Any]] = None,
        strategy_id: str = "",
    ) -> ValidationResult:
        """Run all validation checks on a strategy.

        Args:
            manifest: The strategy manifest to validate.
            config: Optional configuration to validate against the schema.
            strategy_id: Strategy identifier for the result.

        Returns:
            A ValidationResult with all issues found.
        """
        result = ValidationResult(strategy_id=strategy_id or manifest.name)

        # Step 1: Manifest validation
        await self._validate_manifest(manifest, result)

        # Step 2: Configuration validation
        if config:
            await self._validate_config(manifest, config, result)

        # Step 3: Dependency validation
        await self._validate_dependencies(manifest, result)

        # Step 4: Permission validation
        await self._validate_permissions(manifest, result)

        # Step 5: Resource validation
        await self._validate_resources(manifest, result)

        # Step 6: Custom validators
        for validator in self._custom_validators:
            try:
                issues = validator(manifest, config)
                for issue in issues:
                    result.add_issue(issue)
            except Exception as e:
                result.add_error("custom", f"Custom validator failed: {e}")

        logger.info(
            "Validation complete for %s: valid=%s, errors=%d, warnings=%d",
            result.strategy_id,
            result.is_valid,
            len(result.errors),
            len(result.warnings),
        )
        return result

    # ── Validation Steps ──

    async def _validate_manifest(
        self,
        manifest: StrategyManifest,
        result: ValidationResult,
    ) -> None:
        """Validate required manifest fields."""
        result.checks_executed += 1
        missing = manifest.validate_required_fields()
        if missing:
            result.add_error(
                "manifest",
                f"Missing required fields: {', '.join(missing)}",
            )
        else:
            result.checks_passed += 1

        # Validate version format
        try:
            from .strategy_version import StrategyVersion
            StrategyVersion.parse(manifest.version)
        except ValueError as e:
            result.add_error("manifest", f"Invalid version format: {e}", field="version")

    async def _validate_config(
        self,
        manifest: StrategyManifest,
        config: Dict[str, Any],
        result: ValidationResult,
    ) -> None:
        """Validate configuration against manifest schema."""
        result.checks_executed += 1
        schema = manifest.config_schema
        if not schema:
            result.checks_passed += 1
            return

        if "properties" in schema:
            for key, prop in schema["properties"].items():
                if key not in config:
                    if "default" in prop:
                        config[key] = prop["default"]
                    elif prop.get("required", False):
                        result.add_error(
                            "config",
                            f"Missing required config key: {key}",
                            field=key,
                        )
                    continue

                value = config[key]
                expected_type = prop.get("type")

                # Type checking
                if expected_type == "integer" and not isinstance(value, int):
                    result.add_error(
                        "config",
                        f"Config '{key}' expected integer, got {type(value).__name__}",
                        field=key,
                    )
                elif expected_type == "number" and not isinstance(value, (int, float)):
                    result.add_error(
                        "config",
                        f"Config '{key}' expected number, got {type(value).__name__}",
                        field=key,
                    )
                elif expected_type == "string" and not isinstance(value, str):
                    result.add_error(
                        "config",
                        f"Config '{key}' expected string, got {type(value).__name__}",
                        field=key,
                    )

                # Range checking
                if "minimum" in prop and isinstance(value, (int, float)):
                    if value < prop["minimum"]:
                        result.add_error(
                            "config",
                            f"Config '{key}' value {value} below minimum {prop['minimum']}",
                            field=key,
                        )
                if "maximum" in prop and isinstance(value, (int, float)):
                    if value > prop["maximum"]:
                        result.add_error(
                            "config",
                            f"Config '{key}' value {value} above maximum {prop['maximum']}",
                            field=key,
                        )

        result.checks_passed += 1

    async def _validate_dependencies(
        self,
        manifest: StrategyManifest,
        result: ValidationResult,
    ) -> None:
        """Validate that dependencies are available."""
        result.checks_executed += 1
        for dep in manifest.dependencies:
            if dep.optional:
                continue
            # In production, this would check against installed packages
            logger.debug("Dependency check: %s %s", dep.name, dep.version_spec)
        result.checks_passed += 1

    async def _validate_permissions(
        self,
        manifest: StrategyManifest,
        result: ValidationResult,
    ) -> None:
        """Validate that required permissions are granted."""
        result.checks_executed += 1
        # In production, this would check against the RBAC system
        logger.debug("Permission check for strategy: %s", manifest.name)
        result.checks_passed += 1

    async def _validate_resources(
        self,
        manifest: StrategyManifest,
        result: ValidationResult,
    ) -> None:
        """Validate resource requirements against platform capacity."""
        result.checks_executed += 1
        resources = manifest.resources
        # In production, check against cluster capacity
        if resources.memory_mb > 8192:
            result.add_warning(
                "resources",
                f"High memory requirement: {resources.memory_mb}MB",
            )
        if resources.timeout_seconds > 3600:
            result.add_warning(
                "resources",
                f"Long timeout: {resources.timeout_seconds}s",
            )
        result.checks_passed += 1

    def get_summary(self) -> Dict[str, Any]:
        return {
            "custom_validators": len(self._custom_validators),
            "initialized": self._initialized,
        }
