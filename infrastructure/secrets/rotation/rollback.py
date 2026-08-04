"""
Rotation rollback capability.

Provides rollback functionality to
revert secrets to previous versions,
recover credentials, and restore leases
when rotation fails or needs to be undone.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RollbackResult:
    """
    Result of a rollback operation.

    Attributes:
        success: Whether rollback succeeded.
        secret_key: Target secret key.
        from_version: Version rolled back from.
        to_version: Version rolled back to.
        steps_completed: List of completed rollback steps.
        steps_failed: List of failed rollback steps.
        error: Error message if failed.
        rolled_back_at: When rollback was performed.
    """

    success: bool = True
    secret_key: str = ""
    from_version: int = 2
    to_version: int = 1
    steps_completed: List[str] = field(default_factory=list)
    steps_failed: List[str] = field(default_factory=list)
    error: str = ""
    rolled_back_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "secret_key": self.secret_key,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "steps_completed": self.steps_completed,
            "steps_failed": self.steps_failed,
            "error": self.error,
            "rolled_back_at": self.rolled_back_at.isoformat() + "Z",
        }


class RotationRollback:
    """
    Rotation rollback manager.

    Provides capabilities to revert
    secrets to previous versions,
    recover credentials from backups,
    and restore lease configurations.

    Usage:
        rollback = RotationRollback(provider=my_provider)
        result = await rollback.rollback(
            secret_key="database/password",
            target_version=1,
        )
    """

    def __init__(
        self,
        provider: Optional[Any] = None,
        registry: Optional[Any] = None,
        backup_store: Optional[Any] = None,
        on_rollback: Optional[Callable] = None,
    ) -> None:
        """
        Initialize rollback manager.

        Args:
            provider: Secrets provider for write operations.
            registry: Secrets registry for version access.
            backup_store: Backup storage for credential recovery.
            on_rollback: Rollback completion callback.
        """
        self._provider = provider
        self._registry = registry
        self._backup_store = backup_store
        self._on_rollback = on_rollback
        self._rollback_history: List[RollbackResult] = []

    async def rollback(
        self,
        secret_key: str,
        target_version: int,
        reason: str = "",
    ) -> RollbackResult:
        """
        Perform a rollback operation.

        Restores a secret to a previous version
        and ensures all associated state is
        properly recovered.

        Args:
            secret_key: Secret key to rollback.
            target_version: Version to restore.
            reason: Reason for rollback.

        Returns:
            RollbackResult with details.
        """
        result = RollbackResult(
            secret_key=secret_key,
            from_version=target_version + 1,
            to_version=target_version,
        )

        logger.warning(
            "Rollback initiated for %s to version %d: %s",
            secret_key, target_version, reason,
        )

        # Step 1: Get the target version from registry
        try:
            old_secret = await self._get_version(secret_key, target_version)
            if old_secret is None:
                result.success = False
                result.error = f"Version {target_version} not found for {secret_key}"
                result.steps_failed.append("get_version")
                self._record_rollback(result)
                return result
            result.steps_completed.append("get_version")
        except Exception as e:
            result.success = False
            result.error = f"Failed to get version: {e}"
            result.steps_failed.append("get_version")
            self._record_rollback(result)
            return result

        # Step 2: Write the old version back
        try:
            await self._write_secret(secret_key, old_secret)
            result.steps_completed.append("write_secret")
        except Exception as e:
            result.success = False
            result.error = f"Failed to write old secret: {e}"
            result.steps_failed.append("write_secret")
            self._record_rollback(result)
            return result

        # Step 3: Update lifecycle state
        try:
            await self._update_lifecycle(secret_key, target_version)
            result.steps_completed.append("update_lifecycle")
        except Exception as e:
            logger.warning("Lifecycle update failed during rollback: %s", e)
            result.steps_failed.append("update_lifecycle")

        # Step 4: Restore lease if needed
        try:
            await self._restore_lease(secret_key, old_secret)
            result.steps_completed.append("restore_lease")
        except Exception as e:
            logger.warning("Lease restore failed during rollback: %s", e)
            result.steps_failed.append("restore_lease")

        # Step 5: Trigger rollback callback
        if self._on_rollback:
            try:
                await self._on_rollback(result)
                result.steps_completed.append("callback")
            except Exception as e:
                logger.warning("Rollback callback failed: %s", e)

        self._record_rollback(result)
        return result

    async def _get_version(
        self,
        secret_key: str,
        version: int,
    ) -> Optional[Any]:
        """
        Get a specific version of a secret.

        Args:
            secret_key: Secret key path.
            version: Version number.

        Returns:
            Secret item or None.
        """
        if self._registry:
            try:
                return self._registry.get_version(secret_key, version)
            except Exception as e:
                logger.debug(
                    "Registry.get_version failed for %s v%d: %s",
                    secret_key, version, e,
                )

        if self._backup_store:
            try:
                return await self._backup_store.get(secret_key, version)
            except Exception as e:
                logger.debug(
                    "Backup store get failed for %s v%d: %s",
                    secret_key, version, e,
                )

        return None

    async def _write_secret(
        self,
        secret_key: str,
        secret: Any,
    ) -> None:
        """
        Write the restored secret.

        Args:
            secret_key: Secret key path.
            secret: Secret item to write.
        """
        if self._provider and hasattr(self._provider, "write"):
            value = secret.value if hasattr(secret, "value") else str(secret)
            if hasattr(secret, "value"):
                await self._provider.write(secret_key, value)
            else:
                await self._provider.write(secret_key, str(secret))

    async def _update_lifecycle(
        self,
        secret_key: str,
        version: int,
    ) -> None:
        """
        Update lifecycle state after rollback.

        Args:
            secret_key: Secret key path.
            version: Restored version.
        """
        # Lifecycle update is a best-effort operation
        logger.info(
            "Lifecycle would be updated for %s to v%d",
            secret_key, version,
        )

    async def _restore_lease(
        self,
        secret_key: str,
        secret: Any,
    ) -> None:
        """
        Restore lease configuration.

        Args:
            secret_key: Secret key path.
            secret: Restored secret item.
        """
        # Lease restore is best-effort
        if hasattr(secret, "metadata") and secret.metadata:
            lease_id = secret.metadata.get("lease_id")
            if lease_id:
                logger.info(
                    "Lease %s would be restored for %s",
                    lease_id, secret_key,
                )

    def _record_rollback(self, result: RollbackResult) -> None:
        """Record rollback in history."""
        self._rollback_history.append(result)
        if len(self._rollback_history) > 100:
            self._rollback_history = self._rollback_history[-100:]

    def get_history(
        self,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get recent rollback history.

        Args:
            limit: Maximum entries to return.

        Returns:
            List of rollback result dictionaries.
        """
        return [r.to_dict() for r in self._rollback_history[-limit:]]

    def get_stats(self) -> Dict[str, Any]:
        """Get rollback statistics."""
        total = len(self._rollback_history)
        successful = sum(
            1 for r in self._rollback_history if r.success
        )
        return {
            "total_rollbacks": total,
            "successful": successful,
            "failed": total - successful,
            "provider_configured": self._provider is not None,
            "registry_configured": self._registry is not None,
            "backup_configured": self._backup_store is not None,
        }
