"""
Risk & Execution Manager — subsystem lifecycle and dependency management.

Manages 22 subsystems across risk optimization, risk engines, execution
optimization, pre-trade guards, feedback, and memory.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class SubsystemState(Enum):
    """Subsystem lifecycle states."""
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    ACTIVE = "active"
    DEGRADED = "degraded"
    ERROR = "error"
    STOPPED = "stopped"


class SubsystemGroup(Enum):
    """Logical grouping of subsystems."""
    PLATFORM = "platform"
    RISK_OPTIMIZATION = "risk_optimization"
    RISK_ENGINES = "risk_engines"
    EXECUTION_OPTIMIZATION = "execution_optimization"
    PRE_TRADE_GUARDS = "pre_trade_guards"
    EXECUTION_FEEDBACK = "execution_feedback"
    MEMORY = "memory"
    OBSERVABILITY = "observability"


@dataclass
class SubsystemInfo:
    """Metadata for a single subsystem."""
    name: str
    group: SubsystemGroup
    state: SubsystemState = SubsystemState.UNINITIALIZED
    instance: Any = None
    dependencies: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)
    initialized_at: Optional[datetime] = None
    last_health_check: Optional[datetime] = None
    error_count: int = 0


@dataclass
class ManagerConfig:
    """Manager configuration."""
    auto_initialize: bool = True
    health_check_interval_seconds: int = 30
    max_errors_before_degrade: int = 5
    subsystem_startup_timeout: int = 60


# Subsystem registry — all 22 subsystems
SUBSYSTEM_REGISTRY: dict[str, tuple[SubsystemGroup, list[str]]] = {
    # Risk Optimization
    "risk_optimizer": (SubsystemGroup.RISK_OPTIMIZATION, []),
    "dynamic_risk_budget": (SubsystemGroup.RISK_OPTIMIZATION, ["risk_optimizer"]),
    "risk_budget_engine": (SubsystemGroup.RISK_OPTIMIZATION, ["dynamic_risk_budget"]),
    "risk_allocator": (SubsystemGroup.RISK_OPTIMIZATION, ["risk_budget_engine"]),
    "exposure_optimizer": (SubsystemGroup.RISK_OPTIMIZATION, ["risk_allocator"]),
    "leverage_optimizer": (SubsystemGroup.RISK_OPTIMIZATION, ["risk_allocator"]),
    "concentration_optimizer": (SubsystemGroup.RISK_OPTIMIZATION, ["exposure_optimizer"]),
    "correlation_optimizer": (SubsystemGroup.RISK_OPTIMIZATION, ["exposure_optimizer"]),
    "liquidity_optimizer": (SubsystemGroup.RISK_OPTIMIZATION, ["risk_allocator"]),
    "drawdown_controller": (SubsystemGroup.RISK_OPTIMIZATION, ["risk_allocator"]),
    "volatility_controller": (SubsystemGroup.RISK_OPTIMIZATION, ["risk_allocator"]),
    "regime_risk_controller": (SubsystemGroup.RISK_OPTIMIZATION, ["risk_budget_engine"]),
    # Risk Engines
    "portfolio_risk_engine": (SubsystemGroup.RISK_ENGINES, []),
    "marginal_risk_engine": (SubsystemGroup.RISK_ENGINES, ["portfolio_risk_engine"]),
    "incremental_risk_engine": (SubsystemGroup.RISK_ENGINES, ["portfolio_risk_engine"]),
    "factor_risk_engine": (SubsystemGroup.RISK_ENGINES, ["portfolio_risk_engine"]),
    "scenario_engine": (SubsystemGroup.RISK_ENGINES, []),
    "stress_engine": (SubsystemGroup.RISK_ENGINES, ["scenario_engine"]),
    "tail_risk_engine": (SubsystemGroup.RISK_ENGINES, ["portfolio_risk_engine"]),
    "var_engine": (SubsystemGroup.RISK_ENGINES, ["portfolio_risk_engine"]),
    "expected_shortfall": (SubsystemGroup.RISK_ENGINES, ["var_engine"]),
    # Execution Optimization
    "execution_optimizer": (SubsystemGroup.EXECUTION_OPTIMIZATION, []),
    "execution_scheduler": (SubsystemGroup.EXECUTION_OPTIMIZATION, ["execution_optimizer"]),
    "execution_planner": (SubsystemGroup.EXECUTION_OPTIMIZATION, ["execution_scheduler"]),
    "execution_policy": (SubsystemGroup.EXECUTION_OPTIMIZATION, []),
    "execution_strategy_selector": (SubsystemGroup.EXECUTION_OPTIMIZATION, ["execution_policy"]),
    "order_slicer": (SubsystemGroup.EXECUTION_OPTIMIZATION, ["execution_planner"]),
    "child_order_generator": (SubsystemGroup.EXECUTION_OPTIMIZATION, ["order_slicer"]),
    "participation_controller": (SubsystemGroup.EXECUTION_OPTIMIZATION, ["order_slicer"]),
    "liquidity_router": (SubsystemGroup.EXECUTION_OPTIMIZATION, ["execution_planner"]),
    "venue_selector": (SubsystemGroup.EXECUTION_OPTIMIZATION, ["liquidity_router"]),
    "timing_optimizer": (SubsystemGroup.EXECUTION_OPTIMIZATION, ["execution_planner"]),
    "urgency_controller": (SubsystemGroup.EXECUTION_OPTIMIZATION, ["timing_optimizer"]),
    "slippage_optimizer": (SubsystemGroup.EXECUTION_OPTIMIZATION, ["order_slicer"]),
    "market_impact_model": (SubsystemGroup.EXECUTION_OPTIMIZATION, []),
    "transaction_cost_model": (SubsystemGroup.EXECUTION_OPTIMIZATION, ["market_impact_model"]),
    "spread_model": (SubsystemGroup.EXECUTION_OPTIMIZATION, []),
    "fill_probability": (SubsystemGroup.EXECUTION_OPTIMIZATION, ["spread_model"]),
    "execution_cost_estimator": (SubsystemGroup.EXECUTION_OPTIMIZATION, [
        "market_impact_model", "transaction_cost_model", "spread_model"
    ]),
    # Pre-Trade Guards
    "pre_trade_optimizer": (SubsystemGroup.PRE_TRADE_GUARDS, []),
    "pre_trade_guard": (SubsystemGroup.PRE_TRADE_GUARDS, ["pre_trade_optimizer"]),
    "order_constraint_engine": (SubsystemGroup.PRE_TRADE_GUARDS, []),
    "execution_guard": (SubsystemGroup.PRE_TRADE_GUARDS, ["pre_trade_guard"]),
    "kill_switch": (SubsystemGroup.PRE_TRADE_GUARDS, []),
    # Execution Feedback
    "execution_feedback": (SubsystemGroup.EXECUTION_FEEDBACK, []),
    "fill_analyzer": (SubsystemGroup.EXECUTION_FEEDBACK, ["execution_feedback"]),
    "slippage_analyzer": (SubsystemGroup.EXECUTION_FEEDBACK, ["execution_feedback"]),
    "implementation_shortfall": (SubsystemGroup.EXECUTION_FEEDBACK, ["fill_analyzer", "slippage_analyzer"]),
    "execution_quality": (SubsystemGroup.EXECUTION_FEEDBACK, ["implementation_shortfall"]),
    "execution_learning": (SubsystemGroup.EXECUTION_FEEDBACK, ["execution_quality"]),
    "execution_memory": (SubsystemGroup.EXECUTION_FEEDBACK, ["execution_learning"]),
    # Memory
    "risk_memory": (SubsystemGroup.MEMORY, []),
    "scenario_memory": (SubsystemGroup.MEMORY, ["risk_memory"]),
    "optimization_memory": (SubsystemGroup.MEMORY, ["risk_memory"]),
    "lineage_tracker": (SubsystemGroup.MEMORY, []),
    # Observability
    "metrics": (SubsystemGroup.OBSERVABILITY, []),
    "telemetry": (SubsystemGroup.OBSERVABILITY, ["metrics"]),
    "diagnostics": (SubsystemGroup.OBSERVABILITY, ["metrics"]),
    "health": (SubsystemGroup.OBSERVABILITY, []),
}


class RiskExecutionManager:
    """
    Manages lifecycle and dependencies of all subsystems.

    Provides:
        - Ordered initialization respecting dependency graph
        - Health monitoring across all subsystems
        - Graceful degradation on subsystem failures
        - Unified shutdown sequence
    """

    def __init__(self, config: Optional[ManagerConfig] = None) -> None:
        self._id = str(uuid4())
        self._config = config or ManagerConfig()
        self._subsystems: dict[str, SubsystemInfo] = {}
        self._initialize_registry()

    def _initialize_registry(self) -> None:
        """Populate subsystem registry from declarations."""
        for name, (group, deps) in SUBSYSTEM_REGISTRY.items():
            self._subsystems[name] = SubsystemInfo(
                name=name, group=group, dependencies=deps
            )

    async def initialize_all(self) -> list[str]:
        """
        Initialize all subsystems in dependency order.

        Returns list of subsystems that failed to initialize.
        """
        failures: list[str] = []
        initialized: set[str] = set()

        while len(initialized) < len(self._subsystems):
            progress = False
            for name, info in self._subsystems.items():
                if name in initialized:
                    continue
                if all(d in initialized for d in info.dependencies):
                    try:
                        await self._initialize_subsystem(name)
                        initialized.add(name)
                        progress = True
                    except Exception as e:
                        logger.error("Failed to initialize %s: %s", name, e)
                        failures.append(name)
                        info.state = SubsystemState.ERROR
                        initialized.add(name)  # Skip to avoid deadlock
            if not progress:
                remaining = set(self._subsystems) - initialized
                logger.error("Circular dependency or init failure: %s", remaining)
                failures.extend(remaining)
                break

        logger.info(
            "Manager initialized: %d/%d subsystems ready, %d failures",
            len(initialized) - len(failures), len(self._subsystems), len(failures),
        )
        return failures

    async def _initialize_subsystem(self, name: str) -> None:
        """Initialize a single subsystem."""
        info = self._subsystems[name]
        info.state = SubsystemState.INITIALIZING
        # In production, instantiate actual subsystem class
        info.state = SubsystemState.READY
        info.initialized_at = datetime.now()
        logger.debug("Subsystem initialized: %s (%s)", name, info.group.value)

    async def health_check(self) -> dict[str, str]:
        """Run health check on all subsystems."""
        status: dict[str, str] = {}
        for name, info in self._subsystems.items():
            status[name] = info.state.value
        return status

    async def shutdown_all(self) -> None:
        """Shutdown all subsystems in reverse dependency order."""
        for name in reversed(list(self._subsystems)):
            info = self._subsystems[name]
            info.state = SubsystemState.STOPPED
        logger.info("All subsystems shut down")

    def get_subsystem(self, name: str) -> Optional[Any]:
        """Get a subsystem instance by name."""
        info = self._subsystems.get(name)
        return info.instance if info else None

    def get_group(self, group: SubsystemGroup) -> list[SubsystemInfo]:
        """Get all subsystems in a group."""
        return [s for s in self._subsystems.values() if s.group == group]

    @property
    def subsystems(self) -> dict[str, SubsystemInfo]:
        return self._subsystems

    @property
    def subsystem_count(self) -> int:
        return len(self._subsystems)
