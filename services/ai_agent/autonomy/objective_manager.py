"""Objective Manager — defines and tracks measurable research objectives within autonomous workflows.

Pipeline:
    Goal -> ObjectiveManager.create_objective()
        -> Set success criteria
        -> Track metrics against criteria
        -> Evaluate objective completion
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ObjectiveStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    MET = "met"
    EXCEEDED = "exceeded"
    UNMET = "unmet"


class ObjectiveType(str, Enum):
    SHARPE = "sharpe"
    MAX_DRAWDOWN = "max_drawdown"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    RETURNS = "returns"
    CUSTOM = "custom"


@dataclass
class Objective:
    """A measurable objective with success criteria.

    Attributes:
        objective_id: Unique identifier.
        objective_type: Type of objective.
        target_value: The target value to meet.
        direction: "above" or "below" — whether higher or lower is better.
        current_value: Current measured value.
        status: Current status.
        weight: Weight in multi-objective scoring (0.0-1.0).
        metadata: Additional context.
    """

    objective_id: str = ""
    objective_type: ObjectiveType = ObjectiveType.CUSTOM
    target_value: float = 0.0
    direction: str = "above"
    current_value: float = 0.0
    status: ObjectiveStatus = ObjectiveStatus.PENDING
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_met(self) -> bool:
        if self.direction == "above":
            return self.current_value >= self.target_value
        return self.current_value <= self.target_value

    @property
    def progress_ratio(self) -> float:
        if self.target_value == 0:
            return 1.0 if self.is_met else 0.0
        ratio = self.current_value / self.target_value
        if self.direction == "above":
            return min(ratio, 1.0)
        return min(1.0 / ratio if ratio > 0 else 0.0, 1.0)


class ObjectiveManager:
    """Manages research objectives and evaluates them against criteria.

    Supports:
        - Objective creation with target values and directions
        - Multi-objective weighted scoring
        - Progress tracking against criteria
        - Custom objective types

    Usage:
        om = ObjectiveManager()
        obj = om.create_objective(ObjectiveType.SHARPE, target=1.5, direction="above")
        om.update_value(obj, 1.8)
        assert obj.status == ObjectiveStatus.MET
    """

    def __init__(self) -> None:
        self._objectives: Dict[str, Objective] = {}
        self._counter: int = 0
        self._initialized: bool = False
        logger.info("ObjectiveManager created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("ObjectiveManager initialized")

    async def shutdown(self) -> None:
        self._objectives.clear()
        self._initialized = False
        logger.info("ObjectiveManager shutdown complete")

    def create_objective(
        self,
        objective_type: ObjectiveType,
        target_value: float,
        direction: str = "above",
        weight: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Objective:
        self._counter += 1
        obj = Objective(
            objective_id=f"obj_{self._counter}",
            objective_type=objective_type,
            target_value=target_value,
            direction=direction,
            weight=weight,
            metadata=metadata or {},
        )
        self._objectives[obj.objective_id] = obj
        logger.info("Objective created: %s (type=%s, target=%.2f)", obj.objective_id, objective_type.value, target_value)
        return obj

    def update_value(self, objective: Objective, value: float) -> None:
        objective.current_value = value
        objective.status = ObjectiveStatus.IN_PROGRESS
        if objective.is_met:
            objective.status = ObjectiveStatus.MET
            if objective.direction == "above" and value >= objective.target_value * 1.2:
                objective.status = ObjectiveStatus.EXCEEDED
        logger.debug("Objective %s updated: %.2f (status=%s)", objective.objective_id, value, objective.status.value)

    def mark_unmet(self, objective: Objective) -> None:
        objective.status = ObjectiveStatus.UNMET

    def evaluate_all(self) -> Dict[str, Any]:
        objectives = list(self._objectives.values())
        if not objectives:
            return {"score": 1.0, "met": 0, "total": 0}
        total_weight = sum(o.weight for o in objectives)
        weighted_score = sum(
            o.weight * o.progress_ratio for o in objectives
        ) / total_weight if total_weight > 0 else 0.0
        met_count = sum(1 for o in objectives if o.is_met)
        return {
            "score": round(weighted_score, 4),
            "met": met_count,
            "total": len(objectives),
            "objectives": [
                {"id": o.objective_id, "type": o.objective_type.value, "target": o.target_value, "actual": o.current_value, "status": o.status.value}
                for o in objectives
            ],
        }

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_objectives": len(self._objectives),
            "evaluation": self.evaluate_all(),
            "initialized": self._initialized,
        }
