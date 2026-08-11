"""
Mutation Engine — Orchestrates mutation operations across the population.

The Mutation Engine:
    - Selects individuals for mutation based on mutation rate
    - Routes to factor_mutator or alpha_mutator based on genome type
    - Tracks mutation statistics (counts, types, success rates)
    - Validates mutated genomes
    - Supports adaptive mutation rates
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from services.alpha_evolution.genome import Genome, GenomeType
from services.alpha_evolution.factor_mutator import FactorMutator
from services.alpha_evolution.alpha_mutator import AlphaMutator

logger = logging.getLogger(__name__)


class MutationType(Enum):
    PARAMETER = "parameter"
    OPERATOR = "operator"
    FEATURE = "feature"
    WINDOW = "window"
    TRANSFORMATION = "transformation"
    STRUCTURE = "structure"
    WEIGHT = "weight"
    FACTOR_COUNT = "factor_count"
    NEUTRALIZATION = "neutralization"
    COMPOSITION = "composition"


@dataclass
class MutationStats:
    """Statistics for mutation operations."""

    total_attempts: int = 0
    total_success: int = 0
    total_failure: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)
    average_genome_size_change: float = 0.0

    @property
    def success_rate(self) -> float:
        return self.total_success / max(self.total_attempts, 1)


class MutationEngine:
    """
    Orchestrates mutation operations across the population.

    Parameters:
        mutation_rate: Fraction of population to mutate each generation
        adaptive: Whether to adapt mutation rate based on population diversity
        min_mutation_rate: Minimum mutation rate floor
        max_mutation_rate: Maximum mutation rate ceiling
    """

    def __init__(
        self,
        mutation_rate: float = 0.30,
        adaptive: bool = True,
        min_mutation_rate: float = 0.10,
        max_mutation_rate: float = 0.50,
        seed: Optional[int] = None,
    ):
        self._base_mutation_rate = mutation_rate
        self._current_mutation_rate = mutation_rate
        self._adaptive = adaptive
        self._min_rate = min_mutation_rate
        self._max_rate = max_mutation_rate
        self._factor_mutator = FactorMutator(mutation_rate, seed)
        self._alpha_mutator = AlphaMutator(mutation_rate, seed)
        self._stats = MutationStats()
        if seed is not None:
            random.seed(seed)

    # ── Main Mutation Operation ────────────────────────────

    async def mutate_population(
        self,
        genomes: List[Genome],
        diversity: float = 0.5,
    ) -> List[Genome]:
        """
        Apply mutations to a population of genomes.

        Args:
            genomes: Current population of genomes
            diversity: Current population diversity (for adaptive rate)

        Returns:
            List of newly mutated genome offspring
        """
        self._adapt_rate(diversity)
        n_to_mutate = max(1, int(len(genomes) * self._current_mutation_rate))
        candidates = random.sample(
            genomes, min(n_to_mutate, len(genomes))
        )

        offspring = []
        for genome in candidates:
            self._stats.total_attempts += 1
            try:
                mutated = self._mutate_one(genome)
                if mutated:
                    offspring.append(mutated)
                    self._stats.total_success += 1
                else:
                    self._stats.total_failure += 1
            except Exception as e:
                self._stats.total_failure += 1
                logger.warning("Mutation failed for %s: %s", genome.genome_id, e)

        logger.debug(
            "Mutation: %d attempts → %d offspring (rate=%.2f)",
            self._stats.total_attempts, len(offspring), self._current_mutation_rate,
        )
        return offspring

    def _mutate_one(self, genome: Genome) -> Optional[Genome]:
        """Mutate a single genome, routing by type."""
        if genome.genome_type == GenomeType.FACTOR:
            return self._factor_mutator.mutate(genome)
        elif genome.genome_type == GenomeType.ALPHA:
            return self._alpha_mutator.mutate(genome)
        return genome.clone()

    # ── Adaptive Rate ──────────────────────────────────────

    def _adapt_rate(self, diversity: float) -> None:
        """Adapt mutation rate based on population diversity."""
        if not self._adaptive:
            return

        if diversity < 0.20:
            # Low diversity → increase mutation to explore more
            self._current_mutation_rate = min(
                self._max_mutation_rate,
                self._base_mutation_rate * 1.5,
            )
        elif diversity > 0.60:
            # High diversity → decrease mutation to exploit
            self._current_mutation_rate = max(
                self._min_rate,
                self._base_mutation_rate * 0.7,
            )
        else:
            self._current_mutation_rate = self._base_mutation_rate

    # ── Batch Mutations ────────────────────────────────────

    async def mutate_batch(
        self,
        genomes: List[Genome],
        n_desired: int,
    ) -> List[Genome]:
        """Generate exactly N mutated offspring."""
        offspring = []
        attempts = 0
        max_attempts = n_desired * 3

        while len(offspring) < n_desired and attempts < max_attempts:
            parent = random.choice(genomes)
            mutated = self._mutate_one(parent)
            if mutated:
                offspring.append(mutated)
            attempts += 1
            self._stats.total_attempts += 1

        return offspring[:n_desired]

    # ── Statistics ─────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_attempts": self._stats.total_attempts,
            "total_success": self._stats.total_success,
            "total_failure": self._stats.total_failure,
            "success_rate": self._stats.success_rate,
            "mutation_rate": self._current_mutation_rate,
            "adaptive": self._adaptive,
            "by_type": dict(self._stats.by_type),
        }

    def reset_stats(self) -> None:
        self._stats = MutationStats()

    @property
    def mutation_rate(self) -> float:
        return self._current_mutation_rate

    @property
    def stats(self) -> MutationStats:
        return self._stats
