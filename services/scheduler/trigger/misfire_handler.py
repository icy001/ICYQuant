"""Misfire Handler — recovery policies for missed trigger firings.

The :class:`MisfireHandler` manages triggers that missed their scheduled
fire time due to service restart, network issues, or prolonged downtime.
It applies a configurable policy to each misfire.

Policies:
* FIRE_IMMEDIATELY — fire as soon as detected
* SKIP — ignore the missed fire
* RESCHEDULE — re-evaluate for the next valid fire time
* REPLAY — replay all missed fires in order
"""

from __future__ import annotations

import enum
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MisfirePolicy(str, enum.Enum):
    """Recovery strategy for missed trigger firings."""

    FIRE_IMMEDIATELY = "fire_immediately"
    SKIP = "skip"
    RESCHEDULE = "reschedule"
    REPLAY = "replay"


@dataclass
class MisfireRecord:
    """Record of a single misfire event."""

    trigger_id: str
    scheduled_time: datetime
    detected_at: datetime
    policy_applied: MisfirePolicy
    recovered: bool = False
    recovery_time: Optional[datetime] = None
    error: Optional[str] = None


class MisfireHandler:
    """Handles missed trigger firings with configurable recovery policies.

    Usage::

        handler = MisfireHandler(default_policy=MisfirePolicy.FIRE_IMMEDIATELY)
        await handler.handle(trigger, evaluation_result)
    """

    def __init__(
        self,
        default_policy: MisfirePolicy = MisfirePolicy.FIRE_IMMEDIATELY,
        max_misfires_per_trigger: int = 100,
        max_history: int = 10_000,
    ) -> None:
        self._lock = threading.RLock()
        self._default_policy = default_policy
        self._max_misfires_per_trigger = max_misfires_per_trigger
        self._running = False

        # Per-trigger policy overrides
        self._policies: Dict[str, MisfirePolicy] = {}

        # Per-trigger misfire counts
        self._misfire_counts: Dict[str, int] = {}

        # History
        self._history: List[MisfireRecord] = []
        self._max_history = max_history

        # Stats
        self._total_misfires: int = 0
        self._total_recovered: int = 0
        self._total_skipped: int = 0
        self._total_failed: int = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    # ------------------------------------------------------------------
    # Policy management
    # ------------------------------------------------------------------

    def set_policy(self, trigger_id: str, policy: MisfirePolicy) -> None:
        with self._lock:
            self._policies[trigger_id] = policy

    def get_policy(self, trigger_id: str) -> MisfirePolicy:
        with self._lock:
            return self._policies.get(trigger_id, self._default_policy)

    # ------------------------------------------------------------------
    # Handle misfire
    # ------------------------------------------------------------------

    async def handle(self, trigger: Any, eval_result: Any) -> bool:
        """Handle a misfire for the given trigger.

        Returns True if the misfire was successfully recovered.
        """
        trigger_id = getattr(trigger, "trigger_id", "unknown")
        policy = self.get_policy(trigger_id)

        with self._lock:
            count = self._misfire_counts.get(trigger_id, 0)
            if count >= self._max_misfires_per_trigger:
                logger.warning(
                    "MisfireHandler: trigger_id=%s exceeded max misfires (%d)",
                    trigger_id,
                    self._max_misfires_per_trigger,
                )
                return False

        now = datetime.now(timezone.utc)
        record = MisfireRecord(
            trigger_id=trigger_id,
            scheduled_time=now,
            detected_at=now,
            policy_applied=policy,
        )

        try:
            if policy == MisfirePolicy.FIRE_IMMEDIATELY:
                # Mark as recovered — the trigger will fire on next evaluate
                record.recovered = True
                record.recovery_time = now
                self._total_recovered += 1

            elif policy == MisfirePolicy.SKIP:
                record.recovered = True
                record.recovery_time = now
                self._total_skipped += 1

            elif policy == MisfirePolicy.RESCHEDULE:
                # Reset the trigger's next fire time
                if hasattr(trigger, "reset"):
                    trigger.reset()
                record.recovered = True
                record.recovery_time = now
                self._total_recovered += 1

            elif policy == MisfirePolicy.REPLAY:
                # Fire immediately, trigger will handle replay internally
                record.recovered = True
                record.recovery_time = now
                self._total_recovered += 1

            with self._lock:
                self._misfire_counts[trigger_id] = (
                    self._misfire_counts.get(trigger_id, 0) + 1
                )
                self._total_misfires += 1
                self._history.append(record)
                if len(self._history) > self._max_history:
                    self._history = self._history[-self._max_history:]

            return record.recovered

        except Exception as e:
            record.error = str(e)
            self._total_failed += 1
            logger.exception("MisfireHandler: recovery failed for trigger_id=%s", trigger_id)
            return False

    async def handle_dispatch_failure(self, queue_item: Any, dispatch_result: Any) -> None:
        """Handle a dispatch failure (may trigger misfire recovery)."""
        logger.warning(
            "MisfireHandler: dispatch failure trigger_id=%s error=%s",
            getattr(queue_item, "trigger_id", "?"),
            getattr(dispatch_result, "error", "?"),
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_misfire_count(self, trigger_id: str) -> int:
        with self._lock:
            return self._misfire_counts.get(trigger_id, 0)

    def get_recent_misfires(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "trigger_id": r.trigger_id,
                    "scheduled_time": r.scheduled_time.isoformat(),
                    "detected_at": r.detected_at.isoformat(),
                    "policy": r.policy_applied.value,
                    "recovered": r.recovered,
                    "error": r.error,
                }
                for r in self._history[-limit:]
            ]

    def reset_counts(self, trigger_id: Optional[str] = None) -> None:
        with self._lock:
            if trigger_id:
                self._misfire_counts.pop(trigger_id, None)
            else:
                self._misfire_counts.clear()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "default_policy": self._default_policy.value,
                "total_misfires": self._total_misfires,
                "total_recovered": self._total_recovered,
                "total_skipped": self._total_skipped,
                "total_failed": self._total_failed,
                "recovery_rate": (
                    (self._total_recovered + self._total_skipped)
                    / max(self._total_misfires, 1)
                ),
                "triggers_with_misfires": len(self._misfire_counts),
                "history_size": len(self._history),
            }
