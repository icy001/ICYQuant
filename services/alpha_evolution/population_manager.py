"""
Population Manager — Manages the evolving population of factor and alpha candidates.

Responsibilities:
    - Initialize seed populations from discovery engine
    - Track factor and alpha populations separately
    - Manage generation transitions
    - Apply elitism — carry forward top performers
    - Prune low-quality individuals
    - Maintain population size constraints
    - Provide population statistics
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class IndividualType(Enum):
    FACTOR = "factor"
    ALPHA = "alpha"


class IndividualStatus(Enum):
    PENDING = "pending"
    EVALUATING = "evaluating"
    VALIDATED = "validated"
    REJECTED = "rejected"
    REDUNDANT = "redundant"
    ELITE = "elite"
    PROMOTED = "promoted"
    ARCHIVED = "archived"


@dataclass
class PopulationConfig:
    """Configuration for population management."""

    max_factor_population: int = 5000
    max_alpha_population: int = 1000
    elite_fraction: float = 0.10
    min_fitness_for_retention: float = 0.10
    max_age_generations: int = 10
    max_redundancy_correlation: float = 0.85
    diversity_target: float = 0.40
    enable_aging: bool = True


@dataclass
class PopulationStats:
    """Statistics for a population snapshot."""

    total_individuals: int = 0
    factors: int = 0
    alphas: int = 0
    elite_count: int = 0
    validated_count: int = 0
    rejected_count: int = 0
    redundant_count: int = 0
    avg_fitness: float = 0.0
    max_fitness: float = 0.0
    min_fitness: float = 0.0
    diversity_index: float = 0.0
    avg_age: float = 0.0
    generation: int = 0


class PopulationManager:
    """
    Manages the evolving population of factor and alpha candidates.

    Dual population management:
        - Factor population: raw factors undergoing evolution
        - Alpha population: composed alphas (combinations of factors)

    Lifecycle per generation:
        1. Initialize / load seed
        2. Generate (mutation + crossover) → new individuals
        3. Evaluate fitness
        4. Filter diversity (remove redundant)
        5. Select (tournament + elitism)
        6. Validate
        7. Age and prune
    """

    def __init__(self, config: Optional[PopulationConfig] = None):
        self._config = config or PopulationConfig()
        self._factor_population: Dict[str, Dict[str, Any]] = {}
        self._alpha_population: Dict[str, Dict[str, Any]] = {}
        self._elite_ids: Set[str] = set()
        self._redundant_ids: Set[str] = set()
        self._generation: int = 0
        self._history: List[PopulationStats] = []

    # ── Population Management ──────────────────────────────

    async def seed_factors(
        self, factors: List[Dict[str, Any]]
    ) -> int:
        """Seed the factor population from discovery engine."""
        count = 0
        for factor in factors:
            fid = factor.get("id") or uuid.uuid4().hex[:12]
            self._factor_population[fid] = {
                "id": fid,
                "type": IndividualType.FACTOR,
                "status": IndividualStatus.PENDING,
                "genome": factor.get("genome", {}),
                "fitness": factor.get("fitness", 0.0),
                "generation_born": self._generation,
                "generation_evaluated": 0,
                "age": 0,
                "ancestors": factor.get("ancestors", []),
                "metadata": factor.get("metadata", {}),
                "created_at": datetime.now(timezone.utc),
            }
            count += 1
        logger.info("Seeded %d factors into population", count)
        return count

    async def seed_alphas(
        self, alphas: List[Dict[str, Any]]
    ) -> int:
        """Seed the alpha population from discovery engine."""
        count = 0
        for alpha in alphas:
            aid = alpha.get("id") or uuid.uuid4().hex[:12]
            self._alpha_population[aid] = {
                "id": aid,
                "type": IndividualType.ALPHA,
                "status": IndividualStatus.PENDING,
                "genome": alpha.get("genome", {}),
                "fitness": alpha.get("fitness", 0.0),
                "factor_ids": alpha.get("factor_ids", []),
                "generation_born": self._generation,
                "generation_evaluated": 0,
                "age": 0,
                "ancestors": alpha.get("ancestors", []),
                "parent_ids": alpha.get("parent_ids", []),
                "metadata": alpha.get("metadata", {}),
                "created_at": datetime.now(timezone.utc),
            }
            count += 1
        logger.info("Seeded %d alphas into population", count)
        return count

    async def add_factor(self, factor_data: Dict[str, Any]) -> str:
        """Add a single factor to the population."""
        fid = factor_data.get("id") or uuid.uuid4().hex[:12]
        if len(self._factor_population) >= self._config.max_factor_population:
            await self._prune_factors()
        self._factor_population[fid] = {
            "id": fid,
            "type": IndividualType.FACTOR,
            "status": IndividualStatus.PENDING,
            "genome": factor_data.get("genome", {}),
            "fitness": factor_data.get("fitness", 0.0),
            "generation_born": self._generation,
            "age": 0,
            "ancestors": factor_data.get("ancestors", []),
            "metadata": factor_data.get("metadata", {}),
            "created_at": datetime.now(timezone.utc),
        }
        return fid

    async def add_alpha(self, alpha_data: Dict[str, Any]) -> str:
        """Add a single alpha to the population."""
        aid = alpha_data.get("id") or uuid.uuid4().hex[:12]
        if len(self._alpha_population) >= self._config.max_alpha_population:
            await self._prune_alphas()
        self._alpha_population[aid] = {
            "id": aid,
            "type": IndividualType.ALPHA,
            "status": IndividualStatus.PENDING,
            "genome": alpha_data.get("genome", {}),
            "fitness": alpha_data.get("fitness", 0.0),
            "factor_ids": alpha_data.get("factor_ids", []),
            "generation_born": self._generation,
            "age": 0,
            "ancestors": alpha_data.get("ancestors", []),
            "parent_ids": alpha_data.get("parent_ids", []),
            "metadata": alpha_data.get("metadata", {}),
            "created_at": datetime.now(timezone.utc),
        }
        return aid

    # ── Fitness Updates ────────────────────────────────────

    async def update_fitness(
        self, fitness_map: Dict[str, float]
    ) -> None:
        """Update fitness scores for individuals."""
        for pop in [self._factor_population, self._alpha_population]:
            for oid, individual in pop.items():
                if oid in fitness_map:
                    individual["fitness"] = fitness_map[oid]
                    individual["generation_evaluated"] = self._generation

    async def update_status(
        self, status_map: Dict[str, IndividualStatus]
    ) -> None:
        """Update status for individuals."""
        for pop in [self._factor_population, self._alpha_population]:
            for oid, individual in pop.items():
                if oid in status_map:
                    individual["status"] = status_map[oid]

    # ── Selection & Elitism ────────────────────────────────

    async def promote_elite(self, elite_ids: List[str]) -> None:
        """Mark individuals as elite for next generation."""
        self._elite_ids = set(elite_ids)
        for oid in elite_ids:
            for pop in [self._factor_population, self._alpha_population]:
                if oid in pop:
                    pop[oid]["status"] = IndividualStatus.ELITE

    async def mark_redundant(self, redundant_ids: List[str]) -> None:
        """Mark individuals as redundant."""
        self._redundant_ids = set(redundant_ids)
        for oid in redundant_ids:
            for pop in [self._factor_population, self._alpha_population]:
                if oid in pop:
                    pop[oid]["status"] = IndividualStatus.REDUNDANT

    async def advance_generation(self) -> None:
        """Advance to next generation — age and prune population."""
        self._generation += 1

        # Age all individuals
        for pop in [self._factor_population, self._alpha_population]:
            for individual in pop.values():
                individual["age"] += 1

        # Save stats
        self._history.append(self.get_stats())

        # Prune aged-out individuals
        if self._config.enable_aging:
            await self._prune_aged()

        # Reset elite/redundant for new gen
        self._elite_ids.clear()
        self._redundant_ids.clear()

        logger.info(
            "Advanced to generation %d — factors=%d alphas=%d",
            self._generation,
            len(self._factor_population),
            len(self._alpha_population),
        )

    # ── Pruning ────────────────────────────────────────────

    async def _prune_factors(self) -> None:
        """Prune weakest factors to stay within population limit."""
        if len(self._factor_population) <= self._config.max_factor_population:
            return
        sorted_factors = sorted(
            self._factor_population.items(),
            key=lambda x: x[1].get("fitness", 0),
        )
        to_remove = len(self._factor_population) - self._config.max_factor_population
        for fid, _ in sorted_factors[:to_remove]:
            del self._factor_population[fid]
        logger.debug("Pruned %d factors", to_remove)

    async def _prune_alphas(self) -> None:
        """Prune weakest alphas to stay within population limit."""
        if len(self._alpha_population) <= self._config.max_alpha_population:
            return
        sorted_alphas = sorted(
            self._alpha_population.items(),
            key=lambda x: x[1].get("fitness", 0),
        )
        to_remove = len(self._alpha_population) - self._config.max_alpha_population
        for aid, _ in sorted_alphas[:to_remove]:
            del self._alpha_population[aid]
        logger.debug("Pruned %d alphas", to_remove)

    async def _prune_aged(self) -> None:
        """Remove individuals that exceed max age."""
        max_age = self._config.max_age_generations
        for pop in [self._factor_population, self._alpha_population]:
            aged_out = [
                oid for oid, ind in pop.items()
                if ind["age"] > max_age
                and ind["status"] != IndividualStatus.ELITE
                and ind["status"] != IndividualStatus.PROMOTED
            ]
            for oid in aged_out:
                del pop[oid]
            if aged_out:
                logger.debug("Aged out %d individuals", len(aged_out))

    # ── Queries ────────────────────────────────────────────

    def get_elite(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get top-performing non-redundant alphas."""
        candidates = []
        for pop in [self._alpha_population, self._factor_population]:
            for individual in pop.values():
                if individual["status"] not in (
                    IndividualStatus.REJECTED,
                    IndividualStatus.REDUNDANT,
                ):
                    candidates.append(individual)
        candidates.sort(key=lambda x: x.get("fitness", 0), reverse=True)
        return candidates[:limit]

    def get_population(self, type: Optional[IndividualType] = None) -> List[Dict[str, Any]]:
        """Get population filtered by type."""
        if type == IndividualType.FACTOR:
            return list(self._factor_population.values())
        elif type == IndividualType.ALPHA:
            return list(self._alpha_population.values())
        return list(self._factor_population.values()) + list(self._alpha_population.values())

    def get_stats(self) -> PopulationStats:
        """Compute population statistics."""
        all_individuals = (
            list(self._factor_population.values())
            + list(self._alpha_population.values())
        )
        if not all_individuals:
            return PopulationStats(generation=self._generation)

        fitnesses = [ind.get("fitness", 0) for ind in all_individuals]
        ages = [ind.get("age", 0) for ind in all_individuals]
        statuses = [ind.get("status") for ind in all_individuals]

        return PopulationStats(
            total_individuals=len(all_individuals),
            factors=len(self._factor_population),
            alphas=len(self._alpha_population),
            elite_count=sum(1 for s in statuses if s == IndividualStatus.ELITE),
            validated_count=sum(1 for s in statuses if s == IndividualStatus.VALIDATED),
            rejected_count=sum(1 for s in statuses if s == IndividualStatus.REJECTED),
            redundant_count=sum(1 for s in statuses if s == IndividualStatus.REDUNDANT),
            avg_fitness=sum(fitnesses) / len(fitnesses),
            max_fitness=max(fitnesses),
            min_fitness=min(fitnesses),
            diversity_index=0.5,  # placeholder
            avg_age=sum(ages) / len(ages),
            generation=self._generation,
        )

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def factor_count(self) -> int:
        return len(self._factor_population)

    @property
    def alpha_count(self) -> int:
        return len(self._alpha_population)

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "factors": self.factor_count,
            "alphas": self.alpha_count,
            "elite": len(self._elite_ids),
            "generation": self._generation,
        }
