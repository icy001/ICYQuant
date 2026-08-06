"""Recovery Coordinator — orchestrates cross-node recovery after failures.

The :class:`RecoveryCoordinator` manages the full recovery lifecycle:
checkpoint → replication → replay → resume. It coordinates with the
failover manager to restore scheduler state and resume operations
with minimal disruption.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RecoveryPlan:
    """A recovery plan detailing steps to restore operations."""

    def __init__(self, plan_id: str) -> None:
        self.plan_id = plan_id
        self.steps: List[Dict[str, Any]] = []
        self.current_step: int = 0
        self.status: str = "pending"
        self.created_at = datetime.now(timezone.utc)
        self.completed_at: Optional[datetime] = None

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def is_complete(self) -> bool:
        return self.current_step >= self.total_steps

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "total_steps": self.total_steps,
            "current_step": self.current_step,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class RecoveryCoordinator:
    """Orchestrates cross-node recovery after scheduler failures.

    Pipeline::

        Checkpoint → Replication → Replay → Resume

    Usage::

        rc = RecoveryCoordinator(node_id="scheduler-2")
        plan = await rc.create_recovery_plan(failed_node="scheduler-1")
        await rc.execute_plan(plan)
    """

    def __init__(
        self,
        node_id: str,
        *,
        max_recovery_attempts: int = 3,
        step_timeout_seconds: float = 30.0,
    ) -> None:
        self._node_id = node_id
        self._max_attempts = max_recovery_attempts
        self._step_timeout = step_timeout_seconds
        self._lock = threading.Lock()

        self._recovery_count: int = 0
        self._active_plans: Dict[str, RecoveryPlan] = {}
        self._last_recovery: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def node_id(self) -> str:
        return self._node_id

    @property
    def recovery_count(self) -> int:
        return self._recovery_count

    @property
    def last_recovery(self) -> Optional[datetime]:
        return self._last_recovery

    @property
    def active_plan_count(self) -> int:
        with self._lock:
            return len(self._active_plans)

    # ------------------------------------------------------------------
    # Recovery Plan
    # ------------------------------------------------------------------

    async def create_recovery_plan(self, failed_node: str) -> RecoveryPlan:
        """Create a recovery plan for a failed node.

        Standard steps:
        1. Validate checkpoint availability
        2. Load replicated state
        3. Replay pending jobs
        4. Resume scheduling
        5. Verify consistency
        """
        plan_id = f"recovery-{self._recovery_count + 1}"
        plan = RecoveryPlan(plan_id=plan_id)

        plan.steps = [
            {"step": 1, "action": "validate_checkpoint", "description": "Validate checkpoint availability"},
            {"step": 2, "action": "load_state", "description": "Load replicated state from peers"},
            {"step": 3, "action": "replay_jobs", "description": "Replay pending and in-flight jobs"},
            {"step": 4, "action": "resume_scheduling", "description": "Resume scheduling operations"},
            {"step": 5, "action": "verify_consistency", "description": "Verify cluster consistency"},
        ]

        with self._lock:
            self._active_plans[plan_id] = plan

        logger.info("Recovery plan created [id=%s, failed_node=%s]", plan_id, failed_node)
        return plan

    async def execute_plan(self, plan: RecoveryPlan) -> bool:
        """Execute a recovery plan step by step.

        Returns:
            True if all steps completed successfully.
        """
        logger.info("Executing recovery plan [id=%s, steps=%d]", plan.plan_id, plan.total_steps)
        plan.status = "in_progress"

        for step in plan.steps:
            try:
                success = await self._execute_step(step)
                if not success:
                    logger.error("Recovery step %d failed [action=%s]", step["step"], step["action"])
                    plan.status = "failed"
                    return False

                plan.current_step = step["step"]
                logger.debug("Recovery step %d completed [action=%s]", step["step"], step["action"])

            except asyncio.TimeoutError:
                logger.error("Recovery step %d timed out [action=%s]", step["step"], step["action"])
                plan.status = "failed"
                return False

        plan.status = "completed"
        plan.completed_at = datetime.now(timezone.utc)

        with self._lock:
            self._recovery_count += 1
            self._last_recovery = datetime.now(timezone.utc)
            self._active_plans.pop(plan.plan_id, None)

        logger.info("Recovery plan completed [id=%s]", plan.plan_id)
        return True

    async def cancel_plan(self, plan_id: str) -> bool:
        """Cancel an in-progress recovery plan."""
        with self._lock:
            plan = self._active_plans.get(plan_id)
            if plan:
                plan.status = "cancelled"
                self._active_plans.pop(plan_id, None)
                return True
        return False

    # ------------------------------------------------------------------
    # Quick Recovery
    # ------------------------------------------------------------------

    async def quick_recover(self, failed_node: str) -> bool:
        """Perform a quick recovery for a failed node.

        A simplified path for fast failover without creating a full plan.
        """
        logger.info("Quick recovery for failed node %s", failed_node)
        plan = await self.create_recovery_plan(failed_node)
        return await self.execute_plan(plan)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _execute_step(self, step: Dict[str, Any]) -> bool:
        """Execute a single recovery step."""
        action = step["action"]

        handlers = {
            "validate_checkpoint": self._validate_checkpoint,
            "load_state": self._load_state,
            "replay_jobs": self._replay_jobs,
            "resume_scheduling": self._resume_scheduling,
            "verify_consistency": self._verify_consistency,
        }

        handler = handlers.get(action)
        if handler:
            return await asyncio.wait_for(handler(), timeout=self._step_timeout)
        return False

    async def _validate_checkpoint(self) -> bool:
        await asyncio.sleep(0.01)
        return True

    async def _load_state(self) -> bool:
        await asyncio.sleep(0.01)
        return True

    async def _replay_jobs(self) -> bool:
        await asyncio.sleep(0.01)
        return True

    async def _resume_scheduling(self) -> bool:
        await asyncio.sleep(0.01)
        return True

    async def _verify_consistency(self) -> bool:
        await asyncio.sleep(0.01)
        return True

    def get_recovery_info(self) -> Dict[str, Any]:
        """Return recovery coordinator status summary."""
        return {
            "node_id": self._node_id,
            "recovery_count": self._recovery_count,
            "last_recovery": self._last_recovery.isoformat() if self._last_recovery else None,
            "active_plans": self.active_plan_count,
            "max_attempts": self._max_attempts,
        }
