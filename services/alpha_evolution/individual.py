"""
Individual — Represents a single factor or alpha candidate in the population.

Each individual has:
    - A unique ID
    - A genome (the factor/alpha expression)
    - Fitness score(s)
    - Status (pending → evaluating → validated → promoted/rejected)
    - Lineage (parent IDs, generation born)
    - Ancillary metadata
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class IndividualStatus(Enum):
    PENDING = "pending"
    EVALUATING = "evaluating"
    EVALUATED = "evaluated"
    VALIDATING = "validating"
    VALIDATED = "validated"
    REJECTED = "rejected"
    REDUNDANT = "redundant"
    ELITE = "elite"
    PROMOTED = "promoted"
    ARCHIVED = "archived"


class IndividualType(Enum):
    FACTOR = "factor"
    ALPHA = "alpha"


@dataclass
class FitnessMetrics:
    """Multi-dimensional fitness for one individual."""

    ic: float = 0.0
    rank_ic: float = 0.0
    sharpe: float = 0.0
    sortino: float = 0.0
    stability: float = 0.0
    robustness: float = 0.0
    capacity: float = 0.0
    turnover: float = 0.0
    max_drawdown: float = 0.0
    profit_factor: float = 0.0
    win_rate: float = 0.0
    novelty: float = 0.0
    diversity_contribution: float = 0.0

    # Composite score (weighted sum of above)
    composite: float = 0.0


@dataclass
class ValidationResults:
    """Results from validation pipeline."""

    out_of_sample_passed: bool = False
    out_of_sample_ic: float = 0.0
    walk_forward_passed: bool = False
    walk_forward_ic: float = 0.0
    regime_passed: bool = False
    regime_scores: Dict[str, float] = field(default_factory=dict)
    stability_passed: bool = False
    stability_score: float = 0.0
    decay_rate: float = 0.0
    capacity_million: float = 0.0
    transaction_cost_bps: float = 0.0
    all_passed: bool = False


@dataclass
class Individual:
    """
    A single individual (factor or alpha) in the evolutionary population.

    Attributes:
        id: Unique identifier
        individual_type: FACTOR or ALPHA
        genome: The encoded genetic representation
        status: Current lifecycle status
        fitness: Multi-dimensional fitness metrics
        validation: Validation results (if validated)
        parent_ids: IDs of parents (for crossover offspring)
        generation_born: Generation when this individual was created
        age: Number of generations survived
        lineage: Ordered list of ancestor IDs
        metadata: Arbitrary metadata
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    individual_type: IndividualType = IndividualType.FACTOR
    genome: Optional[Any] = None  # Genome object
    status: IndividualStatus = IndividualStatus.PENDING
    fitness: FitnessMetrics = field(default_factory=FitnessMetrics)
    validation: Optional[ValidationResults] = None
    parent_ids: List[str] = field(default_factory=list)
    generation_born: int = 0
    age: int = 0
    lineage: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None

    # ── Status Management ──────────────────────────────────

    def mark_evaluating(self) -> None:
        self.status = IndividualStatus.EVALUATING

    def mark_evaluated(self) -> None:
        self.status = IndividualStatus.EVALUATED
        self.touch()

    def mark_validating(self) -> None:
        self.status = IndividualStatus.VALIDATING

    def mark_validated(self) -> None:
        self.status = IndividualStatus.VALIDATED
        self.touch()

    def mark_rejected(self, reason: str = "") -> None:
        self.status = IndividualStatus.REJECTED
        self.metadata["rejection_reason"] = reason
        self.touch()

    def mark_redundant(self) -> None:
        self.status = IndividualStatus.REDUNDANT
        self.touch()

    def mark_elite(self) -> None:
        self.status = IndividualStatus.ELITE
        self.touch()

    def mark_promoted(self) -> None:
        self.status = IndividualStatus.PROMOTED
        self.touch()

    def mark_archived(self) -> None:
        self.status = IndividualStatus.ARCHIVED
        self.touch()

    def touch(self) -> None:
        """Update the last-modified timestamp."""
        self.updated_at = datetime.now(timezone.utc)

    def age_one_generation(self) -> None:
        """Increment age by one generation."""
        self.age += 1

    # ── Fitness ────────────────────────────────────────────

    @property
    def composite_fitness(self) -> float:
        """Get the composite fitness score."""
        return self.fitness.composite

    def set_fitness_metric(self, name: str, value: float) -> None:
        """Set a specific fitness metric."""
        if hasattr(self.fitness, name):
            setattr(self.fitness, name, value)
        self.touch()

    def compute_composite(
        self,
        weights: Optional[Dict[str, float]] = None,
    ) -> float:
        """Compute weighted composite fitness from individual metrics."""
        if weights is None:
            weights = {
                "ic": 0.15,
                "rank_ic": 0.10,
                "sharpe": 0.15,
                "stability": 0.10,
                "robustness": 0.10,
                "capacity": 0.10,
                "turnover": -0.05,
                "max_drawdown": -0.05,
                "novelty": 0.10,
                "diversity_contribution": 0.05,
            }

        composite = 0.0
        for metric, weight in weights.items():
            value = getattr(self.fitness, metric, 0.0)
            composite += value * weight

        self.fitness.composite = composite
        return composite

    # ── Validation ─────────────────────────────────────────

    def set_validation(self, results: ValidationResults) -> None:
        """Set validation results."""
        self.validation = results
        if results.all_passed:
            self.mark_validated()
        self.touch()

    # ── Serialization ──────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "individual_type": self.individual_type.value,
            "status": self.status.value,
            "fitness": {
                "ic": self.fitness.ic,
                "rank_ic": self.fitness.rank_ic,
                "sharpe": self.fitness.sharpe,
                "sortino": self.fitness.sortino,
                "stability": self.fitness.stability,
                "robustness": self.fitness.robustness,
                "capacity": self.fitness.capacity,
                "turnover": self.fitness.turnover,
                "max_drawdown": self.fitness.max_drawdown,
                "profit_factor": self.fitness.profit_factor,
                "win_rate": self.fitness.win_rate,
                "novelty": self.fitness.novelty,
                "diversity_contribution": self.fitness.diversity_contribution,
                "composite": self.fitness.composite,
            },
            "validation": (
                {
                    "out_of_sample_passed": self.validation.out_of_sample_passed,
                    "walk_forward_passed": self.validation.walk_forward_passed,
                    "regime_passed": self.validation.regime_passed,
                    "stability_passed": self.validation.stability_passed,
                    "all_passed": self.validation.all_passed,
                }
                if self.validation
                else None
            ),
            "parent_ids": self.parent_ids,
            "generation_born": self.generation_born,
            "age": self.age,
            "lineage": self.lineage,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Individual:
        """Deserialize from dictionary."""
        ind = cls(
            id=data.get("id", ""),
            individual_type=IndividualType(data.get("individual_type", "factor")),
            status=IndividualStatus(data.get("status", "pending")),
            parent_ids=data.get("parent_ids", []),
            generation_born=data.get("generation_born", 0),
            age=data.get("age", 0),
            lineage=data.get("lineage", []),
            metadata=data.get("metadata", {}),
        )
        fit = data.get("fitness", {})
        if fit:
            ind.fitness = FitnessMetrics(
                ic=fit.get("ic", 0),
                rank_ic=fit.get("rank_ic", 0),
                sharpe=fit.get("sharpe", 0),
                sortino=fit.get("sortino", 0),
                stability=fit.get("stability", 0),
                robustness=fit.get("robustness", 0),
                capacity=fit.get("capacity", 0),
                turnover=fit.get("turnover", 0),
                max_drawdown=fit.get("max_drawdown", 0),
                profit_factor=fit.get("profit_factor", 0),
                win_rate=fit.get("win_rate", 0),
                novelty=fit.get("novelty", 0),
                diversity_contribution=fit.get("diversity_contribution", 0),
                composite=fit.get("composite", 0),
            )
        return ind

    def __repr__(self) -> str:
        return (
            f"Individual(id={self.id}, type={self.individual_type.value}, "
            f"status={self.status.value}, fitness={self.composite_fitness:.4f})"
        )

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Individual):
            return False
        return self.id == other.id
