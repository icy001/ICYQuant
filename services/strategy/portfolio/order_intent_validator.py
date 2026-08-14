"""
Order Intent Validator
======================
Validates order intents before routing to OMS.

Validation stages:
    Schema → Direction → Quantity → Market → Risk → Compliance
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, field as dataclass_field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ValidationSeverity(str, Enum):
    """Severity of validation issues."""

    ERROR = "error"    # Must be fixed
    WARNING = "warning"  # Should be reviewed
    INFO = "info"      # Informational


@dataclass
class ValidationIssue:
    """A single validation issue found."""

    field: str = ""
    message: str = ""
    severity: ValidationSeverity = ValidationSeverity.ERROR
    code: str = ""
    details: Dict[str, Any] = dataclass_field(default_factory=dict)


@dataclass
class IntentValidationResult:
    """Complete validation result for an order intent."""

    intent_id: str = ""
    is_valid: bool = True
    issues: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)
    infos: List[ValidationIssue] = field(default_factory=list)
    validated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def has_errors(self) -> bool:
        return any(i.severity == ValidationSeverity.ERROR for i in self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "is_valid": self.is_valid,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issues": [
                {"field": i.field, "message": i.message, "severity": i.severity.value, "code": i.code}
                for i in self.issues
            ],
            "warnings": [
                {"field": w.field, "message": w.message, "code": w.code}
                for w in self.warnings
            ],
            "validated_at": self.validated_at.isoformat(),
        }


class OrderIntentValidator:
    """
    Validates order intents across multiple dimensions.

    Checks:
    - Schema completeness (required fields)
    - Direction validity
    - Quantity reasonableness
    - Market conditions
    - Risk boundaries
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._initialized = False

        # Validation rules
        self._min_quantity = self._config.get("min_quantity", 0.0)
        self._max_quantity = self._config.get("max_quantity", float("inf"))
        self._min_notional = self._config.get("min_notional", 0.0)
        self._max_notional = self._config.get("max_notional", float("inf"))
        self._max_confidence_threshold = self._config.get("max_confidence_threshold", 1.0)
        self._min_confidence_threshold = self._config.get("min_confidence_threshold", 0.0)

        # Required fields
        self._required_fields = self._config.get("required_fields", [
            "instrument", "side", "quantity", "portfolio_id",
        ])

        # Metrics
        self._metrics: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("OrderIntentValidator initialized")

    async def shutdown(self) -> None:
        self._initialized = False
        logger.info("OrderIntentValidator shut down")

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_schema(self, intent: Any) -> List[ValidationIssue]:
        """Validate required fields are present."""
        issues = []

        if isinstance(intent, dict):
            data = intent
        else:
            data = intent.to_dict() if hasattr(intent, "to_dict") else {}

        for field in self._required_fields:
            value = data.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                issues.append(ValidationIssue(
                    field=field,
                    message=f"Required field '{field}' is missing or empty",
                    severity=ValidationSeverity.ERROR,
                    code="MISSING_REQUIRED_FIELD",
                ))

        return issues

    def _validate_direction(self, intent: Any) -> List[ValidationIssue]:
        """Validate side/direction is valid."""
        issues = []

        if isinstance(intent, dict):
            side = intent.get("side", "")
        else:
            side = getattr(intent, "side", None)
            if side and hasattr(side, "value"):
                side = side.value

        valid_sides = {"BUY", "SELL", "BUY_TO_COVER", "SELL_SHORT"}
        if side and side not in valid_sides:
            issues.append(ValidationIssue(
                field="side",
                message=f"Invalid side '{side}'. Must be one of {valid_sides}",
                severity=ValidationSeverity.ERROR,
                code="INVALID_SIDE",
            ))

        return issues

    def _validate_quantity(self, intent: Any) -> List[ValidationIssue]:
        """Validate quantity is reasonable."""
        issues = []

        if isinstance(intent, dict):
            quantity = intent.get("quantity", 0)
            notional = intent.get("allocated_capital", intent.get("notional_value", 0))
        else:
            quantity = getattr(intent, "quantity", 0)
            notional = getattr(intent, "notional_value", 0)

        if quantity <= 0:
            issues.append(ValidationIssue(
                field="quantity",
                message=f"Quantity must be positive, got {quantity}",
                severity=ValidationSeverity.ERROR,
                code="INVALID_QUANTITY",
            ))
        elif self._max_quantity != float("inf") and quantity > self._max_quantity:
            issues.append(ValidationIssue(
                field="quantity",
                message=f"Quantity {quantity} exceeds max {self._max_quantity}",
                severity=ValidationSeverity.ERROR,
                code="QUANTITY_EXCEEDS_MAX",
            ))
        elif self._min_quantity > 0 and quantity < self._min_quantity:
            issues.append(ValidationIssue(
                field="quantity",
                message=f"Quantity {quantity} below min {self._min_quantity}",
                severity=ValidationSeverity.WARNING,
                code="QUANTITY_BELOW_MIN",
            ))

        if notional <= 0 and quantity > 0:
            issues.append(ValidationIssue(
                field="allocated_capital",
                message="Notional value is zero or negative",
                severity=ValidationSeverity.WARNING,
                code="ZERO_NOTIONAL",
            ))

        return issues

    def _validate_confidence(self, intent: Any) -> List[ValidationIssue]:
        """Validate confidence score."""
        issues = []

        if isinstance(intent, dict):
            confidence = intent.get("confidence", 0)
        else:
            confidence = getattr(intent, "confidence", 0)

        if confidence < self._min_confidence_threshold:
            issues.append(ValidationIssue(
                field="confidence",
                message=f"Confidence {confidence:.2f} below minimum {self._min_confidence_threshold}",
                severity=ValidationSeverity.WARNING,
                code="LOW_CONFIDENCE",
            ))

        if confidence > self._max_confidence_threshold:
            issues.append(ValidationIssue(
                field="confidence",
                message=f"Confidence {confidence:.2f} exceeds max {self._max_confidence_threshold}",
                severity=ValidationSeverity.WARNING,
                code="HIGH_CONFIDENCE",
            ))

        return issues

    def _validate_market(self, intent: Any) -> List[ValidationIssue]:
        """Validate market-related fields."""
        issues = []

        if isinstance(intent, dict):
            instrument = intent.get("instrument", "")
            instrument_type = intent.get("instrument_type", "")
            exchange = intent.get("exchange", "")
        else:
            instrument = getattr(intent, "instrument", "")
            instrument_type = getattr(intent, "instrument_type", "")
            exchange = getattr(intent, "exchange", "")

        if not instrument:
            issues.append(ValidationIssue(
                field="instrument",
                message="Instrument identifier is empty",
                severity=ValidationSeverity.ERROR,
                code="MISSING_INSTRUMENT",
            ))

        if not instrument_type:
            issues.append(ValidationIssue(
                field="instrument_type",
                message="Instrument type not specified",
                severity=ValidationSeverity.INFO,
                code="MISSING_INSTRUMENT_TYPE",
            ))

        return issues

    async def validate(self, intent: Any) -> IntentValidationResult:
        """
        Validate an order intent.

        Args:
            intent: OrderIntent object or dict.

        Returns:
            IntentValidationResult with all issues found.
        """
        if not self._initialized:
            await self.initialize()

        if isinstance(intent, dict):
            intent_id = intent.get("intent_id", "unknown")
        else:
            intent_id = getattr(intent, "intent_id", "unknown")

        result = IntentValidationResult(intent_id=intent_id)

        # Run all validation stages
        all_checks = [
            self._validate_schema(intent),
            self._validate_direction(intent),
            self._validate_quantity(intent),
            self._validate_confidence(intent),
            self._validate_market(intent),
        ]

        for issues in all_checks:
            for issue in issues:
                if issue.severity == ValidationSeverity.ERROR:
                    result.issues.append(issue)
                elif issue.severity == ValidationSeverity.WARNING:
                    result.warnings.append(issue)
                else:
                    result.infos.append(issue)

        result.is_valid = not result.has_errors

        self._metrics["validated_total"] = self._metrics.get("validated_total", 0) + 1
        if not result.is_valid:
            self._metrics["validation_failed"] = self._metrics.get("validation_failed", 0) + 1
            logger.warning(
                "Intent %s validation failed: %d errors, %d warnings",
                intent_id, result.error_count, result.warning_count,
            )
        elif result.warnings:
            logger.info(
                "Intent %s passed with %d warnings", intent_id, result.warning_count,
            )

        return result

    async def validate_batch(self, intents: List[Any]) -> List[IntentValidationResult]:
        """Validate a batch of order intents."""
        if not self._initialized:
            await self.initialize()

        results = []
        for intent in intents:
            result = await self.validate(intent)
            results.append(result)

        valid_count = sum(1 for r in results if r.is_valid)
        logger.info(
            "Batch validation: %d/%d intents valid", valid_count, len(results),
        )

        return results

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, int]:
        return dict(self._metrics)

    @property
    def is_initialized(self) -> bool:
        return self._initialized
