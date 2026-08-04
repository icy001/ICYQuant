"""
Rotation executor.

Executes the rotation pipeline with
proper error handling, progress tracking,
and integration with the transition engine.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .transition import DualKeyTransition, TransitionPhase
from .workflow import (
    RotationWorkflow,
    WorkflowStep,
    WorkflowStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """
    Result of a rotation execution.

    Attributes:
        success: Whether rotation succeeded.
        secret_key: Target secret key.
        old_version: Previous version.
        new_version: New version.
        duration_ms: Total execution duration.
        transition_phase: Final transition phase.
        workflow_result: Workflow execution summary.
        error: Error message if failed.
        executed_at: When execution was performed.
    """

    success: bool = True
    secret_key: str = ""
    old_version: int = 1
    new_version: int = 2
    duration_ms: float = 0.0
    transition_phase: str = "completed"
    workflow_result: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    executed_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "secret_key": self.secret_key,
            "old_version": self.old_version,
            "new_version": self.new_version,
            "duration_ms": round(self.duration_ms, 2),
            "transition_phase": self.transition_phase,
            "workflow_result": self.workflow_result,
            "error": self.error,
            "executed_at": self.executed_at.isoformat() + "Z",
        }


class RotationExecutor:
    """
    Rotation pipeline executor.

    Orchestrates the full rotation execution
    including validation, dual-key transition,
    and finalization with comprehensive
    error handling and progress tracking.

    Usage:
        executor = RotationExecutor(provider=my_provider)
        result = await executor.execute(
            secret_key="database/password",
            new_value="new-secret-value",
        )
    """

    def __init__(
        self,
        provider: Optional[Any] = None,
        on_progress: Optional[Callable[[str, float], None]] = None,
        on_step_complete: Optional[Callable[[str, Any], None]] = None,
    ) -> None:
        """
        Initialize executor.

        Args:
            provider: Secrets provider.
            on_progress: Progress callback (step_name, progress_pct).
            on_step_complete: Step completion callback.
        """
        self._provider = provider
        self._on_progress = on_progress
        self._on_step_complete = on_step_complete
        self._execution_history: List[ExecutionResult] = []

    async def execute(
        self,
        secret_key: str,
        current_value: str,
        new_value: str,
        old_version: int = 1,
        grace_period_days: int = 7,
        pre_validator: Optional[Callable] = None,
        verify_fn: Optional[Callable] = None,
        skip_validation: bool = False,
    ) -> ExecutionResult:
        """
        Execute the full rotation pipeline.

        Args:
            secret_key: Secret key to rotate.
            current_value: Current secret value.
            new_value: New secret value.
            old_version: Current version number.
            grace_period_days: Grace period duration.
            pre_validator: Pre-validation function.
            verify_fn: New key verification function.
            skip_validation: Skip validation step.

        Returns:
            ExecutionResult with full details.
        """
        start = time.perf_counter()
        result = ExecutionResult(
            secret_key=secret_key,
            old_version=old_version,
            new_version=old_version + 1,
        )

        logger.info(
            "Starting rotation for %s (v%d -> v%d)",
            secret_key, old_version, old_version + 1,
        )

        # Create transition
        transition = DualKeyTransition(
            old_value=current_value,
            new_value=new_value,
            old_version=old_version,
            grace_period_days=grace_period_days,
            on_phase_change=self._on_phase_change,
        )

        # Build workflow
        workflow = RotationWorkflow(auto_rollback=True)

        # Step 1: Validation
        if not skip_validation and pre_validator:
            workflow.create_step(
                name="validate",
                description="Pre-rotation validation",
                execute=lambda: pre_validator(secret_key, new_value),
            )

        # Step 2: Begin transition
        workflow.create_step(
            name="begin_transition",
            description="Begin dual-key transition",
            execute=lambda: transition.begin(),
        )

        # Step 3: Verify new key
        workflow.create_step(
            name="verify",
            description="Verify new key works",
            execute=lambda: transition.verify(verify_fn),
        )

        # Step 4: Complete transition
        workflow.create_step(
            name="complete",
            description="Complete transition and revoke old key",
            execute=lambda: transition.complete(revoke_old=True),
        )

        # Execute workflow
        workflow_result = await workflow.execute()
        result.workflow_result = workflow_result

        # Update result
        result.duration_ms = (time.perf_counter() - start) * 1000
        result.transition_phase = transition.state.phase.value

        if workflow_result.get("success"):
            result.success = True
            logger.info(
                "Rotation completed for %s in %.1fms",
                secret_key, result.duration_ms,
            )
        else:
            result.success = False
            result.error = workflow_result.get("error", "Unknown error")
            logger.error(
                "Rotation failed for %s: %s",
                secret_key, result.error,
            )

        # Record history
        self._execution_history.append(result)
        if len(self._execution_history) > 50:
            self._execution_history = self._execution_history[-50:]

        return result

    async def emergency_rotate(
        self,
        secret_key: str,
        current_value: str,
        new_value: str,
        reason: str = "emergency",
    ) -> ExecutionResult:
        """
        Perform an emergency rotation.

        Emergency rotations skip the grace
        period and immediately revoke the
        old key after verification.

        Args:
            secret_key: Secret key to rotate.
            current_value: Current value.
            new_value: New value.
            reason: Emergency reason.

        Returns:
            ExecutionResult.
        """
        logger.warning(
            "EMERGENCY rotation for %s: %s", secret_key, reason
        )

        return await self.execute(
            secret_key=secret_key,
            current_value=current_value,
            new_value=new_value,
            grace_period_days=0,
            skip_validation=False,
        )

    def _on_phase_change(self, state: Any) -> None:
        """Handle transition phase changes."""
        phase = state.phase.value if hasattr(state, "phase") else "unknown"
        if self._on_progress:
            try:
                self._on_progress(phase, 0.0)
            except Exception:
                pass

    def get_history(
        self,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get recent execution history."""
        return [r.to_dict() for r in self._execution_history[-limit:]]

    def get_stats(self) -> Dict[str, Any]:
        """Get executor statistics."""
        total = len(self._execution_history)
        successful = sum(
            1 for r in self._execution_history if r.success
        )
        durations = [r.duration_ms for r in self._execution_history if r.success]

        return {
            "total_executions": total,
            "successful": successful,
            "failed": total - successful,
            "avg_duration_ms": round(
                sum(durations) / len(durations), 2
            ) if durations else 0,
            "provider_configured": self._provider is not None,
        }
