"""
Rotation policy management.

Defines rotation policies for different
credential types, scheduling intervals,
grace periods, and automation rules.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from ..credentials import (
    ApprovalMode,
    CredentialType,
    RotationConfig,
    RotationStrategy,
    get_default_rotation_config,
)

logger = logging.getLogger(__name__)


@dataclass
class RotationPolicy:
    """
    Rotation policy definition.

    Encapsulates all rules and constraints
    for rotating a specific credential
    or class of credentials.

    Attributes:
        name: Policy name.
        credential_type: Target credential type.
        interval_days: Rotation interval.
        grace_period_days: Overlap duration for dual-key transition.
        auto_rotate: Enable automatic rotation.
        strategy: Rotation execution strategy.
        approval_mode: Required approval level.
        min_age_days: Minimum age before rotation allowed.
        max_age_days: Maximum age before forced rotation.
        notify_before_days: Days before expiration to notify.
        enabled: Whether policy is active.
        custom_validators: Additional validation functions.
    """

    name: str = "default"
    credential_type: CredentialType = CredentialType.DATABASE
    interval_days: int = 90
    grace_period_days: int = 7
    auto_rotate: bool = True
    strategy: RotationStrategy = RotationStrategy.SCHEDULED
    approval_mode: ApprovalMode = ApprovalMode.NONE
    min_age_days: int = 1
    max_age_days: int = 365
    notify_before_days: int = 7
    enabled: bool = True
    custom_validators: List[Callable] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_config(
        cls,
        name: str,
        credential_type: CredentialType,
        config: RotationConfig,
    ) -> RotationPolicy:
        """
        Create policy from RotationConfig.

        Args:
            name: Policy name.
            credential_type: Credential type.
            config: Rotation configuration.

        Returns:
            Configured RotationPolicy.
        """
        return cls(
            name=name,
            credential_type=credential_type,
            interval_days=config.interval_days,
            grace_period_days=config.grace_period_days,
            auto_rotate=config.auto_rotate,
            strategy=config.strategy,
            approval_mode=config.approval_mode,
            min_age_days=config.min_age_days,
            max_age_days=config.max_age_days,
            notify_before_days=config.notify_before_days,
        )

    def get_next_rotation_date(
        self,
        last_rotated: Optional[datetime] = None,
    ) -> datetime:
        """
        Calculate the next rotation date.

        Args:
            last_rotated: Last rotation timestamp.

        Returns:
            Next scheduled rotation date.
        """
        if last_rotated is None:
            last_rotated = datetime.utcnow()

        return last_rotated + timedelta(days=self.interval_days)

    def is_due_for_rotation(
        self,
        last_rotated: Optional[datetime] = None,
        created_at: Optional[datetime] = None,
    ) -> bool:
        """
        Check if a secret is due for rotation.

        Args:
            last_rotated: Last rotation timestamp.
            created_at: Creation timestamp.

        Returns:
            True if rotation should be performed.
        """
        now = datetime.utcnow()

        # If never rotated, use creation time
        reference = last_rotated or created_at or now
        age_days = (now - reference).total_seconds() / 86400.0

        return age_days >= self.interval_days

    def is_overdue(
        self,
        last_rotated: Optional[datetime] = None,
        created_at: Optional[datetime] = None,
    ) -> bool:
        """
        Check if rotation is overdue (past max_age).

        Args:
            last_rotated: Last rotation timestamp.
            created_at: Creation timestamp.

        Returns:
            True if rotation is overdue.
        """
        now = datetime.utcnow()
        reference = last_rotated or created_at or now
        age_days = (now - reference).total_seconds() / 86400.0
        return age_days >= self.max_age_days

    def is_emergency_rotation_allowed(self) -> bool:
        """Check if emergency rotation is allowed."""
        return self.strategy != RotationStrategy.MANUAL

    def get_grace_end(
        self,
        rotated_at: Optional[datetime] = None,
    ) -> datetime:
        """
        Calculate when the grace period ends.

        Args:
            rotated_at: When rotation was performed.

        Returns:
            Grace period end date.
        """
        if rotated_at is None:
            rotated_at = datetime.utcnow()
        return rotated_at + timedelta(days=self.grace_period_days)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "credential_type": self.credential_type.value,
            "interval_days": self.interval_days,
            "grace_period_days": self.grace_period_days,
            "auto_rotate": self.auto_rotate,
            "strategy": self.strategy.value,
            "approval_mode": self.approval_mode.value,
            "min_age_days": self.min_age_days,
            "max_age_days": self.max_age_days,
            "notify_before_days": self.notify_before_days,
            "enabled": self.enabled,
        }


class RotationPolicyRegistry:
    """
    Registry for rotation policies.

    Manages policy lookup by credential type,
    secret key, and environment, with support
    for default and custom policies.

    Usage:
        registry = RotationPolicyRegistry()
        registry.register(default_policy)
        policy = registry.get_for_secret("database/password")
    """

    def __init__(self) -> None:
        self._policies: Dict[str, RotationPolicy] = {}
        self._default_policies: Dict[CredentialType, RotationPolicy] = {}

    def register(
        self,
        policy: RotationPolicy,
    ) -> None:
        """
        Register a rotation policy.

        Args:
            policy: The policy to register.
        """
        self._policies[policy.name] = policy
        logger.info("Rotation policy registered: %s", policy.name)

    def register_default(
        self,
        credential_type: CredentialType,
        policy: RotationPolicy,
    ) -> None:
        """
        Register a default policy for a credential type.

        Args:
            credential_type: Credential type.
            policy: Default policy for the type.
        """
        self._default_policies[credential_type] = policy

    def get(
        self,
        name: str,
    ) -> Optional[RotationPolicy]:
        """Get a policy by name."""
        return self._policies.get(name)

    def get_for_credential(
        self,
        credential_type: CredentialType,
    ) -> RotationPolicy:
        """
        Get policy for a credential type.

        Falls back to default config if no
        custom policy is registered.

        Args:
            credential_type: The credential type.

        Returns:
            RotationPolicy for the credential type.
        """
        # Check named first
        for policy in self._policies.values():
            if policy.credential_type == credential_type:
                return policy

        # Check defaults
        if credential_type in self._default_policies:
            return self._default_policies[credential_type]

        # Fall back to generated default
        config = get_default_rotation_config(credential_type)
        return RotationPolicy.from_config(
            f"default_{credential_type.value}",
            credential_type,
            config,
        )

    def list_policies(self) -> List[Dict[str, Any]]:
        """List all registered policies."""
        return [
            policy.to_dict() for policy in self._policies.values()
        ]

    def remove(self, name: str) -> bool:
        """Remove a policy."""
        return self._policies.pop(name, None) is not None

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        return {
            "total_policies": len(self._policies),
            "default_policies": len(self._default_policies),
            "policy_names": list(self._policies.keys()),
        }
