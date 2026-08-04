"""
Secrets validator.

Provides validation for secret items,
including format validation, size checks,
expiration checks, and integrity verification.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .constants import SecretFormat, ValidationSeverity
from .models import SecretItem, ValidationIssue, ValidationResult

logger = logging.getLogger(__name__)


class SecretValidator:
    """
    Secret validator.

    Validates secret items for format, size,
    expiration, integrity, and policy compliance.

    Usage:
        validator = SecretValidator()
        result = validator.validate(secret_item)
        if not result.valid:
            for issue in result.issues:
                print(issue.message)
    """

    def __init__(self) -> None:
        self._max_size: int = 65536
        self._allow_empty: bool = False
        self._check_expiration: bool = True
        self._check_integrity: bool = True
        self._check_format: bool = True
        self._custom_validators: List[Callable] = []

    # ── Configuration ──

    def set_max_size(self, size: int) -> None:
        """Set maximum secret size in bytes."""
        self._max_size = size

    def set_allow_empty(self, allowed: bool) -> None:
        """Set whether empty values are allowed."""
        self._allow_empty = allowed

    def set_check_expiration(self, enabled: bool) -> None:
        """Enable/disable expiration check."""
        self._check_expiration = enabled

    def set_check_integrity(self, enabled: bool) -> None:
        """Enable/disable integrity check."""
        self._check_integrity = enabled

    def set_check_format(self, enabled: bool) -> None:
        """Enable/disable format check."""
        self._check_format = enabled

    def add_validator(self, validator: Callable) -> None:
        """
        Add a custom validator function.

        Args:
            validator: Callable(SecretItem) -> List[ValidationIssue]
        """
        self._custom_validators.append(validator)

    # ── Validation ──

    def validate(
        self,
        item: SecretItem,
    ) -> ValidationResult:
        """
        Validate a secret item.

        Args:
            item: The secret item to validate.

        Returns:
            ValidationResult with issues.
        """
        issues: List[ValidationIssue] = []

        # Check key
        issues.extend(self._validate_key(item))

        # Check value
        issues.extend(self._validate_value(item))

        # Check size
        issues.extend(self._validate_size(item))

        # Check format
        if self._check_format:
            issues.extend(self._validate_format(item))

        # Check expiration
        if self._check_expiration:
            issues.extend(self._validate_expiration(item))

        # Check integrity
        if self._check_integrity:
            issues.extend(self._validate_integrity(item))

        # Run custom validators
        for validator in self._custom_validators:
            try:
                custom_issues = validator(item)
                if custom_issues:
                    issues.extend(custom_issues)
            except Exception as e:
                issues.append(
                    ValidationIssue(
                        field="custom_validator",
                        message=f"Custom validator error: {e}",
                        severity=ValidationSeverity.WARNING,
                        code="CUSTOM_ERROR",
                    )
                )

        # Determine validity
        has_errors = any(
            i.severity == ValidationSeverity.ERROR or i.severity == ValidationSeverity.CRITICAL
            for i in issues
        )

        return ValidationResult(
            valid=not has_errors,
            issues=issues,
        )

    def validate_batch(
        self,
        items: List[SecretItem],
    ) -> Dict[str, ValidationResult]:
        """
        Validate multiple secret items.

        Args:
            items: List of secret items.

        Returns:
            Dict mapping key to ValidationResult.
        """
        return {item.key: self.validate(item) for item in items}

    # ── Individual Checks ──

    def _validate_key(
        self,
        item: SecretItem,
    ) -> List[ValidationIssue]:
        """Validate the secret key."""
        issues = []

        if not item.key:
            issues.append(
                ValidationIssue(
                    field="key",
                    message="Secret key cannot be empty",
                    severity=ValidationSeverity.ERROR,
                    code="EMPTY_KEY",
                )
            )
        elif len(item.key) > 255:
            issues.append(
                ValidationIssue(
                    field="key",
                    message=f"Secret key too long ({len(item.key)} > 255)",
                    severity=ValidationSeverity.ERROR,
                    code="KEY_TOO_LONG",
                )
            )
        elif not re.match(r"^[a-zA-Z0-9_\-/]+$", item.key):
            issues.append(
                ValidationIssue(
                    field="key",
                    message=f"Invalid key format: {item.key}",
                    severity=ValidationSeverity.ERROR,
                    code="INVALID_KEY_FORMAT",
                )
            )

        return issues

    def _validate_value(
        self,
        item: SecretItem,
    ) -> List[ValidationIssue]:
        """Validate the secret value."""
        issues = []

        if not item.value and not self._allow_empty:
            issues.append(
                ValidationIssue(
                    field="value",
                    message="Secret value cannot be empty",
                    severity=ValidationSeverity.ERROR,
                    code="EMPTY_VALUE",
                )
            )

        return issues

    def _validate_size(
        self,
        item: SecretItem,
    ) -> List[ValidationIssue]:
        """Validate secret size."""
        issues = []
        size = len(item.value) if item.value else 0

        if size > self._max_size:
            issues.append(
                ValidationIssue(
                    field="value",
                    message=f"Secret value exceeds max size ({size} > {self._max_size})",
                    severity=ValidationSeverity.ERROR,
                    code="SIZE_EXCEEDED",
                )
            )

        return issues

    def _validate_format(
        self,
        item: SecretItem,
    ) -> List[ValidationIssue]:
        """Validate secret value format."""
        issues = []

        fmt = item.format
        value = item.value

        if not value:
            return issues

        try:
            if fmt == SecretFormat.JSON:
                json.loads(value)
            elif fmt == SecretFormat.BASE64:
                import base64
                base64.b64decode(value, validate=True)
            elif fmt == SecretFormat.PEM:
                if "-----BEGIN" not in value:
                    issues.append(
                        ValidationIssue(
                            field="value",
                            message="PEM format must contain -----BEGIN marker",
                            severity=ValidationSeverity.WARNING,
                            code="INVALID_PEM",
                        )
                    )
        except json.JSONDecodeError:
            issues.append(
                ValidationIssue(
                    field="value",
                    message="Invalid JSON format",
                    severity=ValidationSeverity.ERROR,
                    code="INVALID_JSON",
                )
            )
        except Exception as e:
            issues.append(
                ValidationIssue(
                    field="value",
                    message=f"Format validation failed: {e}",
                    severity=ValidationSeverity.WARNING,
                    code="FORMAT_ERROR",
                )
            )

        return issues

    def _validate_expiration(
        self,
        item: SecretItem,
    ) -> List[ValidationIssue]:
        """Validate secret expiration."""
        issues = []

        if item.expires_at and datetime.utcnow() > item.expires_at:
            issues.append(
                ValidationIssue(
                    field="expires_at",
                    message="Secret has expired",
                    severity=ValidationSeverity.ERROR,
                    code="EXPIRED",
                )
            )

        return issues

    def _validate_integrity(
        self,
        item: SecretItem,
    ) -> List[ValidationIssue]:
        """Validate secret integrity via checksum."""
        issues = []

        if item.checksum:
            from .utils import compute_checksum
            expected = compute_checksum(item.value)
            if item.checksum != expected:
                issues.append(
                    ValidationIssue(
                        field="checksum",
                        message="Checksum mismatch - secret may be corrupted",
                        severity=ValidationSeverity.CRITICAL,
                        code="CHECKSUM_MISMATCH",
                    )
                )

        return issues

    def get_stats(self) -> Dict[str, Any]:
        """Get validator statistics."""
        return {
            "max_size": self._max_size,
            "allow_empty": self._allow_empty,
            "check_expiration": self._check_expiration,
            "check_integrity": self._check_integrity,
            "check_format": self._check_format,
            "custom_validators": len(self._custom_validators),
        }
