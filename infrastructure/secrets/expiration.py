"""
Secret expiration monitoring.

Monitors secret expiration dates and
triggers alerts, rotation, and audit
events based on configurable warning
thresholds.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .credentials import CredentialType

logger = logging.getLogger(__name__)


class ExpirationLevel(str, Enum):
    """Expiration warning levels."""

    NORMAL = "normal"
    WARNING_7_DAYS = "warning_7_days"
    WARNING_3_DAYS = "warning_3_days"
    WARNING_1_DAY = "warning_1_day"
    EXPIRED = "expired"


# Thresholds in days
EXPIRATION_THRESHOLDS: List[tuple] = [
    (7, ExpirationLevel.WARNING_7_DAYS),
    (3, ExpirationLevel.WARNING_3_DAYS),
    (1, ExpirationLevel.WARNING_1_DAY),
]


@dataclass
class ExpirationStatus:
    """
    Expiration status for a single secret.

    Attributes:
        secret_key: Secret key path.
        credential_type: Credential type.
        expires_at: Expiration timestamp.
        level: Current expiration warning level.
        days_remaining: Days until expiration.
        needs_rotation: Whether rotation should be triggered.
    """

    secret_key: str = ""
    credential_type: CredentialType = CredentialType.DATABASE
    expires_at: Optional[datetime] = None
    level: ExpirationLevel = ExpirationLevel.NORMAL
    days_remaining: float = 0.0
    needs_rotation: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "secret_key": self.secret_key,
            "credential_type": self.credential_type.value,
            "expires_at": (
                self.expires_at.isoformat() + "Z"
                if self.expires_at
                else None
            ),
            "level": self.level.value,
            "days_remaining": round(self.days_remaining, 2),
            "needs_rotation": self.needs_rotation,
        }


class ExpirationMonitor:
    """
    Secret expiration monitor.

    Tracks expiration dates for all
    managed secrets and triggers
    appropriate actions as deadlines
    approach.

    Features:
    - Multi-level warnings (7, 3, 1 days)
    - Automatic rotation triggering
    - Expiration audit logging
    - Bulk status reporting

    Usage:
        monitor = ExpirationMonitor(
            on_expiring=alert_callback,
        )
        monitor.register_secret(
            "database/password",
            expires_at=datetime.utcnow() + timedelta(days=5),
        )
        status = monitor.check_all()
    """

    def __init__(
        self,
        on_expiring: Optional[Callable[[ExpirationStatus], None]] = None,
        on_expired: Optional[Callable[[ExpirationStatus], None]] = None,
        rotation_callback: Optional[Callable[[str], None]] = None,
    ) -> None:
        """
        Initialize expiration monitor.

        Args:
            on_expiring: Callback for expiring secrets.
            on_expired: Callback for expired secrets.
            rotation_callback: Callback to trigger rotation.
        """
        self._on_expiring = on_expiring
        self._on_expired = on_expired
        self._rotation_callback = rotation_callback
        self._secrets: Dict[str, Dict[str, Any]] = {}
        self._status_cache: Dict[str, ExpirationStatus] = {}

    def register_secret(
        self,
        secret_key: str,
        expires_at: Optional[datetime] = None,
        credential_type: CredentialType = CredentialType.DATABASE,
        rotation_threshold_days: int = 7,
    ) -> None:
        """
        Register a secret for expiration tracking.

        Args:
            secret_key: Secret key path.
            expires_at: Expiration date.
            credential_type: Credential type.
            rotation_threshold_days: Days before expiration to trigger rotation.
        """
        self._secrets[secret_key] = {
            "expires_at": expires_at,
            "credential_type": credential_type,
            "rotation_threshold_days": rotation_threshold_days,
            "registered_at": datetime.utcnow(),
        }

    def update_expiration(
        self,
        secret_key: str,
        expires_at: datetime,
    ) -> None:
        """Update the expiration date for a tracked secret."""
        if secret_key in self._secrets:
            self._secrets[secret_key]["expires_at"] = expires_at

    def unregister_secret(self, secret_key: str) -> None:
        """Stop tracking a secret."""
        self._secrets.pop(secret_key, None)
        self._status_cache.pop(secret_key, None)

    def get_status(
        self,
        secret_key: str,
    ) -> Optional[ExpirationStatus]:
        """Get expiration status for a secret."""
        if secret_key in self._status_cache:
            return self._status_cache[secret_key]

        return self._calculate_status(secret_key)

    def check_secret(
        self,
        secret_key: str,
    ) -> ExpirationStatus:
        """
        Check expiration status for a single secret.

        Args:
            secret_key: Secret key to check.

        Returns:
            ExpirationStatus with current level.
        """
        status = self._calculate_status(secret_key)
        self._status_cache[secret_key] = status

        # Fire callbacks
        if status.level != ExpirationLevel.NORMAL:
            if self._on_expiring:
                try:
                    self._on_expiring(status)
                except Exception as e:
                    logger.error("Expiring callback error: %s", e)

        if status.level == ExpirationLevel.EXPIRED:
            if self._on_expired:
                try:
                    self._on_expired(status)
                except Exception as e:
                    logger.error("Expired callback error: %s", e)

        # Trigger rotation if needed
        if status.needs_rotation and self._rotation_callback:
            try:
                self._rotation_callback(secret_key)
            except Exception as e:
                logger.error("Rotation callback error: %s", e)

        return status

    def check_all(self) -> List[ExpirationStatus]:
        """
        Check expiration status for all tracked secrets.

        Returns:
            List of ExpirationStatus for all secrets.
        """
        statuses: List[ExpirationStatus] = []
        for secret_key in list(self._secrets.keys()):
            try:
                status = self.check_secret(secret_key)
                statuses.append(status)
            except Exception as e:
                logger.error(
                    "Error checking expiration for %s: %s", secret_key, e,
                )

        return statuses

    def _calculate_status(
        self,
        secret_key: str,
    ) -> ExpirationStatus:
        """Calculate expiration status for a secret."""
        info = self._secrets.get(secret_key)
        if info is None:
            return ExpirationStatus(secret_key=secret_key)

        expires_at = info.get("expires_at")
        credential_type = info.get(
            "credential_type", CredentialType.DATABASE
        )
        rotation_threshold = info.get("rotation_threshold_days", 7)

        if expires_at is None:
            return ExpirationStatus(
                secret_key=secret_key,
                credential_type=credential_type,
                level=ExpirationLevel.NORMAL,
                days_remaining=9999,
                needs_rotation=False,
            )

        now = datetime.utcnow()
        days_remaining = (expires_at - now).total_seconds() / 86400.0

        # Determine level
        level = ExpirationLevel.NORMAL
        for threshold_days, threshold_level in EXPIRATION_THRESHOLDS:
            if days_remaining <= threshold_days:
                level = threshold_level

        if days_remaining <= 0:
            level = ExpirationLevel.EXPIRED

        # Determine if rotation is needed
        needs_rotation = days_remaining <= rotation_threshold

        return ExpirationStatus(
            secret_key=secret_key,
            credential_type=credential_type,
            expires_at=expires_at,
            level=level,
            days_remaining=max(0.0, days_remaining),
            needs_rotation=needs_rotation,
        )

    def get_expiring_secrets(
        self,
        level: Optional[ExpirationLevel] = None,
    ) -> List[ExpirationStatus]:
        """
        Get secrets approaching expiration.

        Args:
            level: Filter by expiration level.

        Returns:
            List of ExpirationStatus matching the filter.
        """
        all_statuses = self.check_all()
        if level:
            return [s for s in all_statuses if s.level == level]
        return [
            s for s in all_statuses
            if s.level != ExpirationLevel.NORMAL
        ]

    def get_expired_secrets(self) -> List[ExpirationStatus]:
        """Get all expired secrets."""
        return self.get_expiring_secrets(ExpirationLevel.EXPIRED)

    def count(self) -> int:
        """Get number of tracked secrets."""
        return len(self._secrets)

    def get_stats(self) -> Dict[str, Any]:
        """Get expiration monitor statistics."""
        all_statuses = self.check_all()
        by_level: Dict[str, int] = {}
        for s in all_statuses:
            level_name = s.level.value
            by_level[level_name] = by_level.get(level_name, 0) + 1

        return {
            "total_tracked": len(self._secrets),
            "by_level": by_level,
            "expiring_soon": len([
                s for s in all_statuses
                if s.level != ExpirationLevel.NORMAL
            ]),
            "expired": len([
                s for s in all_statuses
                if s.level == ExpirationLevel.EXPIRED
            ]),
            "needs_rotation": len([
                s for s in all_statuses if s.needs_rotation
            ]),
        }
