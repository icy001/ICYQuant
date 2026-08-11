"""
Evolution Orchestrator — Coordinates the full evolution pipeline.

Pipeline stages:
    1. Seed Population → from discovery engine or archive
    2. Factor Generation → mutation + crossover on factor genomes
    3. Alpha Composition → combine factors into alpha candidates
    4. Fitness Evaluation → multi-objective scoring
    5. Diversity Filtering → remove redundant/similar alphas
    6. Novelty Scoring → reward novel expressions
    7. Selection → tournament + elitism + Pareto
    8. Validation → robustness, stability, regime, OOS
    9. Archiving → store in memory with lineage
    10. Promotion → gate-controlled promotion to candidate pool
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class PipelineStage(Enum):
    SEED = "seed"
    GENERATE_FACTORS = "generate_factors"
    COMPOSE_ALPHAS = "compose_alphas"
    EVALUATE_FITNESS = "evaluate_fitness"
    FILTER_DIVERSITY = "filter_diversity"
    SCORE_NOVELTY = "score_novelty"
    SELECT = "select"
    VALIDATE = "validate"
    ARCHIVE = "archive"
    PROMOTE = "promote"
    COMPLETE = "complete"


@dataclass
class PipelineContext:
    """Shared context across pipeline stages."""

    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    generation: int = 0
    current_stage: PipelineStage = PipelineStage.SEED

    # Population data
    factor_population: List[Dict[str, Any]] = field(default_factory=list)
    alpha_population: List[Dict[str, Any]] = field(default_factory=list)
    new_factors: List[Dict[str, Any]] = field(default_factory=list)
    new_alphas: List[Dict[str, Any]] = field(default_factory=list)

    # Scoring
    fitness_scores: Dict[str, float] = field(default_factory=dict)
    novelty_scores: Dict[str, float] = field(default_factory=dict)
    diversity_scores: Dict[str, float] = field(default_factory=dict)

    # Selection results
    selected_ids: List[str] = field(default_factory=list)
    rejected_ids: List[str] = field(default_factory=list)
    redundant_ids: List[str] = field(default_factory=list)
    pareto_ids: List[str] = field(default_factory=list)

    # Validation results
    validated_ids: List[str] = field(default_factory=list)
    failed_validation_ids: List[str] = field(default_factory=list)

    # Promotion
    promoted_ids: List[str] = field(default_factory=list)
    promotion_pending_ids: List[str] = field(default_factory=list)

    # Metrics
    stage_durations: Dict[str, float] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class OrchestratorConfig:
    """Configuration for the evolution orchestrator."""

    pipeline_stages: List[PipelineStage] = field(default_factory=lambda: [
        PipelineStage.SEED,
        PipelineStage.GENERATE_FACTORS,
        PipelineStage.COMPOSE_ALPHAS,
        PipelineStage.EVALUATE_FITNESS,
        PipelineStage.FILTER_DIVERSITY,
        PipelineStage.SCORE_NOVELTY,
        PipelineStage.SELECT,
        PipelineStage.VALIDATE,
        PipelineStage.ARCHIVE,
        PipelineStage.PROMOTE,
    ])

    max_factors_per_generation: int = 2000
    max_alphas_per_generation: int = 500
    min_fitness_threshold: float = 0.20
    max_redundancy_correlation: float = 0.85
    diversity_target: float = 0.40
    novelty_weight: float = 0.10
    elite_fraction: float = 0.10
    tournament_size: int = 5
    enable_parallel_validation: bool = True
    stage_timeout_seconds: float = 300.0


class EvolutionOrchestrator:
    """
    Coordinates the full evolution pipeline stage by stage.

    The orchestrator:
        - Initializes from seed population
        - Runs factor generation (mutation + crossover)
        - Composes alphas from factors
        - Evaluates multi-objective fitness
        - Filters for diversity and novelty
        - Selects elite individuals
        - Validates robustness
        - Archives and promotes candidates
    """

    def __init__(self, config: Optional[OrchestratorConfig] = None):
        self._config = config or OrchestratorConfig()
        self._stages: Dict[PipelineStage, Any] = {}

    # ── Full Pipeline ──────────────────────────────────────

    async def run_pipeline(
        self,
        seed_factors: Optional[List[Dict[str, Any]]] = None,
        seed_alphas: Optional[List[Dict[str, Any]]] = None,
    ) -> PipelineContext:
        """Execute the full evolution pipeline for one generation."""
        ctx = PipelineContext(
            generation=0,
            factor_population=seed_factors or [],
            alpha_population=seed_alphas or [],
        )
        ctx.current_stage = PipelineStage.SEED

        for stage in self._config.pipeline_stages:
            ctx.current_stage = stage
            stage_start = asyncio.get_event_loop().time()

            try:
                await asyncio.wait_for(
                    self._execute_stage(stage, ctx),
                    timeout=self._config.stage_timeout_seconds,
                )
            except asyncio.TimeoutError:
                ctx.errors.append(f"Stage {stage.value} timed out")
                logger.error("Stage %s timed out", stage.value)
                break
            except Exception as e:
                ctx.errors.append(f"Stage {stage.value}: {e}")
                logger.exception("Stage %s failed", stage.value)
                break

            stage_duration = asyncio.get_event_loop().time() - stage_start
            ctx.stage_durations[stage.value] = stage_duration

        ctx.current_stage = PipelineStage.COMPLETE
        logger.info(
            "Pipeline complete — gen=%d factors=%d alphas=%d promoted=%d",
            ctx.generation,
            len(ctx.factor_population),
            len(ctx.alpha_population),
            len(ctx.promoted_ids),
        )
        return ctx

    async def _execute_stage(
        self, stage: PipelineStage, ctx: PipelineContext
    ) -> None:
        """Dispatch to the appropriate stage handler."""
        handlers = {
            PipelineStage.SEED: self._stage_seed,
            PipelineStage.GENERATE_FACTORS: self._stage_generate_factors,
            PipelineStage.COMPOSE_ALPHAS: self._stage_compose_alphas,
            PipelineStage.EVALUATE_FITNESS: self._stage_evaluate_fitness,
            PipelineStage.FILTER_DIVERSITY: self._stage_filter_diversity,
            PipelineStage.SCORE_NOVELTY: self._stage_score_novelty,
            PipelineStage.SELECT: self._stage_select,
            PipelineStage.VALIDATE: self._stage_validate,
            PipelineStage.ARCHIVE: self._stage_archive,
            PipelineStage.PROMOTE: self._stage_promote,
        }
        handler = handlers.get(stage)
        if handler:
            await handler(ctx)

    # ── Stage Handlers ─────────────────────────────────────

    async def _stage_seed(self, ctx: PipelineContext) -> None:
        """Stage 1: Load or generate seed population."""
        logger.debug("Stage SEED — factors=%d alphas=%d",
                     len(ctx.factor_population), len(ctx.alpha_population))
        # Seeds come from discovery engine or candidate_archive

    async def _stage_generate_factors(self, ctx: PipelineContext) -> None:
        """Stage 2: Generate new factors via mutation + crossover."""
        n_new = min(
            self._config.max_factors_per_generation,
            self._config.max_alphas_per_generation * 4,
        )
        ctx.new_factors = [{"id": f"f-{ctx.generation}-{i}"} for i in range(n_new)]
        ctx.factor_population.extend(ctx.new_factors)
        logger.debug("Stage GENERATE_FACTORS — generated %d factors", n_new)

    async def _stage_compose_alphas(self, ctx: PipelineContext) -> None:
        """Stage 3: Compose alpha candidates from factor pool."""
        n_new = min(self._config.max_alphas_per_generation, len(ctx.factor_population) // 4)
        ctx.new_alphas = [{"id": f"a-{ctx.generation}-{i}"} for i in range(n_new)]
        ctx.alpha_population.extend(ctx.new_alphas)
        logger.debug("Stage COMPOSE_ALPHAS — composed %d alphas", n_new)

    async def _stage_evaluate_fitness(self, ctx: PipelineContext) -> None:
        """Stage 4: Compute multi-objective fitness for all alphas."""
        for alpha in ctx.alpha_population:
            alpha_id = alpha["id"]
            ctx.fitness_scores[alpha_id] = 0.5  # placeholder
        logger.debug("Stage EVALUATE_FITNESS — scored %d alphas",
                     len(ctx.alpha_population))

    async def _stage_filter_diversity(self, ctx: PipelineContext) -> None:
        """Stage 5: Remove redundant/highly-correlated alphas."""
        threshold = self._config.max_redundancy_correlation
        redundant = set()
        # In production: compute pairwise correlation matrix
        # For now, mark bottom performers as potentially redundant
        if len(ctx.alpha_population) > 100:
            sorted_by_fitness = sorted(
                ctx.alpha_population,
                key=lambda a: ctx.fitness_scores.get(a["id"], 0),
            )
            n_redundant = max(1, int(len(sorted_by_fitness) * 0.05))
            for a in sorted_by_fitness[:n_redundant]:
                redundant.add(a["id"])
        ctx.redundant_ids = list(redundant)
        ctx.diversity_scores = {
            aid: 0.5 for aid in [a["id"] for a in ctx.alpha_population]
        }
        logger.debug("Stage FILTER_DIVERSITY — %d redundant identified",
                     len(ctx.redundant_ids))

    async def _stage_score_novelty(self, ctx: PipelineContext) -> None:
        """Stage 6: Score novelty of each alpha candidate."""
        for alpha in ctx.alpha_population:
            alpha_id = alpha["id"]
            ctx.novelty_scores[alpha_id] = 0.3  # placeholder
        logger.debug("Stage SCORE_NOVELTY — scored %d alphas",
                     len(ctx.alpha_population))

    async def _stage_select(self, ctx: PipelineContext) -> None:
        """Stage 7: Tournament + elitism + Pareto selection."""
        # Elite: top fraction by combined score
        combined_scores = {}
        for aid in ctx.fitness_scores:
            fitness = ctx.fitness_scores.get(aid, 0)
            novelty = ctx.novelty_scores.get(aid, 0)
            combined_scores[aid] = fitness + self._config.novelty_weight * novelty

        sorted_ids = sorted(combined_scores, key=combined_scores.get, reverse=True)
        n_elite = max(1, int(len(sorted_ids) * self._config.elite_fraction))

        # Exclude redundant
        elite = [oid for oid in sorted_ids if oid not in set(ctx.redundant_ids)]
        ctx.selected_ids = elite[:n_elite]
        ctx.rejected_ids = [
            oid for oid in sorted_ids
            if oid not in set(ctx.selected_ids) and oid not in set(ctx.redundant_ids)
        ]
        ctx.pareto_ids = ctx.selected_ids[: max(1, len(ctx.selected_ids) // 3)]
        logger.debug("Stage SELECT — selected=%d rejected=%d pareto=%d",
                     len(ctx.selected_ids), len(ctx.rejected_ids), len(ctx.pareto_ids))

    async def _stage_validate(self, ctx: PipelineContext) -> None:
        """Stage 8: Robustness, stability, regime, OOS validation."""
        # In production: submit to validation pipeline
        passed = ctx.pareto_ids[:int(len(ctx.pareto_ids) * 0.7)]
        failed = [oid for oid in ctx.pareto_ids if oid not in set(passed)]
        ctx.validated_ids = passed
        ctx.failed_validation_ids = failed
        logger.debug("Stage VALIDATE — passed=%d failed=%d",
                     len(passed), len(failed))

    async def _stage_archive(self, ctx: PipelineContext) -> None:
        """Stage 9: Archive surviving candidates to memory."""
        logger.debug("Stage ARCHIVE — archiving %d validated alphas",
                     len(ctx.validated_ids))

    async def _stage_promote(self, ctx: PipelineContext) -> None:
        """Stage 10: Gate-controlled promotion to candidate pool."""
        # Filter by fitness threshold
        to_promote = [
            oid for oid in ctx.validated_ids
            if ctx.fitness_scores.get(oid, 0) >= self._config.min_fitness_threshold
        ]
        ctx.promoted_ids = to_promote
        logger.debug("Stage PROMOTE — promoted %d alphas", len(to_promote))

    # ── Pipeline Statistics ────────────────────────────────

    def get_pipeline_summary(self, ctx: PipelineContext) -> Dict[str, Any]:
        return {
            "run_id": ctx.run_id,
            "generation": ctx.generation,
            "current_stage": ctx.current_stage.value,
            "population": {
                "factors": len(ctx.factor_population),
                "alphas": len(ctx.alpha_population),
            },
            "selection": {
                "selected": len(ctx.selected_ids),
                "rejected": len(ctx.rejected_ids),
                "redundant": len(ctx.redundant_ids),
                "pareto": len(ctx.pareto_ids),
            },
            "validation": {
                "passed": len(ctx.validated_ids),
                "failed": len(ctx.failed_validation_ids),
            },
            "promotion": {
                "promoted": len(ctx.promoted_ids),
            },
            "stage_durations": ctx.stage_durations,
            "errors": ctx.errors,
            "warnings": ctx.warnings,
        }

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "stages": len(self._config.pipeline_stages),
            "config": {
                "max_factors": self._config.max_factors_per_generation,
                "max_alphas": self._config.max_alphas_per_generation,
            },
        }
