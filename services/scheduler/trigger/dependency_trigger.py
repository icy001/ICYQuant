"""Dependency Trigger — fires when upstream triggers/ jobs complete.

The :class:`DependencyTrigger` waits for one or more upstream jobs or
workflows to finish before firing.  Supports ALL, ANY, and SEQUENTIAL
completion policies.

Typical use::

    Workflow A finishes → DependencyTrigger → Workflow B starts
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set


class DependencyPolicy(str, enum.Enum):
    """How dependencies must be satisfied."""

    ALL = "all"          # All dependencies must complete
    ANY = "any"          # Any one dependency completes
    SEQUENTIAL = "sequential"  # Dependencies complete in order


@dataclass
class _EvaluationResult:
    should_fire: bool
    is_misfire: bool = False
    payload: Dict[str, Any] = field(default_factory=dict)
    fire_at: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class DependencyTrigger:
    """Trigger that fires when upstream dependencies are satisfied.

    Usage::

        trigger = DependencyTrigger(
            schedule_id="sch-post-settlement",
            depends_on=["workflow-trade", "workflow-risk"],
            policy=DependencyPolicy.ALL,
            target="job-settlement",
        )
        # Notify when upstream completes:
        await trigger.on_upstream_completed("workflow-trade")
        await trigger.on_upstream_completed("workflow-risk")
        # → Next evaluate() will fire
    """

    schedule_id: str
    depends_on: List[str]  # upstream trigger/job/workflow ids
    policy: DependencyPolicy = DependencyPolicy.ALL
    target: str = ""
    priority: int = 120
    payload: Dict[str, Any] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    tags: list = field(default_factory=list)

    # Internal state
    trigger_id: str = field(default_factory=lambda: f"dep_{id(object()):x}")
    trigger_type: str = "dependency"
    _completed: Set[str] = field(default_factory=set)
    _last_fire_at: Optional[datetime] = field(default=None, repr=False)
    _fire_count: int = field(default=0, repr=False)
    _sequential_index: int = field(default=0, repr=False)

    # ------------------------------------------------------------------
    # Upstream notification
    # ------------------------------------------------------------------

    async def on_upstream_completed(self, upstream_id: str, result: Optional[Dict[str, Any]] = None) -> None:
        """Notify that an upstream trigger/job/workflow has completed."""
        if upstream_id not in self.depends_on:
            return
        self._completed.add(upstream_id)

    async def on_upstream_failed(self, upstream_id: str) -> None:
        """Notify that an upstream has failed (may still count for ANY policy)."""
        if self.policy == DependencyPolicy.ANY:
            self._completed.add(upstream_id)

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    async def evaluate(self) -> _EvaluationResult:
        """Evaluate whether dependency conditions are met."""
        try:
            if self._is_satisfied():
                now = datetime.now(timezone.utc)

                # Prevent double-fire
                if self._last_fire_at is not None:
                    delta = (now - self._last_fire_at).total_seconds()
                    if delta < 1.0:
                        return _EvaluationResult(should_fire=False)

                self._last_fire_at = now
                self._fire_count += 1

                return _EvaluationResult(
                    should_fire=True,
                    payload={
                        **self.payload,
                        "depends_on": self.depends_on,
                        "completed": sorted(self._completed),
                        "policy": self.policy.value,
                        "trigger_type": "dependency",
                    },
                    fire_at=now,
                )

            return _EvaluationResult(should_fire=False)

        except Exception as e:
            return _EvaluationResult(
                should_fire=False,
                is_misfire=True,
                error=str(e),
            )

    def _is_satisfied(self) -> bool:
        if not self._completed:
            return False

        if self.policy == DependencyPolicy.ALL:
            return set(self.depends_on).issubset(self._completed)

        if self.policy == DependencyPolicy.ANY:
            return bool(self._completed)

        if self.policy == DependencyPolicy.SEQUENTIAL:
            # Must have completed up to sequential_index
            expected = set(self.depends_on[: self._sequential_index + 1])
            if expected.issubset(self._completed):
                self._sequential_index += 1
                return True
            return False

        return False

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset completion state (e.g., for retry or replay)."""
        self._completed.clear()
        self._sequential_index = 0

    @property
    def is_satisfied(self) -> bool:
        return self._is_satisfied()

    @property
    def completed_count(self) -> int:
        return len(self._completed)

    @property
    def remaining(self) -> List[str]:
        return [d for d in self.depends_on if d not in self._completed]

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "trigger_type": self.trigger_type,
            "schedule_id": self.schedule_id,
            "depends_on": self.depends_on,
            "policy": self.policy.value,
            "target": self.target,
            "priority": self.priority,
            "payload": self.payload,
            "labels": self.labels,
            "tags": self.tags,
            "completed": sorted(self._completed),
            "remaining": self.remaining,
        }

    def __repr__(self) -> str:
        return (
            f"DependencyTrigger(id={self.trigger_id}, "
            f"policy={self.policy.value}, "
            f"completed={len(self._completed)}/{len(self.depends_on)})"
        )
