"""
Tournament Selector — Tournament selection for evolutionary populations.

Selects individuals by running tournaments (random subsets) and picking
the winner based on fitness. Supports configurable tournament size.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional


class TournamentSelector:
    """
    Tournament-based selection operator.

    For each selection, randomly samples `tournament_size` individuals
    and returns the one with the highest fitness score.
    """

    def __init__(
        self,
        tournament_size: int = 5,
        elitism_count: int = 2,
        seed: Optional[int] = None,
    ):
        self._tournament_size = tournament_size
        self._elitism_count = elitism_count
        if seed is not None:
            random.seed(seed)

    def select_one(
        self,
        population: List[str],
        fitness_scores: Dict[str, float],
    ) -> Optional[str]:
        """Select one individual via tournament."""
        if not population:
            return None

        candidates = random.sample(
            population,
            min(self._tournament_size, len(population)),
        )
        return max(candidates, key=lambda oid: fitness_scores.get(oid, 0))

    def select_many(
        self,
        population: List[str],
        fitness_scores: Dict[str, float],
        n: int,
        with_replacement: bool = True,
    ) -> List[str]:
        """Select N individuals via tournament."""
        if not population:
            return []

        # Always preserve elite
        elite = self._select_elite(population, fitness_scores)

        remaining = n - len(elite)
        if remaining <= 0:
            return elite[:n]

        pool = list(population)
        selected = list(elite)

        for _ in range(remaining):
            if not with_replacement and pool:
                winner = self.select_one(pool, fitness_scores)
                if winner:
                    pool.remove(winner)
                    selected.append(winner)
            else:
                winner = self.select_one(population, fitness_scores)
                if winner:
                    selected.append(winner)

        return selected

    def _select_elite(
        self,
        population: List[str],
        fitness_scores: Dict[str, float],
    ) -> List[str]:
        """Select top individuals by fitness (elitism)."""
        sorted_pop = sorted(
            population,
            key=lambda oid: fitness_scores.get(oid, 0),
            reverse=True,
        )
        return sorted_pop[:self._elitism_count]

    def select_pairs(
        self,
        population: List[str],
        fitness_scores: Dict[str, float],
        n_pairs: int,
    ) -> List[tuple[str, str]]:
        """Select N parent pairs for crossover."""
        parents = self.select_many(
            population, fitness_scores, n_pairs * 2, with_replacement=True
        )
        pairs = []
        for i in range(0, len(parents) - 1, 2):
            if i + 1 < len(parents) and parents[i] != parents[i + 1]:
                pairs.append((parents[i], parents[i + 1]))
        return pairs[:n_pairs]

    @property
    def tournament_size(self) -> int:
        return self._tournament_size

    @property
    def elitism_count(self) -> int:
        return self._elitism_count
