"""
Crossover Engine — Orchestrates crossover operations across the population.

The Crossover Engine:
    - Selects parent pairs for crossover based on fitness
    - Routes to factor_crossover or alpha_crossover based on genome type
    - Supports tournament-based parent selection
    - Tracks crossover statistics
    - Validates offspring genomes
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from services.alpha_evolution.genome import Genome, GenomeType
from services.alpha_evolution.factor_crossover import FactorCrossover
from services.alpha_evolution.alpha_crossover import AlphaCrossover

logger = logging.getLogger(__name__)


@dataclass
class CrossoverStats:
    """Statistics for crossover operations."""

    total_attempts: int = 0
    total_success: int = 0
    total_failure: int = 0
    single_point_count: int = 0
    uniform_count: int = 0
    arithmetic_count: int = 0
    factor_mix_count: int = 0
    weight_crossover_count: int = 0
    neutralization_mix_count: int = 0

    @property
    def success_rate(self) -> float:
        return self.total_success / max(self.total_attempts, 1)


class CrossoverEngine:
    """
    Orchestrates crossover operations to produce offspring from parent pairs.

    Parent selection strategies:
        - Fitness-proportional: higher-fitness parents more likely to be selected
        - Tournament: pick best of random samples
        - Random: uniform random pairing
    """

    def __init__(
        self,
        crossover_rate: float = 0.40,
        tournament_size: int = 5,
        preference_fitness_proportional: bool = True,
        seed: Optional[int] = None,
    ):
        self._crossover_rate = crossover_rate
        self._tournament_size = tournament_size
        self._preference_fitness = preference_fitness_proportional
        self._factor_crossover = FactorCrossover(crossover_rate, seed)
        self._alpha_crossover = AlphaCrossover(crossover_rate, seed)
        self._stats = CrossoverStats()
        if seed is not None:
            random.seed(seed)

    # ── Main Crossover Operation ───────────────────────────

    async def crossover_population(
        self,
        genomes: List[Genome],
        fitness_map: Optional[Dict[str, float]] = None,
    ) -> List[Genome]:
        """
        Apply crossover to produce offspring from the population.

        Args:
            genomes: Current population (parents)
            fitness_map: Individual fitness scores for parent selection

        Returns:
            List of offspring genomes
        """
        n_pairs = max(1, int(len(genomes) * self._crossover_rate // 2))
        offspring = []

        for _ in range(n_pairs):
            parent_a = self._select_parent(genomes, fitness_map)
            parent_b = self._select_parent(genomes, fitness_map)

            # Ensure parents are different
            attempts = 0
            while parent_b.genome_id == parent_a.genome_id and attempts < 5:
                parent_b = self._select_parent(genomes, fitness_map)
                attempts += 1

            self._stats.total_attempts += 1
            try:
                child = self._crossover_pair(parent_a, parent_b)
                if child:
                    offspring.append(child)
                    self._stats.total_success += 1
                else:
                    self._stats.total_failure += 1
            except Exception as e:
                self._stats.total_failure += 1
                logger.warning("Crossover failed: %s", e)

        logger.debug(
            "Crossover: %d pairs → %d offspring",
            n_pairs, len(offspring),
        )
        return offspring

    def _crossover_pair(
        self, parent_a: Genome, parent_b: Genome
    ) -> Optional[Genome]:
        """Perform crossover between two parents, routing by type."""
        if parent_a.genome_type != parent_b.genome_type:
            # Cross-type crossover not supported
            return parent_a.clone()

        if parent_a.genome_type == GenomeType.FACTOR:
            return self._factor_crossover.crossover(parent_a, parent_b)
        elif parent_a.genome_type == GenomeType.ALPHA:
            return self._alpha_crossover.crossover(parent_a, parent_b)

        return parent_a.clone()

    # ── Parent Selection ───────────────────────────────────

    def _select_parent(
        self,
        genomes: List[Genome],
        fitness_map: Optional[Dict[str, float]] = None,
    ) -> Genome:
        """
        Select a parent genome.

        Strategy:
            - Fitness-proportional: weighted by fitness score
            - Tournament: pick best from random sample
            - Random: uniform if no fitness available
        """
        if fitness_map and self._preference_fitness:
            # Tournament selection
            candidates = random.sample(
                genomes, min(self._tournament_size, len(genomes))
            )
            return max(candidates, key=lambda g: fitness_map.get(g.genome_id, 0))
        else:
            # Random selection
            return random.choice(genomes)

    # ── Batch Operations ───────────────────────────────────

    async def crossover_pairs(
        self,
        parent_pairs: List[Tuple[Genome, Genome]],
    ) -> List[Genome]:
        """Perform crossover on explicit parent pairs."""
        offspring = []
        for parent_a, parent_b in parent_pairs:
            self._stats.total_attempts += 1
            try:
                child = self._crossover_pair(parent_a, parent_b)
                if child:
                    offspring.append(child)
                    self._stats.total_success += 1
                else:
                    self._stats.total_failure += 1
            except Exception as e:
                self._stats.total_failure += 1
                logger.warning("Crossover failed for pair: %s", e)
        return offspring

    async def best_pair_crossover(
        self,
        elite: List[Genome],
        fitness_map: Dict[str, float],
        n_offspring: int = 10,
    ) -> List[Genome]:
        """
        Cross the best individuals with each other.
        This is "elite crossover" to generate high-quality offspring.
        """
        if len(elite) < 2:
            return []

        # Sort elite by fitness
        elite_sorted = sorted(
            elite, key=lambda g: fitness_map.get(g.genome_id, 0), reverse=True
        )

        offspring = []
        # Pair top performers with each other
        for i in range(min(n_offspring, len(elite_sorted) - 1)):
            parent_a = elite_sorted[i]
            parent_b = elite_sorted[i + 1]
            child = self._crossover_pair(parent_a, parent_b)
            if child:
                offspring.append(child)

        return offspring[:n_offspring]

    # ── Statistics ─────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_attempts": self._stats.total_attempts,
            "total_success": self._stats.total_success,
            "total_failure": self._stats.total_failure,
            "success_rate": self._stats.success_rate,
            "crossover_rate": self._crossover_rate,
        }

    def reset_stats(self) -> None:
        self._stats = CrossoverStats()

    @property
    def crossover_rate(self) -> float:
        return self._crossover_rate

    @property
    def stats(self) -> CrossoverStats:
        return self._stats
