"""
Elitism Selector — Preserves top-performing individuals across generations.

Ensures the best individuals survive and propagate to the next generation.
Supports configurable elitism fraction and minimum fitness thresholds.
"""

from __future__ import annotations

from typing import Dict, List, Optional


class ElitismSelector:
    """
    Elitism-based selection — preserves top individuals across generations.

    Ensures:
        - Top K individuals by fitness always survive
        - Configurable fraction or absolute count
        - Can combine with other selectors (e.g., tournament)
    """

    def __init__(
        self,
        elite_fraction: float = 0.10,
        elite_count: Optional[int] = None,
        min_fitness: float = 0.0,
    ):
        self._elite_fraction = elite_fraction
        self._elite_count = elite_count
        self._min_fitness = min_fitness

    def select_elite(
        self,
        population: List[str],
        fitness_scores: Dict[str, float],
    ) -> List[str]:
        """
        Select the elite individuals from the population.

        Returns:
            List of elite individual IDs, sorted by fitness descending.
        """
        if not population:
            return []

        # Determine count
        if self._elite_count is not None:
            n_elite = min(self._elite_count, len(population))
        else:
            n_elite = max(1, int(len(population) * self._elite_fraction))

        # Sort by fitness
        sorted_pop = sorted(
            population,
            key=lambda oid: fitness_scores.get(oid, 0),
            reverse=True,
        )

        elite = []
        for oid in sorted_pop:
            if len(elite) >= n_elite:
                break
            if fitness_scores.get(oid, 0) >= self._min_fitness:
                elite.append(oid)

        return elite

    def select_non_elite(
        self,
        population: List[str],
        fitness_scores: Dict[str, float],
    ) -> List[str]:
        """Get non-elite individuals (for replacement/mutation)."""
        elite_set = set(self.select_elite(population, fitness_scores))
        return [oid for oid in population if oid not in elite_set]

    def select_elite_with_backup(
        self,
        population: List[str],
        fitness_scores: Dict[str, float],
        backup_count: int = 2,
    ) -> tuple[List[str], List[str]]:
        """
        Select elite + backup individuals.

        Returns:
            (elite_list, backup_list)
        """
        elite = self.select_elite(population, fitness_scores)
        elite_set = set(elite)
        non_elite = sorted(
            [oid for oid in population if oid not in elite_set],
            key=lambda oid: fitness_scores.get(oid, 0),
            reverse=True,
        )
        backup = non_elite[:backup_count]
        return elite, backup

    @property
    def elite_fraction(self) -> float:
        return self._elite_fraction

    @property
    def min_fitness(self) -> float:
        return self._min_fitness
