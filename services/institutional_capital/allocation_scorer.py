"""
Allocation Scorer — Scores and ranks capital allocation proposals.

Combines objective function evaluation with constraint feasibility to produce
a unified score per allocation candidate. Supports multi-metric ranking.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from .allocation_constraints import ConstraintSet
from .allocation_objective import AllocationObjective


class ScoreStatus(str, Enum):
    OPTIMAL = "optimal"
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    REJECTED = "rejected"


@dataclass
class AllocationScore:
    """Score for a single allocation candidate."""

    allocation_id: str
    strategy_id: str = ""
    total_score: float = 0.0
    objective_score: float = 0.0
    feasibility_score: float = 0.0
    constraint_penalty: float = 0.0
    status: ScoreStatus = ScoreStatus.FEASIBLE
    violations: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    rank: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allocation_id": self.allocation_id,
            "strategy_id": self.strategy_id,
            "total_score": self.total_score,
            "objective_score": self.objective_score,
            "feasibility_score": self.feasibility_score,
            "constraint_penalty": self.constraint_penalty,
            "status": self.status.value,
            "violations": self.violations,
            "rank": self.rank,
        }


@dataclass
class AllocationScorer:
    """Scores allocation candidates against objectives and constraints."""

    scorer_id: str = field(default_factory=lambda: f"AS-{uuid.uuid4().hex[:8]}")
    objective: AllocationObjective = field(default_factory=AllocationObjective)
    constraints: ConstraintSet = field(default_factory=ConstraintSet)
    feasibility_weight: float = 10.0     # penalty multiplier for constraint violations
    min_feasibility_score: float = -100.0 # minimum before outright rejection

    def score(self, allocation_id: str, metrics: Dict[str, float],
              strategy_id: str = "") -> AllocationScore:
        """Score a single allocation candidate."""
        score = AllocationScore(
            allocation_id=allocation_id,
            strategy_id=strategy_id,
            metrics=dict(metrics),
        )

        # Objective evaluation
        score.objective_score = self.objective.evaluate(metrics)

        # Constraint check
        valid, violations = self.constraints.check_all(metrics)
        score.constraint_penalty = self.constraints.total_penalty(metrics)

        if not valid:
            score.status = ScoreStatus.INFEASIBLE
            score.violations = violations
            score.feasibility_score = self.min_feasibility_score - score.constraint_penalty
        else:
            score.feasibility_score = 0.0

        # Composite total
        score.total_score = score.objective_score + score.feasibility_score - score.constraint_penalty

        if score.feasibility_score <= self.min_feasibility_score:
            score.status = max(score.status.value, ScoreStatus.REJECTED.value)
            # Map back in a safe way
            if score.feasibility_score <= self.min_feasibility_score:
                score.status = ScoreStatus.REJECTED

        return score

    def score_many(self, candidates: List[Tuple[str, Dict[str, float], str]]) -> List[AllocationScore]:
        """Score multiple candidates and rank them.

        Each candidate: (allocation_id, metrics, strategy_id)
        """
        scores = [
            self.score(aid, metrics, sid)
            for aid, metrics, sid in candidates
        ]

        # Sort by total_score descending
        scores.sort(key=lambda s: s.total_score, reverse=True)
        for i, s in enumerate(scores):
            s.rank = i + 1

        return scores

    def top_n(self, candidates: List[Tuple[str, Dict[str, float], str]],
              n: int = 3) -> List[AllocationScore]:
        """Return top N feasible candidates."""
        scored = self.score_many(candidates)
        feasible = [s for s in scored if s.status != ScoreStatus.REJECTED]
        return feasible[:n]

    def best(self, candidates: List[Tuple[str, Dict[str, float], str]]) -> Optional[AllocationScore]:
        """Return the single best allocation."""
        scored = self.score_many(candidates)
        feasible = [s for s in scored if s.status != ScoreStatus.REJECTED]
        return feasible[0] if feasible else None
