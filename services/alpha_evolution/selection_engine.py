"""
Selection Engine — Orchestrates selection across the population.

Combines:
    - Elitism: preserve top performers
    - Tournament: competitive selection
    - Pareto: preserve frontier diversity
    - Fitness threshold: filter low-quality individuals

Produces the next generation's parent pool.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from services.alpha_evolution.tournament_selector import TournamentSelector
from services.alpha_evolution.elitism_selector import ElitismSelector

logger = logging.getLogger(__name__)


@dataclass
class SelectionConfig:
    """Configuration for the selection engine."""

    elite_fraction: float = 0.10
    tournament_size: int = 5
    min_fitness: float = 0.10
    max_selection_ratio: float = 0.50
    include_pareto: bool = True


@dataclass
class SelectionResult:
    """Result of a selection operation."""

    selected: List[str]
    rejected: List[str]
    elite: List[str]
    pareto_selected: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)


class SelectionEngine:
    """
    Orchestrates selection combining elitism, tournament, and Pareto.
    """

    def __init__(self, config: Optional[SelectionConfig] = None):
        self._config = config or SelectionConfig()
        self._tournament = TournamentSelector(
            tournament_size=self._config.tournament_size,
            elitism_count=int(self._config.elite_fraction * 100),
        )
        self._elitism = ElitismSelector(
            elite_fraction=self._config.elite_fraction,
            min_fitness=self._config.min_fitness,
        )

    # ── Selection ──────────────────────────────────────────

    async def select(
        self,
        population: List[str],
        fitness_scores: Dict[str, float],
        novelty_scores: Optional[Dict[str, float]] = None,
        pareto_ids: Optional[List[str]] = None,
    ) -> SelectionResult:
        """
        Perform selection on the population.

        1. Select elite (top fraction by fitness)
        2. Select Pareto frontier (if enabled)
        3. Tournament-select remaining slots
        4. Reject low-fitness individuals
        """
        if not population:
            return SelectionResult(selected=[], rejected=[], elite=[])

        # Combined scores (fitness + novelty)
        combined = dict(fitness_scores)
        if novelty_scores:
            for oid in novelty_scores:
                combined[oid] = combined.get(oid, 0) + novelty_scores[oid] * 0.10

        # 1. Elitism
        elite = self._elitism.select_elite(population, combined)
        elite_set = set(elite)
        logger.debug("Elite selected: %d", len(elite))

        # 2. Pareto
        pareto_selected = []
        if self._config.include_pareto and pareto_ids:
            pareto_selected = [oid for oid in pareto_ids if oid in population]
            logger.debug("Pareto selected: %d", len(pareto_selected))

        # 3. Tournament for remaining
        already_selected = set(elite) | set(pareto_selected)
        candidates = [oid for oid in population if oid not in already_selected]

        n_to_select = int(len(population) * self._config.max_selection_ratio) - len(already_selected)
        n_to_select = max(1, min(n_to_select, len(candidates)))

        tournament_selected = self._tournament.select_many(
            candidates, combined, n_to_select, with_replacement=False,
        )

        # 4. Assemble result
        all_selected_ids = elite + pareto_selected + tournament_selected
        all_selected_set = set(all_selected_ids)
        rejected = [oid for oid in population if oid not in all_selected_set]

        n_selected = len(all_selected_set)
        stats = {
            "population_size": len(population),
            "selected": n_selected,
            "rejected": len(rejected),
            "selection_ratio": n_selected / max(len(population), 1),
            "elite_count": len(elite),
            "pareto_count": len(pareto_selected),
            "tournament_count": len(tournament_selected),
        }

        logger.info(
            "Selection: pop=%d → selected=%d (elite=%d, pareto=%d, tournament=%d)",
            len(population), n_selected, len(elite), len(pareto_selected), len(tournament_selected),
        )

        return SelectionResult(
            selected=list(all_selected_set),
            rejected=rejected,
            elite=elite,
            pareto_selected=pareto_selected,
            stats=stats,
        )

    # ── Utilities ──────────────────────────────────────────

    async def quick_select_best(
        self,
        population: List[str],
        fitness_scores: Dict[str, float],
        n: int,
    ) -> List[str]:
        """Quickly select the top N by fitness."""
        sorted_pop = sorted(
            population,
            key=lambda oid: fitness_scores.get(oid, 0),
            reverse=True,
        )
        return sorted_pop[:n]

    async def weighted_sample(
        self,
        population: List[str],
        fitness_scores: Dict[str, float],
        n: int,
    ) -> List[str]:
        """Fitness-proportional weighted sampling."""
        import random
        fitnesses = [fitness_scores.get(oid, 0.001) for oid in population]
        total = sum(fitnesses) or 1.0
        probs = [f / total for f in fitnesses]
        selected = random.choices(population, weights=probs, k=min(n, len(population)))
        return list(set(selected))  # deduplicate

    @property
    def config(self) -> SelectionConfig:
        return self._config
