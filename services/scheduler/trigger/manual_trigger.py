"""Manual Trigger — human-initiated trigger via CLI, API, Dashboard, or SDK.

The :class:`ManualTrigger` fires exactly when explicitly invoked.  It is
used for operations, debugging, replay, and ad-hoc job execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class _EvaluationResult:
    should_fire: bool
    is_misfire: bool = False
    payload: Dict[str, Any] = field(default_factory=dict)
    fire_at: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class ManualTrigger:
    """Trigger that fires only when explicitly invoked by a human or external system.

    Usage::

        trigger = ManualTrigger(
            schedule_id="sch-adhoc-rebalance",
            target="job-rebalance",
        )
        await trigger.fire(payload={"portfolio": "P1"})
    """

    schedule_id: str
    target: str = ""
    priority: int = 200  # manual triggers default to high priority
    payload: Dict[str, Any] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    tags: list = field(default_factory=list)

    # Internal state
    trigger_id: str = field(default_factory=lambda: f"manual_{id(object()):x}")
    trigger_type: str = "manual"
    _fire_requested: bool = field(default=False, repr=False)
    _fire_payload: Dict[str, Any] = field(default_factory=dict, repr=False)
    _last_fire_at: Optional[datetime] = field(default=None, repr=False)
    _fire_count: int = field(default=0, repr=False)

    # ------------------------------------------------------------------
    # Fire API
    # ------------------------------------------------------------------

    async def fire(self, payload: Optional[Dict[str, Any]] = None) -> None:
        """Request a manual fire. Will be picked up by next evaluate()."""
        self._fire_requested = True
        if payload:
            self._fire_payload = payload

    async def fire_now(self) -> _EvaluationResult:
        """Fire immediately (synchronous convenience)."""
        await self.fire()
        return await self.evaluate()

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    async def evaluate(self) -> _EvaluationResult:
        """Evaluate — fires exactly once per fire() request."""
        try:
            if not self._fire_requested:
                return _EvaluationResult(should_fire=False)

            now = datetime.now(timezone.utc)
            self._fire_requested = False
            self._last_fire_at = now
            self._fire_count += 1

            result = _EvaluationResult(
                should_fire=True,
                payload={
                    **self.payload,
                    **self._fire_payload,
                    "trigger_type": "manual",
                    "fire_count": self._fire_count,
                },
                fire_at=now,
            )
            self._fire_payload.clear()
            return result

        except Exception as e:
            self._fire_requested = False
            return _EvaluationResult(
                should_fire=False,
                is_misfire=True,
                error=str(e),
            )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    @property
    def is_pending(self) -> bool:
        return self._fire_requested

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "trigger_type": self.trigger_type,
            "schedule_id": self.schedule_id,
            "target": self.target,
            "priority": self.priority,
            "payload": self.payload,
            "labels": self.labels,
            "tags": self.tags,
            "fire_count": self._fire_count,
        }

    def __repr__(self) -> str:
        return f"ManualTrigger(id={self.trigger_id}, target={self.target})"
