"""
Evolution Gateway — Unified API entry point for alpha evolution.

Provides a single interface for:
    - Starting and managing evolution runs
    - Submitting factor/alpha candidates
    - Querying population, fitness, and generation status
    - Retrieving elite candidates and Pareto frontier
    - Managing evolution memory and archives
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.alpha_evolution.evolution_platform import (
    EvolutionConfig,
    EvolutionPlatform,
    EvolutionRun,
)

logger = logging.getLogger(__name__)


@dataclass
class EvolutionRequest:
    """Incoming evolution request."""

    request_type: str  # "start_run", "evolve", "promote", "query", "stop"
    config: Optional[EvolutionConfig] = None
    filters: Dict[str, Any] = field(default_factory=dict)
    limit: int = 50


@dataclass
class EvolutionResponse:
    """Standard evolution response."""

    success: bool
    data: Any = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class EvolutionGateway:
    """
    Unified API gateway for the Alpha Evolution Engine.

    Usage:
        gateway = EvolutionGateway()
        await gateway.start_run(config)
        result = await gateway.get_elite_candidates()
        status = await gateway.get_status()
    """

    def __init__(self):
        self._platform = EvolutionPlatform()

    # ── Run Management ─────────────────────────────────────

    async def start_run(
        self, config: Optional[EvolutionConfig] = None
    ) -> EvolutionResponse:
        """Start a new evolution run."""
        try:
            run = await self._platform.start_run(config)
            return EvolutionResponse(
                success=True,
                data={
                    "run_id": run.run_id,
                    "status": run.status.value,
                    "config": {
                        "population_size": run.config.population_size,
                        "max_generations": run.config.max_generations,
                    },
                },
            )
        except Exception as e:
            logger.exception("Failed to start evolution run")
            return EvolutionResponse(success=False, error=str(e))

    async def run_full_evolution(
        self, config: Optional[EvolutionConfig] = None
    ) -> EvolutionResponse:
        """Execute a complete evolution cycle."""
        try:
            run = await self._platform.run_full_evolution(config)
            return EvolutionResponse(
                success=True,
                data={
                    "run_id": run.run_id,
                    "status": run.status.value,
                    "generations": run.current_generation,
                    "best_fitness": run.best_fitness,
                    "total_promoted": run.total_promoted,
                    "pareto_size": run.pareto_frontier_size,
                    "compute_hours": run.compute_hours_used,
                },
            )
        except Exception as e:
            logger.exception("Full evolution run failed")
            return EvolutionResponse(success=False, error=str(e))

    async def pause_run(self) -> EvolutionResponse:
        """Pause the active evolution run."""
        try:
            run = await self._platform.pause_run()
            return EvolutionResponse(
                success=True, data={"run_id": run.run_id, "status": run.status.value}
            )
        except Exception as e:
            return EvolutionResponse(success=False, error=str(e))

    async def resume_run(self) -> EvolutionResponse:
        """Resume a paused evolution run."""
        try:
            run = await self._platform.resume_run()
            return EvolutionResponse(
                success=True, data={"run_id": run.run_id, "status": run.status.value}
            )
        except Exception as e:
            return EvolutionResponse(success=False, error=str(e))

    # ── Query Methods ──────────────────────────────────────

    async def get_status(self) -> EvolutionResponse:
        """Get current evolution run status."""
        run = self._platform.active_run
        if not run:
            return EvolutionResponse(
                success=True, data={"active": False, "message": "No active run"}
            )
        return EvolutionResponse(
            success=True,
            data={
                "active": True,
                "run_id": run.run_id,
                "status": run.status.value,
                "generation": run.current_generation,
                "best_fitness": run.best_fitness,
                "pipeline": {
                    "total_generated": run.total_alphas_generated,
                    "total_mutations": run.total_mutations,
                    "total_crossovers": run.total_crossovers,
                    "total_validated": run.total_validated,
                    "total_promoted": run.total_promoted,
                    "total_rejected": run.total_rejected,
                    "total_redundant": run.total_redundant,
                },
                "population": {
                    "size": run.config.population_size,
                    "diversity": run.population_diversity,
                    "pareto_size": run.pareto_frontier_size,
                },
            },
        )

    async def get_elite_candidates(
        self, limit: int = 10, min_fitness: float = 0.0
    ) -> EvolutionResponse:
        """Retrieve top-performing candidates (Pareto frontier)."""
        # Placeholder — in production, queries candidate_archive
        return EvolutionResponse(
            success=True,
            data={
                "candidates": [],
                "count": 0,
                "pareto_frontier_size": 0,
            },
        )

    async def get_generation_history(
        self, run_id: Optional[str] = None, limit: int = 50
    ) -> EvolutionResponse:
        """Get generation-level history for a run."""
        run = self._platform.get_run(run_id) if run_id else self._platform.active_run
        if not run:
            return EvolutionResponse(success=False, error="Run not found")
        return EvolutionResponse(
            success=True,
            data={
                "run_id": run.run_id,
                "generations": run.generations[-limit:],
                "total_generations": len(run.generations),
            },
        )

    async def query_population(
        self, filters: Optional[Dict[str, Any]] = None, limit: int = 100
    ) -> EvolutionResponse:
        """Query the current population with filters."""
        return EvolutionResponse(
            success=True,
            data={"individuals": [], "total": 0, "filters": filters or {}},
        )

    # ── Candidate Management ───────────────────────────────

    async def submit_seed_candidate(
        self, candidate_data: Dict[str, Any]
    ) -> EvolutionResponse:
        """Submit an externally-discovered candidate as evolution seed."""
        return EvolutionResponse(
            success=True,
            data={"candidate_id": "", "status": "accepted", "message": "Seed candidate registered"},
        )

    async def promote_candidate(
        self, candidate_id: str
    ) -> EvolutionResponse:
        """Request promotion of a candidate to production candidate."""
        return EvolutionResponse(
            success=True,
            data={
                "candidate_id": candidate_id,
                "status": "pending_approval",
                "message": "Promotion requires human approval",
            },
        )

    # ── Memory Queries ─────────────────────────────────────

    async def get_failure_memory(
        self, query: Optional[str] = None, limit: int = 50
    ) -> EvolutionResponse:
        """Query the failure memory for past rejected alphas."""
        return EvolutionResponse(
            success=True,
            data={"failures": [], "total": 0, "query": query},
        )

    async def get_evolution_lineage(
        self, alpha_id: str, depth: int = 5
    ) -> EvolutionResponse:
        """Trace the evolutionary lineage of an alpha."""
        return EvolutionResponse(
            success=True,
            data={
                "alpha_id": alpha_id,
                "depth": depth,
                "ancestors": [],
                "descendants": [],
            },
        )

    # ── Health ─────────────────────────────────────────────

    async def health_check(self) -> EvolutionResponse:
        """Platform health check."""
        return EvolutionResponse(
            success=True,
            data={
                "status": "healthy",
                "platform": "alpha_evolution",
                "version": "0.1.0",
            },
        )
