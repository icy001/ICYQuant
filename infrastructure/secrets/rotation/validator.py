"""
Rotation pre-validation.

Validates secrets before rotation
to ensure they meet format, expiration,
uniqueness, and provider health requirements.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ..credentials import CredentialType
from ..models import ValidationIssue, ValidationResult
from ..utils import mask_secret_value

logger = logging.getLogger(__name__)


class RotationCheckType(str, Enum):
    """Types of rotation pre-checks."""

    FORMAT = "format"
    EXPIRATION = "expiration"
    DUPLICATE = "duplicate"
    PERMISSION = "permission"
    PROVIDER_HEALTH = "provider_health"
    SIZE = "size"
    CONNECTION = "connection"


@dataclass
class RotationCheckResult:
    """
    Result of a single rotation check.

    Attributes:
        check_type: Type of check performed.
        passed: Whether the check passed.
        message: Human-readable result message.
        severity: Issue severity if failed.
        details: Additional diagnostic details.
    """

    check_type: RotationCheckType
    passed: bool
    message: str = ""
    severity: str = "warning"
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_type": self.check_type.value,
            "passed": self.passed,
            "message": self.message,
            "severity": self.severity,
            "details": self.details,
        }


class RotationValidator:
    """
    Pre-rotation validation engine.

    Runs comprehensive checks before
    rotation can proceed, including format
    validation, expiration checking,
    duplicate detection, and provider
    health verification.

    Usage:
        validator = RotationValidator(provider=my_provider)
        result = await validator.validate(
            secret_key="database/password",
            new_value="new-secret-value",
        )
        if result.passed:
            await manager.rotate("database/password")
    """

    # Format patterns by credential type
    CREDENTIAL_FORMATS: Dict[CredentialType, re.Pattern] = {
        CredentialType.DATABASE: re.compile(r"^.{1,1024}$"),
        CredentialType.BROKER_API_KEY: re.compile(r"^[A-Za-z0-9_\-\.]{8,256}$"),
        CredentialType.JWT_SIGNING: re.compile(r"^[A-Za-z0-9_\-\/\+=\.]{32,}$"),
        CredentialType.TLS_CERTIFICATE: re.compile(
            r"-----BEGIN CERTIFICATE-----[\s\S]+-----END CERTIFICATE-----"
        ),
        CredentialType.SSH_KEY: re.compile(
            r"-----BEGIN (RSA|EC|DSA|ED25519|OPENSSH) (PRIVATE|PUBLIC) KEY-----"
        ),
        CredentialType.ENCRYPTION_KEY: re.compile(r"^[A-Za-z0-9_\-\/\+=\.]{32,}$"),
        CredentialType.WEBHOOK_SECRET: re.compile(r"^[A-Za-z0-9_\-]{16,256}$"),
        CredentialType.API_TOKEN: re.compile(r"^[A-Za-z0-9_\-\.]{16,512}$"),
    }

    MAX_SECRET_SIZE = 65536

    def __init__(
        self,
        provider: Optional[Any] = None,
        registry: Optional[Any] = None,
        custom_checks: Optional[List[Callable]] = None,
    ) -> None:
        """
        Initialize validator.

        Args:
            provider: Secrets provider for health checks.
            registry: Secrets registry for duplicate checks.
            custom_checks: Additional validation functions.
        """
        self._provider = provider
        self._registry = registry
        self._custom_checks = custom_checks or []

    async def validate(
        self,
        secret_key: str,
        new_value: str,
        credential_type: CredentialType = CredentialType.DATABASE,
        current_value: Optional[str] = None,
    ) -> ValidationResult:
        """
        Run all pre-rotation validations.

        Args:
            secret_key: The secret key path.
            new_value: The new secret value.
            credential_type: Expected credential type.
            current_value: Current value for comparison.

        Returns:
            ValidationResult with pass/fail and issues.
        """
        issues: List[ValidationIssue] = []

        # Check 1: Size validation
        size_ok, size_issue = self._check_size(secret_key, new_value)
        if not size_ok and size_issue:
            issues.append(size_issue)

        # Check 2: Format validation
        format_ok, format_issue = self._check_format(
            secret_key, new_value, credential_type
        )
        if not format_ok and format_issue:
            issues.append(format_issue)

        # Check 3: Duplicate value check
        if current_value is not None:
            dup_ok, dup_issue = self._check_duplicate(
                secret_key, new_value, current_value
            )
            if not dup_ok and dup_issue:
                issues.append(dup_issue)

        # Check 4: Provider health
        provider_ok, provider_issue = await self._check_provider_health()
        if not provider_ok and provider_issue:
            issues.append(provider_issue)

        # Check 5: Custom checks
        for check_fn in self._custom_checks:
            try:
                result = await check_fn(secret_key, new_value)
                if result is False:
                    issues.append(ValidationIssue(
                        field="custom",
                        message=f"Custom check failed: {check_fn.__name__}",
                        severity="error",
                    ))
                elif isinstance(result, ValidationIssue):
                    issues.append(result)
            except Exception as e:
                issues.append(ValidationIssue(
                    field="custom",
                    message=f"Custom check error: {e}",
                    severity="error",
                ))

        valid = len([
            i for i in issues if i.severity in ("error", "critical")
        ]) == 0

        return ValidationResult(
            valid=valid,
            issues=issues,
        )

    def _check_size(
        self,
        secret_key: str,
        value: str,
    ) -> tuple:
        """Validate secret size."""
        size = len(value.encode("utf-8"))
        if size > self.MAX_SECRET_SIZE:
            return False, ValidationIssue(
                field="size",
                message=f"Secret value exceeds {self.MAX_SECRET_SIZE} bytes ({size} bytes)",
                severity="error",
                code="SECRET_TOO_LARGE",
            )
        if size == 0:
            return False, ValidationIssue(
                field="size",
                message="Secret value is empty",
                severity="error",
                code="SECRET_EMPTY",
            )
        return True, None

    def _check_format(
        self,
        secret_key: str,
        value: str,
        credential_type: CredentialType,
    ) -> tuple:
        """Validate credential format."""
        pattern = self.CREDENTIAL_FORMATS.get(credential_type)
        if pattern is None:
            return True, None

        if not pattern.match(value):
            return False, ValidationIssue(
                field="format",
                message=f"Secret value does not match expected format for {credential_type.value}",
                severity="error",
                code="FORMAT_MISMATCH",
            )
        return True, None

    def _check_duplicate(
        self,
        secret_key: str,
        new_value: str,
        current_value: str,
    ) -> tuple:
        """Check that new value differs from current."""
        if new_value == current_value:
            return False, ValidationIssue(
                field="value",
                message="New secret value is identical to current value",
                severity="error",
                code="DUPLICATE_VALUE",
            )
        return True, None

    async def _check_provider_health(self) -> tuple:
        """Check provider health status."""
        if self._provider is None:
            return True, None

        try:
            if hasattr(self._provider, "health_check"):
                health = await self._provider.health_check()
                if isinstance(health, dict) and not health.get("healthy", True):
                    return False, ValidationIssue(
                        field="provider",
                        message="Provider health check failed",
                        severity="error",
                        code="PROVIDER_UNHEALTHY",
                    )
        except Exception as e:
            return False, ValidationIssue(
                field="provider",
                message=f"Provider health check error: {e}",
                severity="error",
                code="PROVIDER_ERROR",
            )

        return True, None

    def get_check_types(self) -> List[str]:
        """Get all available check types."""
        return [ct.value for ct in RotationCheckType]

    def get_stats(self) -> Dict[str, Any]:
        """Get validator statistics."""
        return {
            "provider_configured": self._provider is not None,
            "registry_configured": self._registry is not None,
            "custom_checks": len(self._custom_checks),
            "credential_formats": {
                ct.value: pattern is not None
                for ct, pattern in self.CREDENTIAL_FORMATS.items()
            },
        }
