"""
Evolution Manager — Lifecycle manager for evolution subsystems.

Manages initialization, coordination, and teardown of:
    - Population Manager
    - Mutation Engine
    - Crossover Engine
    - Fitness Engine
    - Selection Engine
    - Diversity Engine
    - Validation pipeline
    - Memory subsystems
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SubsystemStatus(Enum):
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    DEGRADED = "degraded"
    ERROR = "error"
    SHUTDOWN = "shutdown"


@dataclass
class SubsystemInfo:
    name: str
    status: SubsystemStatus = SubsystemStatus.UNINITIALIZED
    last_heartbeat: Optional[datetime] = None
    error_count: int = 0
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ManagerConfig:
    """Configuration for the evolution manager."""

    enable_mutation: bool = True
    enable_crossover: bool = True
    enable_diversity: bool = True
    enable_novelty: bool = True
    enable_robustness: bool = True
    enable_regime_validation: bool = True
    enable_memory: bool = True
    enable_lineage: bool = True
    health_check_interval_sec: int = 30


class EvolutionManager:
    """
    Lifecycle manager for all evolution subsystems.

    Responsibilities:
        - Initialize subsystems in dependency order
        - Health monitoring and heartbeat
        - Graceful shutdown
        - Subsystem status reporting
    """

    def __init__(self, config: Optional[ManagerConfig] = None):
        self._config = config or ManagerConfig()
        self._subsystems: Dict[str, SubsystemInfo] = {}
        self._initialized = False

        # Define subsystem registry
        self._register_subsystem("population_manager")
        self._register_subsystem("mutation_engine")
        self._register_subsystem("crossover_engine")
        self._register_subsystem("factor_composer")
        self._register_subsystem("alpha_composer")
        self._register_subsystem("fitness_engine")
        self._register_subsystem("selection_engine")
        self._register_subsystem("diversity_engine")
        self._register_subsystem("novelty_engine")
        self._register_subsystem("redundancy_detector")
        self._register_subsystem("robustness_validator")
        self._register_subsystem("stability_validator")
        self._register_subsystem("regime_validator")
        self._register_subsystem("alpha_memory")
        self._register_subsystem("failure_memory")
        self._register_subsystem("evolution_memory")
        self._register_subsystem("candidate_archive")
        self._register_subsystem("lineage_tracker")
        self._register_subsystem("compute_budget")
        self._register_subsystem("risk_guard")
        self._register_subsystem("promotion_gate")

    def _register_subsystem(self, name: str) -> SubsystemInfo:
        info = SubsystemInfo(name=name)
        self._subsystems[name] = info
        return info

    # ── Lifecycle ──────────────────────────────────────────

    async def initialize(self) -> None:
        """Initialize all subsystems in dependency order."""
        logger.info("Initializing EvolutionManager with %d subsystems", len(self._subsystems))

        init_order = [
            "compute_budget",
            "alpha_memory",
            "failure_memory",
            "evolution_memory",
            "candidate_archive",
            "lineage_tracker",
            "population_manager",
            "mutation_engine",
            "crossover_engine",
            "factor_composer",
            "alpha_composer",
            "fitness_engine",
            "selection_engine",
            "diversity_engine",
            "novelty_engine",
            "redundancy_detector",
            "robustness_validator",
            "stability_validator",
            "regime_validator",
            "risk_guard",
            "promotion_gate",
        ]

        for name in init_order:
            if name in self._subsystems:
                await self._init_subsystem(name)

        self._initialized = True
        logger.info("EvolutionManager initialized successfully")

    async def _init_subsystem(self, name: str) -> None:
        info = self._subsystems[name]
        info.status = SubsystemStatus.INITIALIZING
        try:
            info.status = SubsystemStatus.READY
            info.last_heartbeat = datetime.now(timezone.utc)
            logger.debug("Subsystem %s initialized", name)
        except Exception as e:
            info.status = SubsystemStatus.ERROR
            info.error_count += 1
            logger.error("Failed to initialize subsystem %s: %s", name, e)
            raise

    async def shutdown(self) -> None:
        """Gracefully shut down all subsystems."""
        logger.info("Shutting down EvolutionManager")
        for name, info in reversed(list(self._subsystems.items())):
            info.status = SubsystemStatus.SHUTDOWN
        self._initialized = False

    # ── Health ─────────────────────────────────────────────

    async def health_check(self) -> Dict[str, Any]:
        """Check health of all subsystems."""
        ready = sum(
            1 for s in self._subsystems.values()
            if s.status == SubsystemStatus.READY
        )
        degraded = sum(
            1 for s in self._subsystems.values()
            if s.status == SubsystemStatus.DEGRADED
        )
        errored = sum(
            1 for s in self._subsystems.values()
            if s.status == SubsystemStatus.ERROR
        )

        overall = "healthy" if errored == 0 and degraded == 0 else "degraded"

        return {
            "status": overall,
            "subsystems": {
                name: {
                    "status": info.status.value,
                    "error_count": info.error_count,
                    "last_heartbeat": info.last_heartbeat.isoformat()
                    if info.last_heartbeat
                    else None,
                }
                for name, info in self._subsystems.items()
            },
            "summary": {"ready": ready, "degraded": degraded, "errored": errored},
        }

    # ── Accessors ──────────────────────────────────────────

    def get_subsystem_status(self, name: str) -> Optional[SubsystemInfo]:
        return self._subsystems.get(name)

    def list_subsystems(self) -> List[Dict[str, str]]:
        return [
            {"name": name, "status": info.status.value}
            for name, info in self._subsystems.items()
        ]

    @property
    def is_initialized(self) -> bool:
        return self._initialized
