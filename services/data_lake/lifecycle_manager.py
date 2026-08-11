"""
Lifecycle Manager — end-to-end dataset lifecycle management with
state transitions, policy-driven automation, and audit trail.

Commit 16 Part 1.3
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LifecycleStage(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    WARM = "warm"
    COLD = "cold"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"
    DELETED = "deleted"


class TransitionTrigger(str, Enum):
    TIME_BASED = "time_based"
    SIZE_BASED = "size_based"
    ACCESS_BASED = "access_based"
    MANUAL = "manual"
    POLICY_BASED = "policy_based"


@dataclass
class LifecycleTransition:
    from_stage: LifecycleStage
    to_stage: LifecycleStage
    trigger: TransitionTrigger
    condition: str = ""
    executed_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LifecyclePolicy:
    dataset: str
    stages: list[LifecycleTransition] = field(default_factory=list)
    auto_transition: bool = True
    max_active_days: int = 30
    max_warm_days: int = 90
    max_cold_days: int = 365
    archive_after_days: int = 730
    delete_after_days: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class LifecycleManager:
    """
    Manages the complete lifecycle of data lake datasets.

    Features:
    - Stage-based lifecycle (created → active → warm → cold → archived → deleted)
    - Policy-driven automatic transitions
    - Time/size/access-based triggers
    - Audit trail for all transitions
    - Manual override support
    """

    STAGE_ORDER = [
        LifecycleStage.CREATED,
        LifecycleStage.ACTIVE,
        LifecycleStage.WARM,
        LifecycleStage.COLD,
        LifecycleStage.ARCHIVED,
        LifecycleStage.DEPRECATED,
        LifecycleStage.DELETED,
    ]

    def __init__(self) -> None:
        self._policies: dict[str, LifecyclePolicy] = {}
        self._current_stages: dict[str, LifecycleStage] = {}
        self._transition_log: dict[str, list[LifecycleTransition]] = {}
        self._created_dates: dict[str, datetime] = {}

    async def register_dataset(
        self, dataset: str, *, initial_stage: LifecycleStage = LifecycleStage.ACTIVE
    ) -> None:
        """Register a dataset for lifecycle management."""
        self._current_stages[dataset] = initial_stage
        self._created_dates[dataset] = datetime.now(timezone.utc)
        logger.info("Registered dataset %s (stage=%s)", dataset, initial_stage.value)

    async def set_policy(self, policy: LifecyclePolicy) -> None:
        """Set lifecycle policy for a dataset."""
        self._policies[policy.dataset] = policy
        logger.info(
            "Lifecycle policy set for %s: %d transitions",
            policy.dataset, len(policy.stages),
        )

    async def get_stage(self, dataset: str) -> Optional[LifecycleStage]:
        """Get the current lifecycle stage for a dataset."""
        return self._current_stages.get(dataset)

    async def transition(
        self,
        dataset: str,
        to_stage: LifecycleStage,
        *,
        trigger: TransitionTrigger = TransitionTrigger.MANUAL,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Transition a dataset to a new lifecycle stage."""
        current = self._current_stages.get(dataset)
        if current is None:
            logger.warning("Dataset not registered: %s", dataset)
            return False

        transition = LifecycleTransition(
            from_stage=current,
            to_stage=to_stage,
            trigger=trigger,
            executed_at=datetime.now(timezone.utc),
            metadata=metadata or {},
        )

        self._current_stages[dataset] = to_stage
        self._transition_log.setdefault(dataset, []).append(transition)

        logger.info(
            "Lifecycle transition: %s [%s → %s] (%s)",
            dataset, current.value, to_stage.value, trigger.value,
        )
        return True

    async def evaluate(self, dataset: str) -> Optional[LifecycleTransition]:
        """Evaluate and apply automatic lifecycle transitions."""
        policy = self._policies.get(dataset)
        if not policy or not policy.auto_transition:
            return None

        current = self._current_stages.get(dataset)
        created = self._created_dates.get(dataset)
        if not current or not created:
            return None

        age_days = (datetime.now(timezone.utc) - created).days

        if age_days > policy.delete_after_days > 0:
            return LifecycleTransition(
                from_stage=current,
                to_stage=LifecycleStage.DELETED,
                trigger=TransitionTrigger.TIME_BASED,
                condition=f"age={age_days}d > delete_after={policy.delete_after_days}d",
            )
        elif age_days > policy.archive_after_days:
            return LifecycleTransition(
                from_stage=current,
                to_stage=LifecycleStage.ARCHIVED,
                trigger=TransitionTrigger.TIME_BASED,
                condition=f"age={age_days}d > archive_after={policy.archive_after_days}d",
            )
        elif age_days > policy.max_cold_days:
            return LifecycleTransition(
                from_stage=current,
                to_stage=LifecycleStage.COLD,
                trigger=TransitionTrigger.TIME_BASED,
            )
        elif age_days > policy.max_warm_days:
            return LifecycleTransition(
                from_stage=current,
                to_stage=LifecycleStage.WARM,
                trigger=TransitionTrigger.TIME_BASED,
            )

        return None

    async def get_transition_history(
        self, dataset: str
    ) -> list[dict[str, Any]]:
        """Get transition history for a dataset."""
        return [
            {
                "from_stage": t.from_stage.value,
                "to_stage": t.to_stage.value,
                "trigger": t.trigger.value,
                "executed_at": t.executed_at.isoformat() if t.executed_at else None,
            }
            for t in self._transition_log.get(dataset, [])
        ]

    async def list_stages(self) -> dict[str, str]:
        """Get current stages for all datasets."""
        return {k: v.value for k, v in self._current_stages.items()}

    def stage_order(self, stage: LifecycleStage) -> int:
        """Get the ordinal position of a lifecycle stage."""
        try:
            return self.STAGE_ORDER.index(stage)
        except ValueError:
            return -1
