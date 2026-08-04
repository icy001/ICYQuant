"""
Secret rotation manager.

Main entry point for rotation operations,
orchestrating validation, approval,
execution, audit, and notification
into a unified interface for the
secrets platform.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from ..credentials import (
    ApprovalMode,
    CredentialType,
    RotationConfig,
    RotationStrategy,
    get_default_rotation_config,
)
from ..exceptions import SecretRotationError
from ..lifecycle import LifecycleManager, SecretLifecycle
from .approval import (
    ApprovalRequest,
    ApprovalResult,
    RotationApproval,
)
from .audit import (
    RotationAudit,
    RotationAuditEntry,
    RotationAuditAction,
)
from .executor import ExecutionResult, RotationExecutor
from .metrics import RotationMetrics
from .notifier import (
    RotationEvent,
    RotationEventType,
    RotationNotifier,
)
from .policy import RotationPolicy, RotationPolicyRegistry
from .rollback import RotationRollback
from .scheduler import RotationScheduler, ScheduleType
from .transition import TransitionPhase
from .validator import RotationValidator

logger = logging.getLogger(__name__)


class SecretRotationManager:
    """
    Main rotation orchestrator.

    Provides a unified interface for
    all rotation operations including
    manual rotation, emergency rotation,
    rollback, and scheduled rotation
    management.

    Usage:
        manager = SecretRotationManager(
            provider=vault_provider,
            registry=secrets_registry,
        )
        result = await manager.rotate("database/password")
        await manager.start_scheduler()
    """

    def __init__(
        self,
        provider: Optional[Any] = None,
        registry: Optional[Any] = None,
        cache: Optional[Any] = None,
        vault_client: Optional[Any] = None,
        provider_router: Optional[Callable[[str], Any]] = None,
    ) -> None:
        """
        Initialize rotation manager.

        Args:
            provider: Default secrets provider.
            registry: Secrets registry for versioning.
            cache: Secrets cache.
            vault_client: Vault client for Vault operations.
            provider_router: Router for provider selection.
        """
        self._provider = provider
        self._registry = registry
        self._cache = cache
        self._vault_client = vault_client
        self._provider_router = provider_router

        # Subsystems
        self._validator = RotationValidator(
            provider=provider,
            registry=registry,
        )
        self._approval = RotationApproval()
        self._executor = RotationExecutor(
            provider=provider,
        )
        self._rollback = RotationRollback(
            provider=provider,
            registry=registry,
        )
        self._audit = RotationAudit()
        self._notifier = RotationNotifier()
        self._metrics = RotationMetrics()
        self._policy_registry = RotationPolicyRegistry()
        self._lifecycle = LifecycleManager()
        self._scheduler = RotationScheduler(
            execute_fn=self._scheduled_rotate,
            on_schedule=self._scheduled_rotate,
        )

    # ── Properties ──

    @property
    def audit(self) -> RotationAudit:
        """Get audit logger."""
        return self._audit

    @property
    def scheduler(self) -> RotationScheduler:
        """Get scheduler."""
        return self._scheduler

    @property
    def metrics(self) -> RotationMetrics:
        """Get metrics."""
        return self._metrics

    @property
    def notifier(self) -> RotationNotifier:
        """Get notifier."""
        return self._notifier

    @property
    def lifecycle(self) -> LifecycleManager:
        """Get lifecycle manager."""
        return self._lifecycle

    # ── Configuration ──

    def set_provider_router(
        self,
        router: Callable[[str], Any],
    ) -> None:
        """
        Set provider router for multi-provider support.

        Args:
            router: Provider routing function.
        """
        self._provider_router = router

    def get_provider(
        self,
        secret_key: str,
    ) -> Any:
        """
        Get the appropriate provider for a secret.

        Args:
            secret_key: Secret key to look up provider for.

        Returns:
            Provider instance.
        """
        if self._provider_router:
            provider = self._provider_router(secret_key)
            if provider:
                return provider
        return self._provider

    def register_policy(
        self,
        policy: RotationPolicy,
    ) -> None:
        """Register a rotation policy."""
        self._policy_registry.register(policy)

    # ── Rotation Operations ──

    async def rotate(
        self,
        secret_key: str,
        new_value: Optional[str] = None,
        credential_type: CredentialType = CredentialType.DATABASE,
        operator: str = "system",
        reason: str = "",
        skip_approval: bool = False,
        skip_validation: bool = False,
    ) -> ExecutionResult:
        """
        Perform a manual rotation.

        Args:
            secret_key: Secret key to rotate.
            new_value: New secret value (auto-generated if None).
            credential_type: Credential type.
            operator: Who performs the rotation.
            reason: Rotation reason.
            skip_approval: Skip approval workflow.
            skip_validation: Skip pre-validation.

        Returns:
            ExecutionResult with details.

        Raises:
            SecretRotationError: If rotation fails critically.
        """
        # Log rotation start
        self._audit.log(
            action=RotationAuditAction.ROTATION_STARTED,
            secret_key=secret_key,
            operator=operator,
            reason=reason,
        )

        self._metrics.set_active_rotations(
            self._metrics._gauges.get("active_rotations", 0) + 1
        )

        try:
            # Get current secret
            provider = self.get_provider(secret_key)
            current_value = ""
            old_version = 1

            if provider:
                try:
                    current_item = provider.read(secret_key)
                    if current_item and hasattr(current_item, "value"):
                        current_value = current_item.value
                        old_version = getattr(current_item, "version", 1) or 1
                    elif isinstance(current_item, str):
                        current_value = current_item
                except Exception as e:
                    logger.warning(
                        "Could not read current value for %s: %s",
                        secret_key, e,
                    )

            # Generate new value if not provided
            if new_value is None:
                new_value = self._generate_new_value(current_value)

            # Pre-validation
            if not skip_validation and current_value:
                validation = await self._validator.validate(
                    secret_key=secret_key,
                    new_value=new_value,
                    credential_type=credential_type,
                    current_value=current_value,
                )
                if not validation.valid:
                    error_msg = "; ".join(
                        i.message for i in validation.issues
                    )
                    self._audit.log(
                        action=RotationAuditAction.VALIDATION_FAILED,
                        secret_key=secret_key,
                        operator=operator,
                        reason=error_msg,
                    )
                    self._metrics.record_rotation(
                        secret_type=credential_type.value,
                        success=False,
                        failure_reason="validation_failed",
                    )
                    raise SecretRotationError(
                        secret_key, f"Validation failed: {error_msg}"
                    )

            # Approval
            policy = self._policy_registry.get_for_credential(credential_type)
            if not skip_approval and policy.approval_mode != ApprovalMode.NONE:
                approval_result = await self._handle_approval(
                    secret_key=secret_key,
                    credential_type=credential_type,
                    operator=operator,
                    reason=reason,
                    policy=policy,
                )
                if not approval_result.approved:
                    self._audit.log(
                        action=RotationAuditAction.APPROVAL_REJECTED,
                        secret_key=secret_key,
                        operator=operator,
                        reason=reason,
                    )
                    raise SecretRotationError(
                        secret_key, f"Approval rejected: {approval_result.message}"
                    )

            # Execute rotation
            self._audit.log(
                action=RotationAuditAction.TRANSITION_BEGUN,
                secret_key=secret_key,
                operator=operator,
                old_version=old_version,
                new_version=old_version + 1,
            )

            result = await self._executor.execute(
                secret_key=secret_key,
                current_value=current_value,
                new_value=new_value,
                old_version=old_version,
                grace_period_days=policy.grace_period_days,
                skip_validation=True,
            )

            # Update lifecycle
            lifecycle = self._lifecycle.get(secret_key)
            if lifecycle:
                if result.success:
                    lifecycle.complete_rotation()
                else:
                    lifecycle.mark_deprecated(reason="rotation_failed")

            # Log completion
            if result.success:
                self._audit.log(
                    action=RotationAuditAction.ROTATION_COMPLETED,
                    secret_key=secret_key,
                    operator=operator,
                    old_version=old_version,
                    new_version=old_version + 1,
                )
                self._metrics.record_rotation(
                    secret_type=credential_type.value,
                    strategy=policy.strategy.value,
                    success=True,
                    duration=result.duration_ms / 1000,
                )
                self._metrics.record_dualkey_transition("completed")

                # Notify
                await self._notifier.notify(
                    self._notifier.create_event(
                        RotationEventType.ROTATION_SUCCESS,
                        secret_key=secret_key,
                        message=f"Rotation completed for {secret_key}",
                        severity="info",
                        old_version=old_version,
                        new_version=old_version + 1,
                    )
                )
            else:
                self._audit.log(
                    action=RotationAuditAction.ROTATION_FAILED,
                    secret_key=secret_key,
                    operator=operator,
                    reason=result.error,
                )
                self._metrics.record_rotation(
                    secret_type=credential_type.value,
                    strategy=policy.strategy.value,
                    success=False,
                    duration=result.duration_ms / 1000,
                    failure_reason=result.error[:100],
                )
                self._metrics.record_dualkey_transition("failed")

                await self._notifier.notify(
                    self._notifier.create_event(
                        RotationEventType.ROTATION_FAILED,
                        secret_key=secret_key,
                        message=f"Rotation failed for {secret_key}: {result.error}",
                        severity="error",
                    )
                )

            return result

        finally:
            current_count = self._metrics._gauges.get("active_rotations", 1)
            self._metrics.set_active_rotations(max(0, current_count - 1))

    async def emergency_rotate(
        self,
        secret_key: str,
        new_value: str,
        operator: str = "system",
        reason: str = "emergency",
    ) -> ExecutionResult:
        """
        Perform an emergency rotation.

        Args:
            secret_key: Secret key.
            new_value: New secret value.
            operator: Who performs the rotation.
            reason: Emergency reason.

        Returns:
            ExecutionResult.
        """
        logger.warning(
            "EMERGENCY rotation for %s: %s by %s",
            secret_key, reason, operator,
        )

        self._audit.log(
            action=RotationAuditAction.ROTATION_STARTED,
            secret_key=secret_key,
            operator=operator,
            reason=f"EMERGENCY: {reason}",
        )

        # Emergency bypasses normal approval but requires emergency approval
        approval_result = await self._handle_emergency_approval(
            secret_key, operator, reason,
        )

        if not approval_result.approved:
            raise SecretRotationError(
                secret_key,
                f"Emergency rotation not approved: {approval_result.message}",
            )

        # Execute with zero grace period
        provider = self.get_provider(secret_key)
        current_value = ""
        old_version = 1

        if provider:
            try:
                current_item = provider.read(secret_key)
                if current_item and hasattr(current_item, "value"):
                    current_value = current_item.value
                    old_version = getattr(current_item, "version", 1) or 1
            except Exception:
                pass

        result = await self._executor.emergency_rotate(
            secret_key=secret_key,
            current_value=current_value,
            new_value=new_value,
            reason=reason,
        )

        if result.success:
            self._audit.log(
                action=RotationAuditAction.ROTATION_COMPLETED,
                secret_key=secret_key,
                operator=operator,
                old_version=old_version,
                new_version=old_version + 1,
                reason=f"EMERGENCY: {reason}",
            )
            await self._notifier.notify(
                self._notifier.create_event(
                    RotationEventType.ROTATION_SUCCESS,
                    secret_key=secret_key,
                    message=f"Emergency rotation completed for {secret_key}",
                    severity="critical",
                    emergency=True,
                )
            )
        else:
            self._audit.log(
                action=RotationAuditAction.ROTATION_FAILED,
                secret_key=secret_key,
                operator=operator,
                reason=result.error,
            )

        return result

    async def rollback(
        self,
        secret_key: str,
        target_version: int,
        operator: str = "system",
        reason: str = "",
    ) -> Dict[str, Any]:
        """
        Rollback a secret to a previous version.

        Args:
            secret_key: Secret key to rollback.
            target_version: Version to restore.
            operator: Who performs the rollback.
            reason: Rollback reason.

        Returns:
            Rollback result dictionary.
        """
        self._audit.log(
            action=RotationAuditAction.TRANSITION_ROLLED_BACK,
            secret_key=secret_key,
            operator=operator,
            old_version=target_version + 1,
            new_version=target_version,
            reason=reason,
        )

        result = await self._rollback.rollback(
            secret_key=secret_key,
            target_version=target_version,
            reason=reason,
        )

        if result.success:
            self._audit.log(
                action=RotationAuditAction.ROTATION_ROLLED_BACK,
                secret_key=secret_key,
                operator=operator,
                old_version=target_version + 1,
                new_version=target_version,
                reason=reason,
            )
            await self._notifier.notify(
                self._notifier.create_event(
                    RotationEventType.ROLLBACK_COMPLETED,
                    secret_key=secret_key,
                    message=f"Rollback completed for {secret_key} to v{target_version}",
                    severity="warning",
                )
            )

        return result.to_dict()

    # ── Scheduler Management ──

    def schedule_rotation(
        self,
        secret_key: str,
        schedule_type: ScheduleType = ScheduleType.DAILY,
        credential_type: CredentialType = CredentialType.DATABASE,
        interval_seconds: int = 86400,
    ) -> str:
        """
        Schedule automatic rotation.

        Args:
            secret_key: Secret key.
            schedule_type: Schedule type.
            credential_type: Credential type for policy lookup.
            interval_seconds: Rotation interval.

        Returns:
            Schedule ID.
        """
        policy = self._policy_registry.get_for_credential(credential_type)
        entry = self._scheduler.add_schedule(
            secret_key=secret_key,
            schedule_type=schedule_type,
            interval_seconds=interval_seconds,
            policy=policy,
        )

        self._audit.log(
            action=RotationAuditAction.SCHEDULE_CREATED,
            secret_key=secret_key,
            reason=f"Schedule: {schedule_type.value}",
        )

        return entry.schedule_id

    async def start_scheduler(self) -> None:
        """Start the rotation scheduler."""
        await self._scheduler.start()

    async def stop_scheduler(self) -> None:
        """Stop the rotation scheduler."""
        await self._scheduler.stop()

    # ── Internal Helpers ──

    async def _scheduled_rotate(
        self,
        secret_key: str,
    ) -> bool:
        """Handle a scheduled rotation."""
        try:
            result = await self.rotate(
                secret_key=secret_key,
                skip_approval=True,
                skip_validation=False,
            )
            return result.success
        except Exception as e:
            logger.error(
                "Scheduled rotation failed for %s: %s",
                secret_key, e,
            )
            return False

    async def _handle_approval(
        self,
        secret_key: str,
        credential_type: CredentialType,
        operator: str,
        reason: str,
        policy: RotationPolicy,
    ) -> ApprovalResult:
        """Handle the approval workflow."""
        mode = policy.approval_mode
        if mode == ApprovalMode.NONE:
            return ApprovalResult(approved=True, message="No approval required")

        request = self._approval.request_approval(
            secret_key=secret_key,
            mode=mode,
            requester=operator,
            reason=reason or "Rotation requires approval",
        )

        self._audit.log(
            action=RotationAuditAction.APPROVAL_REQUESTED,
            secret_key=secret_key,
            operator=operator,
            reason=f"Approval request: {request.request_id}",
        )

        self._metrics.set_pending_approvals(
            self._metrics._gauges.get("pending_approvals", 0) + 1
        )

        # Auto-approve single approver for non-critical secrets
        if mode == ApprovalMode.SINGLE:
            request.approve("auto_system")

        result = self._approval.check_approval(request.request_id)

        self._metrics.set_pending_approvals(
            max(0, self._metrics._gauges.get("pending_approvals", 1) - 1)
        )

        return result

    async def _handle_emergency_approval(
        self,
        secret_key: str,
        operator: str,
        reason: str,
    ) -> ApprovalResult:
        """Handle emergency approval."""
        request = self._approval.request_approval(
            secret_key=secret_key,
            mode=ApprovalMode.EMERGENCY,
            requester=operator,
            reason=f"EMERGENCY: {reason}",
            emergency=True,
        )

        # Emergency auto-approval for authorized operators
        request.approve(operator, emergency=True)

        return self._approval.check_approval(request.request_id)

    def _generate_new_value(
        self,
        current_value: str,
    ) -> str:
        """Generate a new secret value."""
        import secrets
        import string

        alphabet = string.ascii_letters + string.digits
        new_chars = [secrets.choice(alphabet) for _ in range(32)]
        return "".join(new_chars)

    # ── Diagnostics ──

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the rotation system.

        Returns:
            Health status dictionary.
        """
        return {
            "healthy": True,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "scheduler_running": self._scheduler.is_running,
            "active_rotations": self._metrics._gauges.get("active_rotations", 0),
            "pending_approvals": self._metrics._gauges.get("pending_approvals", 0),
            "schedules_count": len(self._scheduler._schedules),
            "audit_entries": self._audit.count(),
            "provider_configured": self._provider is not None,
            "registry_configured": self._registry is not None,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get rotation manager statistics."""
        return {
            "scheduler": self._scheduler.get_stats(),
            "executor": self._executor.get_stats(),
            "audit": self._audit.get_stats(),
            "metrics": self._metrics.get_stats(),
            "lifecycle": self._lifecycle.get_stats(),
            "policy_registry": self._policy_registry.get_stats(),
        }
