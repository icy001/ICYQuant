"""
Strategy Evolution Platform — Top-level orchestrator for strategy + portfolio evolution.

Lifecycle:
    Alpha Pool → Strategy Generator → Strategy Population
    → Strategy Evolution (mutate/crossover/validate)
    → Portfolio Builder → Portfolio Evolution
    → Allocation → Position → Risk Guard → Production Proposal
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


class EvolutionPhase(Enum):
    IDLE = "idle"
    GENERATING_STRATEGIES = "generating_strategies"
    EVOLVING_STRATEGIES = "evolving_strategies"
    BUILDING_PORTFOLIOS = "building_portfolios"
    OPTIMIZING_PORTFOLIOS = "optimizing_portfolios"
    VALIDATING = "validating"
    ALLOCATING = "allocating"
    STRESS_TESTING = "stress_testing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class EvolutionConfig:
    """Configuration for strategy + portfolio evolution."""

    # Strategy evolution
    max_strategy_generations: int = 50
    strategy_population_size: int = 200
    strategy_mutation_rate: float = 0.30
    strategy_crossover_rate: float = 0.35
    strategy_elite_fraction: float = 0.15

    # Portfolio
    max_portfolio_generations: int = 30
    portfolio_population_size: int = 100
    max_strategies_per_portfolio: int = 10
    portfolio_elite_fraction: float = 0.15

    # Allocation
    risk_budget_method: str = "risk_parity"
    max_leverage: float = 2.0
    max_position_pct: float = 0.15
    max_sector_concentration: float = 0.35
    max_strategy_correlation: float = 0.70

    # Validation
    require_walk_forward: bool = True
    require_regime_test: bool = True
    min_sharpe: float = 0.50
    max_drawdown_pct: float = 20.0
    min_capacity_million: float = 10.0

    # Budget
    max_compute_hours: float = 48.0
    max_backtests_per_run: int = 10000
    early_stopping_generations: int = 15


@dataclass
class EvolutionRun:
    """Tracks a complete strategy+portfolio evolution run."""

    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    config: EvolutionConfig = field(default_factory=EvolutionConfig)
    phase: EvolutionPhase = EvolutionPhase.IDLE
    current_strategy_gen: int = 0
    current_portfolio_gen: int = 0
    strategies_generated: int = 0
    strategies_mutated: int = 0
    strategies_crossed: int = 0
    strategies_promoted: int = 0
    strategies_rejected: int = 0
    portfolios_built: int = 0
    portfolios_optimized: int = 0
    portfolios_promoted: int = 0
    best_strategy_fitness: float = 0.0
    best_portfolio_fitness: float = 0.0
    compute_hours_used: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)
    generations: List[Dict[str, Any]] = field(default_factory=list)


class StrategyEvolutionPlatform:
    """
    Top-level orchestrator for strategy and portfolio evolution.

    Pipeline:
        Alpha Pool → Strategy Gen → Strategy Evolution
        → Portfolio Build → Portfolio Evolution
        → Allocation → Position → Validation → Promotion
    """

    def __init__(self, config: Optional[EvolutionConfig] = None):
        self._config = config or EvolutionConfig()
        self._runs: Dict[str, EvolutionRun] = {}
        self._active_run: Optional[EvolutionRun] = None

    async def start_run(self, config: Optional[EvolutionConfig] = None) -> EvolutionRun:
        if config:
            self._config = config
        run = EvolutionRun(config=self._config, started_at=datetime.now(timezone.utc))
        self._runs[run.run_id] = run
        self._active_run = run
        logger.info("Strategy evolution run %s started", run.run_id)
        return run

    async def run_full_evolution(self, alpha_ids: Optional[List[str]] = None) -> EvolutionRun:
        """Execute complete strategy→portfolio evolution."""
        run = await self.start_run()
        try:
            run.phase = EvolutionPhase.GENERATING_STRATEGIES
            await self._generate_strategies(run, alpha_ids)

            while run.current_strategy_gen < self._config.max_strategy_generations:
                run.phase = EvolutionPhase.EVOLVING_STRATEGIES
                await self._evolve_strategies(run)
                run.current_strategy_gen += 1
                if await self._should_early_stop(run):
                    break

            run.phase = EvolutionPhase.BUILDING_PORTFOLIOS
            await self._build_portfolios(run)

            while run.current_portfolio_gen < self._config.max_portfolio_generations:
                run.phase = EvolutionPhase.OPTIMIZING_PORTFOLIOS
                await self._optimize_portfolios(run)
                run.current_portfolio_gen += 1

            run.phase = EvolutionPhase.STRESS_TESTING
            await self._stress_test(run)

            run.phase = EvolutionPhase.COMPLETED
        except Exception as e:
            run.phase = EvolutionPhase.FAILED
            run.errors.append(str(e))
            logger.exception("Evolution run failed")
        finally:
            run.completed_at = datetime.now(timezone.utc)
        return run

    async def _generate_strategies(self, run: EvolutionRun, alpha_ids: Optional[List[str]]) -> None:
        run.strategies_generated = self._config.strategy_population_size
        logger.debug("Generated %d strategies", run.strategies_generated)

    async def _evolve_strategies(self, run: EvolutionRun) -> None:
        n_mutate = int(run.config.strategy_population_size * run.config.strategy_mutation_rate)
        n_crossover = int(run.config.strategy_population_size * run.config.strategy_crossover_rate)
        run.strategies_mutated += n_mutate
        run.strategies_crossed += n_crossover

    async def _build_portfolios(self, run: EvolutionRun) -> None:
        run.portfolios_built = self._config.portfolio_population_size

    async def _optimize_portfolios(self, run: EvolutionRun) -> None:
        run.portfolios_optimized += 1

    async def _stress_test(self, run: EvolutionRun) -> None:
        pass

    async def _should_early_stop(self, run: EvolutionRun) -> bool:
        if run.compute_hours_used >= run.config.max_compute_hours:
            return True
        return run.current_strategy_gen >= run.config.early_stopping_generations and run.best_strategy_fitness < 0.1

    @property
    def active_run(self) -> Optional[EvolutionRun]:
        return self._active_run

    async def health_check(self) -> Dict[str, Any]:
        return {"status": "healthy", "active_runs": len(self._runs)}
