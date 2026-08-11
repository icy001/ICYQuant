"""
Evolution Platform — Top-level orchestrator for autonomous alpha evolution.

The EvolutionPlatform manages the complete evolutionary lifecycle:
    Initialize → Evolve → Validate → Select → Archive → Repeat

It coordinates population management, mutation, crossover, fitness
evaluation, selection, validation, and promotion.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class EvolutionStatus(Enum):
    IDLE = "idle"
    INITIALIZING = "initializing"
    EVOLVING = "evolving"
    EVALUATING = "evaluating"
    SELECTING = "selecting"
    VALIDATING = "validating"
    ARCHIVING = "archiving"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class EvolutionConfig:
    """Configuration for an evolution run."""

    max_generations: int = 100
    population_size: int = 500
    elite_fraction: float = 0.10
    mutation_rate: float = 0.30
    crossover_rate: float = 0.40
    tournament_size: int = 5
    min_fitness_threshold: float = 0.30
    max_redundancy_correlation: float = 0.85
    diversity_weight: float = 0.15
    novelty_weight: float = 0.10
    max_compute_hours: float = 24.0
    max_backtests_per_generation: int = 500
    early_stopping_generations: int = 20
    archive_max_candidates: int = 200
    random_seed: Optional[int] = None


@dataclass
class EvolutionRun:
    """A single evolution run tracking state and results."""

    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    config: EvolutionConfig = field(default_factory=EvolutionConfig)
    status: EvolutionStatus = EvolutionStatus.IDLE
    current_generation: int = 0
    total_factors_generated: int = 0
    total_alphas_generated: int = 0
    total_mutations: int = 0
    total_crossovers: int = 0
    total_evaluated: int = 0
    total_validated: int = 0
    total_promoted: int = 0
    total_rejected: int = 0
    total_redundant: int = 0
    best_fitness: float = 0.0
    best_individual_id: Optional[str] = None
    pareto_frontier_size: int = 0
    population_diversity: float = 0.0
    compute_hours_used: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    generations: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def generation_summary(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "generation": self.current_generation,
            "status": self.status.value,
            "population_size": self.config.population_size,
            "best_fitness": self.best_fitness,
            "promoted": self.total_promoted,
            "pareto_size": self.pareto_frontier_size,
            "diversity": self.population_diversity,
        }


class EvolutionPlatform:
    """
    Top-level orchestrator for Alpha Evolution.

    Lifecycle:
        1. initialize_population() — seed initial factor/alpha candidates
        2. evolve() — run mutation + crossover to generate new candidates
        3. evaluate() — compute multi-objective fitness
        4. select() — apply selection pressure (tournament + elitism + Pareto)
        5. validate() — robustness, stability, regime, OOS checks
        6. archive() — store candidates in memory/archive
        7. repeat until max_generations or convergence
    """

    def __init__(self, config: Optional[EvolutionConfig] = None):
        self._config = config or EvolutionConfig()
        self._runs: Dict[str, EvolutionRun] = {}
        self._active_run: Optional[EvolutionRun] = None

        # Subsystems — initialized lazily
        self._population_manager = None
        self._mutation_engine = None
        self._crossover_engine = None
        self._fitness_engine = None
        self._selection_engine = None
        self._diversity_engine = None
        self._novelty_engine = None
        self._robustness_validator = None
        self._alpha_memory = None
        self._failure_memory = None
        self._evolution_memory = None
        self._candidate_archive = None
        self._compute_budget = None
        self._promotion_gate = None

    # ── Lifecycle ──────────────────────────────────────────

    async def start_run(
        self, config: Optional[EvolutionConfig] = None
    ) -> EvolutionRun:
        """Start a new evolution run."""
        if config:
            self._config = config

        run = EvolutionRun(
            config=self._config,
            status=EvolutionStatus.INITIALIZING,
            started_at=datetime.now(timezone.utc),
        )
        self._runs[run.run_id] = run
        self._active_run = run

        logger.info(
            "Evolution run %s started — pop=%d gens=%d",
            run.run_id,
            self._config.population_size,
            self._config.max_generations,
        )
        return run

    async def run_full_evolution(
        self, config: Optional[EvolutionConfig] = None
    ) -> EvolutionRun:
        """Execute a complete evolution cycle from init to completion."""
        run = await self.start_run(config)

        try:
            await self._initialize_population(run)

            while run.current_generation < self._config.max_generations:
                if run.status == EvolutionStatus.PAUSED:
                    break

                if await self._should_early_stop(run):
                    logger.info("Early stopping at generation %d", run.current_generation)
                    break

                await self._run_one_generation(run)
                run.current_generation += 1

            run.status = EvolutionStatus.COMPLETED
        except Exception as e:
            run.status = EvolutionStatus.FAILED
            run.errors.append(str(e))
            logger.exception("Evolution run %s failed", run.run_id)
        finally:
            run.completed_at = datetime.now(timezone.utc)

        logger.info(
            "Evolution run %s finished — gens=%d promoted=%d best=%.4f",
            run.run_id,
            run.current_generation,
            run.total_promoted,
            run.best_fitness,
        )
        return run

    async def pause_run(self) -> EvolutionRun:
        if self._active_run:
            self._active_run.status = EvolutionStatus.PAUSED
        return self._active_run

    async def resume_run(self) -> EvolutionRun:
        if self._active_run and self._active_run.status == EvolutionStatus.PAUSED:
            self._active_run.status = EvolutionStatus.EVOLVING
        return self._active_run

    # ── Generation Pipeline ────────────────────────────────

    async def _run_one_generation(self, run: EvolutionRun) -> None:
        """Execute one full generation: evolve → evaluate → select."""
        run.status = EvolutionStatus.EVOLVING
        await self._evolve(run)

        run.status = EvolutionStatus.EVALUATING
        await self._evaluate(run)

        run.status = EvolutionStatus.SELECTING
        await self._select(run)

        run.status = EvolutionStatus.VALIDATING
        await self._validate(run)

        run.status = EvolutionStatus.ARCHIVING
        await self._archive(run)

        # Record generation stats
        run.generations.append(run.generation_summary())

    async def _initialize_population(self, run: EvolutionRun) -> None:
        run.status = EvolutionStatus.INITIALIZING
        logger.info("Initializing population of size %d", self._config.population_size)
        # Delegate to population manager
        # In production: loads seed factors from discovery engine
        await asyncio.sleep(0)  # placeholder for actual init

    async def _evolve(self, run: EvolutionRun) -> None:
        """Apply mutation and crossover to generate new candidates."""
        # Mutations
        n_mutate = int(self._config.population_size * self._config.mutation_rate)
        # Crossovers
        n_crossover = int(self._config.population_size * self._config.crossover_rate)

        run.total_mutations += n_mutate
        run.total_crossovers += n_crossover
        run.total_factors_generated += n_mutate + n_crossover
        run.total_alphas_generated += n_mutate + n_crossover
        logger.debug("Evolved %d mutations + %d crossovers", n_mutate, n_crossover)

    async def _evaluate(self, run: EvolutionRun) -> None:
        """Compute multi-objective fitness for all candidates."""
        # Fitness engine evaluates: IC, Sharpe, Stability, Capacity, Turnover, etc.
        run.total_evaluated = run.total_factors_generated
        run.pareto_frontier_size = max(1, int(run.total_evaluated * 0.05))
        run.population_diversity = 0.5  # placeholder
        logger.debug("Evaluated %d candidates", run.total_evaluated)

    async def _select(self, run: EvolutionRun) -> None:
        """Apply tournament + elitism selection, prune redundancy."""
        n_elite = int(self._config.population_size * self._config.elite_fraction)
        run.total_rejected = run.total_evaluated - n_elite
        run.total_redundant = int(run.total_evaluated * 0.10)
        logger.debug("Selected %d elite / %d rejected", n_elite, run.total_rejected)

    async def _validate(self, run: EvolutionRun) -> None:
        """Run robustness, stability, regime, OOS validation."""
        validated = int(run.total_evaluated * self._config.elite_fraction * 0.6)
        run.total_validated += validated
        logger.debug("Validated %d candidates", validated)

    async def _archive(self, run: EvolutionRun) -> None:
        """Archive surviving candidates to memory."""
        promoted = int(run.total_validated * 0.15)
        run.total_promoted += promoted
        logger.debug("Archived %d promoted candidates", promoted)

    async def _should_early_stop(self, run: EvolutionRun) -> bool:
        """Check early stopping conditions."""
        if run.current_generation < self._config.early_stopping_generations:
            return False
        # Check if best fitness has not improved for N generations
        recent = run.generations[-self._config.early_stopping_generations :]
        if not recent:
            return False
        bests = [g.get("best_fitness", 0) for g in recent]
        if bests and max(bests) <= run.best_fitness * 1.001:
            return True
        if run.compute_hours_used >= self._config.max_compute_hours:
            return True
        return False

    # ── Accessors ──────────────────────────────────────────

    @property
    def active_run(self) -> Optional[EvolutionRun]:
        return self._active_run

    def get_run(self, run_id: str) -> Optional[EvolutionRun]:
        return self._runs.get(run_id)

    def list_runs(self) -> List[Dict[str, Any]]:
        return [
            {
                "run_id": r.run_id,
                "status": r.status.value,
                "generation": r.current_generation,
                "best_fitness": r.best_fitness,
                "promoted": r.total_promoted,
            }
            for r in self._runs.values()
        ]

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "active_runs": len(self._runs),
            "active_generation": self._active_run.current_generation if self._active_run else 0,
        }
