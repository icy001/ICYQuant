"""
Recovery Controller — System recovery after incidents or kill switch.

Manages the staged recovery process to bring the system back to
normal operation after an incident or kill switch event.
"""

from __future__ import annotations

import time
import logging
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RecoveryStage(Enum):
    """Stages of system recovery."""
    ASSESSMENT = "assessment"
    PARTIAL_RESTORE = "partial_restore"
    SHADOW_MODE = "shadow_mode"
    RESTRICTED_OPERATIONS = "restricted_operations"
    FULL_RESTORE = "full_restore"
    MONITORING = "monitoring"


class RecoveryController:
    """
    Manages system recovery after incidents or kill switch activation.

    Staged recovery process:
        Assessment → Partial Restore → Shadow Mode →
        Restricted Operations → Full Restore → Monitoring
    """

    def __init__(self):
        self._stage = RecoveryStage.ASSESSMENT
        self._in_recovery: bool = False
        self._recovery_start: float = 0.0
        self._recovery_history: list[dict] = []

    # ------------------------------------------------------------------
    # Recovery Lifecycle
    # ------------------------------------------------------------------

    async def start_recovery(self, incident_id: str) -> None:
        """Begin the recovery process."""
        self._in_recovery = True
        self._stage = RecoveryStage.ASSESSMENT
        self._recovery_start = time.time()
        logger.warning("Recovery started for incident %s", incident_id)
        self._recovery_history.append({
            "event": "recovery_started",
            "incident_id": incident_id,
            "timestamp": time.time(),
        })

    async def advance_stage(self, to_stage: RecoveryStage, operator: str = "autonomous") -> bool:
        """Advance to the next recovery stage."""
        valid_next = {
            RecoveryStage.ASSESSMENT: [RecoveryStage.PARTIAL_RESTORE],
            RecoveryStage.PARTIAL_RESTORE: [RecoveryStage.SHADOW_MODE],
            RecoveryStage.SHADOW_MODE: [RecoveryStage.RESTRICTED_OPERATIONS],
            RecoveryStage.RESTRICTED_OPERATIONS: [RecoveryStage.FULL_RESTORE],
            RecoveryStage.FULL_RESTORE: [RecoveryStage.MONITORING],
            RecoveryStage.MONITORING: [],
        }

        if to_stage in valid_next.get(self._stage, []):
            old = self._stage
            self._stage = to_stage
            logger.info("Recovery stage: %s → %s", old.value, to_stage.value)
            self._recovery_history.append({
                "event": "stage_advanced",
                "from": old.value,
                "to": to_stage.value,
                "operator": operator,
                "timestamp": time.time(),
            })
            return True

        return False

    async def complete_recovery(self) -> None:
        """Mark recovery as complete."""
        self._in_recovery = False
        duration = time.time() - self._recovery_start
        logger.info("Recovery completed in %.0fs", duration)
        self._recovery_history.append({
            "event": "recovery_completed",
            "duration_seconds": duration,
            "timestamp": time.time(),
        })

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    @property
    def stage(self) -> RecoveryStage:
        return self._stage

    @property
    def is_recovering(self) -> bool:
        return self._in_recovery

    def can_operate(self) -> tuple[bool, str]:
        """Determine what operations are allowed during recovery."""
        if not self._in_recovery:
            return True, ""

        if self._stage in (RecoveryStage.RESTRICTED_OPERATIONS, RecoveryStage.FULL_RESTORE, RecoveryStage.MONITORING):
            return True, f"Limited operations allowed ({self._stage.value})"

        return False, f"Recovery in progress ({self._stage.value})"

    def stats(self) -> dict:
        return {
            "in_recovery": self._in_recovery,
            "stage": self._stage.value,
            "duration_seconds": time.time() - self._recovery_start if self._in_recovery else 0,
        }
