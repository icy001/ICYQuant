"""
Population — Represents a generation's worth of individuals in the evolution.

A Population is a container for a set of Individuals (factors or alphas)
that coexist in one generation. It supports:
    - Bulk fitness evaluation
    - Diversity measurement
    - Selection operations
    - Generation statistics
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from services.alpha_evolution.individual import Individual
from services.alpha_evolution.genome import Genome

logger = logging.getLogger(__name__)


@dataclass
class Population:
    """
    A generation of individuals in the evolution process.

    Can hold both factors and alphas, or be filtered by type.
    """

    generation: int = 0
    individuals: Dict[str, Individual] = field(default_factory=dict)
    elite_ids: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ── Population Operations ──────────────────────────────

    def add(self, individual: Individual) -> None:
        """Add an individual to the population."""
        self.individuals[individual.id] = individual

    def add_batch(self, individuals: List[Individual]) -> None:
        """Add multiple individuals to the population."""
        for ind in individuals:
            self.individuals[ind.id] = ind

    def remove(self, individual_id: str) -> Optional[Individual]:
        """Remove and return an individual by ID."""
        return self.individuals.pop(individual_id, None)

    def remove_batch(self, individual_ids: List[str]) -> List[Individual]:
        """Remove multiple individuals by ID."""
        removed = []
        for oid in individual_ids:
            ind = self.individuals.pop(oid, None)
            if ind:
                removed.append(ind)
        return removed

    def get(self, individual_id: str) -> Optional[Individual]:
        """Get an individual by ID."""
        return self.individuals.get(individual_id)

    # ── Selection Helpers ──────────────────────────────────

    def sort_by_fitness(self, descending: bool = True) -> List[Individual]:
        """Sort individuals by fitness score."""
        return sorted(
            self.individuals.values(),
            key=lambda ind: ind.fitness,
            reverse=descending,
        )

    def get_elite(self, fraction: float = 0.10) -> List[Individual]:
        """Get top-performing individuals."""
        sorted_ind = self.sort_by_fitness()
        n_elite = max(1, int(len(sorted_ind) * fraction))
        return sorted_ind[:n_elite]

    def get_top_n(self, n: int = 10) -> List[Individual]:
        """Get top N individuals by fitness."""
        return self.sort_by_fitness()[:n]

    def get_best(self) -> Optional[Individual]:
        """Get the best individual by fitness."""
        sorted_ind = self.sort_by_fitness()
        return sorted_ind[0] if sorted_ind else None

    def get_worst(self) -> Optional[Individual]:
        """Get the worst individual by fitness."""
        sorted_ind = self.sort_by_fitness(descending=False)
        return sorted_ind[0] if sorted_ind else None

    def sample(self, n: int = 5) -> List[Individual]:
        """Randomly sample individuals (for tournament selection)."""
        import random
        pool = list(self.individuals.values())
        if len(pool) <= n:
            return pool
        return random.sample(pool, n)

    # ── Filtering ──────────────────────────────────────────

    def filter_by_type(self, type_name: str) -> List[Individual]:
        """Filter individuals by type ('factor' or 'alpha')."""
        return [
            ind for ind in self.individuals.values()
            if ind.genome and ind.genome.genome_type == type_name
        ]

    def filter_by_fitness(self, min_fitness: float) -> List[Individual]:
        """Filter individuals above a fitness threshold."""
        return [
            ind for ind in self.individuals.values()
            if ind.fitness >= min_fitness
        ]

    def filter_by_status(self, status: str) -> List[Individual]:
        """Filter individuals by status."""
        return [
            ind for ind in self.individuals.values()
            if ind.status == status
        ]

    def filter_active(self) -> List[Individual]:
        """Get non-rejected, non-redundant individuals."""
        excluded = {"rejected", "redundant", "archived"}
        return [
            ind for ind in self.individuals.values()
            if ind.status not in excluded
        ]

    # ── Statistics ─────────────────────────────────────────

    def fitness_stats(self) -> Dict[str, float]:
        """Compute fitness statistics."""
        fitnesses = [ind.fitness for ind in self.individuals.values() if ind.fitness > 0]
        if not fitnesses:
            return {"mean": 0, "max": 0, "min": 0, "std": 0, "median": 0}

        fitnesses.sort()
        n = len(fitnesses)
        return {
            "mean": sum(fitnesses) / n,
            "max": max(fitnesses),
            "min": min(fitnesses),
            "std": (
                (sum((f - sum(fitnesses) / n) ** 2 for f in fitnesses) / n) ** 0.5
            ),
            "median": fitnesses[n // 2] if n > 0 else 0,
        }

    def diversity_score(self) -> float:
        """Compute population diversity index (simplified)."""
        if len(self.individuals) < 2:
            return 0.0
        # Placeholder: ratio of unique genomes to total
        unique_hashes = len(set(
            hash(str(ind.genome)) for ind in self.individuals.values() if ind.genome
        ))
        return unique_hashes / max(len(self.individuals), 1)

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the population."""
        stats = self.fitness_stats()
        return {
            "generation": self.generation,
            "size": len(self.individuals),
            "elite_count": len(self.elite_ids),
            "fitness": stats,
            "diversity": self.diversity_score(),
            "metadata": self.metadata,
        }

    # ── Convenience ────────────────────────────────────────

    def __len__(self) -> int:
        return len(self.individuals)

    def __contains__(self, individual_id: str) -> bool:
        return individual_id in self.individuals

    def __iter__(self):
        return iter(self.individuals.values())

    @property
    def ids(self) -> List[str]:
        return list(self.individuals.keys())

    @property
    def size(self) -> int:
        return len(self.individuals)

    @property
    def is_empty(self) -> bool:
        return len(self.individuals) == 0
