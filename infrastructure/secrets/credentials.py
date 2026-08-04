"""
Credential type definitions.

Defines credential categories and
metadata for the rotation subsystem,
covering database credentials,
broker API keys, certificates,
JWT secrets, and SSH keys.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class CredentialType(str, Enum):
    """Credential type classification."""

    DATABASE = "database"
    BROKER_API_KEY = "broker_api_key"
    EXCHANGE_SECRET = "exchange_secret"
    JWT_SIGNING = "jwt_signing"
    TLS_CERTIFICATE = "tls_certificate"
    SSH_KEY = "ssh_key"
    ENCRYPTION_KEY = "encryption_key"
    WEBHOOK_SECRET = "webhook_secret"
    API_TOKEN = "api_token"


class RotationStrategy(str, Enum):
    """Rotation execution strategy."""

    AUTOMATIC = "automatic"
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    EMERGENCY = "emergency"


class ApprovalMode(str, Enum):
    """Approval mode for rotation."""

    NONE = "none"
    SINGLE = "single"
    DUAL = "dual"
    EMERGENCY = "emergency"


@dataclass
class CredentialMetadata:
    """
    Metadata about a credential.

    Provides classification and context
    for credential rotation and management.

    Attributes:
        credential_type: Classification type.
        service: Service that uses the credential.
        owner: Team/owner responsible.
        environment: Deployment environment.
        risk_level: Assessed risk level (0-5).
        compliance_tags: Compliance framework tags.
    """

    credential_type: CredentialType = CredentialType.DATABASE
    service: str = ""
    owner: str = ""
    environment: str = "production"
    risk_level: int = 3
    compliance_tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "credential_type": self.credential_type.value,
            "service": self.service,
            "owner": self.owner,
            "environment": self.environment,
            "risk_level": self.risk_level,
            "compliance_tags": self.compliance_tags,
        }


@dataclass
class RotationConfig:
    """
    Configuration for credential rotation.

    Defines the policy and constraints
    for rotating a specific credential.

    Attributes:
        interval_days: Rotation interval in days.
        grace_period_days: Overlap period for dual-key transition.
        auto_rotate: Enable automatic rotation.
        strategy: Rotation execution strategy.
        approval_mode: Required approval mode.
        min_age_days: Minimum age before rotation allowed.
        max_age_days: Maximum age before forced rotation.
        notify_before_days: Days before expiration to notify.
    """

    interval_days: int = 90
    grace_period_days: int = 7
    auto_rotate: bool = True
    strategy: RotationStrategy = RotationStrategy.SCHEDULED
    approval_mode: ApprovalMode = ApprovalMode.NONE
    min_age_days: int = 1
    max_age_days: int = 365
    notify_before_days: int = 7

    def to_dict(self) -> Dict[str, Any]:
        return {
            "interval_days": self.interval_days,
            "grace_period_days": self.grace_period_days,
            "auto_rotate": self.auto_rotate,
            "strategy": self.strategy.value,
            "approval_mode": self.approval_mode.value,
            "min_age_days": self.min_age_days,
            "max_age_days": self.max_age_days,
            "notify_before_days": self.notify_before_days,
        }


# Default rotation configs by credential type
DEFAULT_ROTATION_CONFIGS: Dict[CredentialType, RotationConfig] = {
    CredentialType.DATABASE: RotationConfig(
        interval_days=90,
        grace_period_days=7,
        auto_rotate=True,
        strategy=RotationStrategy.SCHEDULED,
        approval_mode=ApprovalMode.NONE,
    ),
    CredentialType.BROKER_API_KEY: RotationConfig(
        interval_days=30,
        grace_period_days=3,
        auto_rotate=True,
        strategy=RotationStrategy.SCHEDULED,
        approval_mode=ApprovalMode.SINGLE,
        notify_before_days=3,
    ),
    CredentialType.EXCHANGE_SECRET: RotationConfig(
        interval_days=30,
        grace_period_days=3,
        auto_rotate=True,
        strategy=RotationStrategy.SCHEDULED,
        approval_mode=ApprovalMode.SINGLE,
        notify_before_days=3,
    ),
    CredentialType.JWT_SIGNING: RotationConfig(
        interval_days=180,
        grace_period_days=14,
        auto_rotate=True,
        strategy=RotationStrategy.SCHEDULED,
        approval_mode=ApprovalMode.NONE,
    ),
    CredentialType.TLS_CERTIFICATE: RotationConfig(
        interval_days=365,
        grace_period_days=30,
        auto_rotate=True,
        strategy=RotationStrategy.SCHEDULED,
        approval_mode=ApprovalMode.DUAL,
        notify_before_days=30,
    ),
    CredentialType.SSH_KEY: RotationConfig(
        interval_days=90,
        grace_period_days=7,
        auto_rotate=False,
        strategy=RotationStrategy.MANUAL,
        approval_mode=ApprovalMode.SINGLE,
    ),
    CredentialType.ENCRYPTION_KEY: RotationConfig(
        interval_days=365,
        grace_period_days=30,
        auto_rotate=True,
        strategy=RotationStrategy.SCHEDULED,
        approval_mode=ApprovalMode.DUAL,
    ),
    CredentialType.WEBHOOK_SECRET: RotationConfig(
        interval_days=90,
        grace_period_days=7,
        auto_rotate=True,
        strategy=RotationStrategy.SCHEDULED,
    ),
    CredentialType.API_TOKEN: RotationConfig(
        interval_days=60,
        grace_period_days=5,
        auto_rotate=True,
        strategy=RotationStrategy.SCHEDULED,
    ),
}


def get_default_rotation_config(
    credential_type: CredentialType,
) -> RotationConfig:
    """
    Get the default rotation config for a credential type.

    Args:
        credential_type: The credential type.

    Returns:
        Default RotationConfig for the type.
    """
    config = DEFAULT_ROTATION_CONFIGS.get(
        credential_type,
        RotationConfig(),
    )
    return RotationConfig(
        interval_days=config.interval_days,
        grace_period_days=config.grace_period_days,
        auto_rotate=config.auto_rotate,
        strategy=config.strategy,
        approval_mode=config.approval_mode,
        min_age_days=config.min_age_days,
        max_age_days=config.max_age_days,
        notify_before_days=config.notify_before_days,
    )
