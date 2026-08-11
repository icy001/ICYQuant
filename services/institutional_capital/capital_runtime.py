"""
Capital Runtime — Lifecycle & Dependency Injection

The CapitalRuntime is the bootstrapper that wires all institutional capital
subsystems together. It manages the lifecycle of CapitalPool, StrategyPool,
PortfolioPool, AllocationOptimizer, EfficiencyAnalytics, ExposureEngine,
and Governance, and injects them into CapitalIntelligence.

Lifecycle:
    INIT → CONFIGURE → BOOTSTRAP → ACTIVE → PAUSE → SHUTDOWN
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class RuntimeState(str, Enum):
    """Capital runtime lifecycle states."""
    INIT = "INIT"
    CONFIGURING = "CONFIGURING"
    BOOTSTRAPPING = "BOOTSTRAPPING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    SHUTTING_DOWN = "SHUTTING_DOWN"
    TERMINATED = "TERMINATED"


@dataclass
class RuntimeContext:
    """Shared runtime context for all capital subsystems."""
    runtime_id: str
    started_at: datetime
    config: Dict[str, Any] = field(default_factory=dict)
    env: Dict[str, str] = field(default_factory=dict)
    flags: Dict[str, bool] = field(default_factory=dict)


class CapitalRuntime:
    """
    Bootstraps and manages all institutional capital subsystems.

    Responsibilities:
    - Load configuration
    - Instantiate all subsystems in correct dependency order
    - Wire them into CapitalIntelligence
    - Lifecycle management (start, pause, resume, shutdown)
    - Health checks for all subsystems
    """

    def __init__(
        self,
        runtime_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.runtime_id = runtime_id or f"cr-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self.state = RuntimeState.INIT
        self.context = RuntimeContext(
            runtime_id=self.runtime_id,
            started_at=datetime.utcnow(),
            config=self.config,
        )

        # Subsystem instances
        self._intelligence = None
        self._capital_pool = None
        self._strategy_pool = None
        self._portfolio_pool = None
        self._allocator = None
        self._efficiency = None
        self._exposure = None
        self._guard = None
        self._memory = None
        self._metrics = None
        self._telemetry = None
        self._diagnostics = None
        self._health = None

        # Control plane wiring
        self._control_plane = None

        self._boot_errors: List[Dict[str, Any]] = []
        logger.info(f"CapitalRuntime created: {self.runtime_id}")

    # ─── Lifecycle ──────────────────────────────────────────────

    def configure(self, config_overrides: Optional[Dict[str, Any]] = None) -> None:
        """Load and merge configuration."""
        self.state = RuntimeState.CONFIGURING
        if config_overrides:
            self.config.update(config_overrides)
        self.context.config = self.config

        # Resolution order: env vars > config file > defaults
        self._resolve_env_overrides()
        logger.info(f"Runtime {self.runtime_id} configured")

    def bootstrap(self) -> bool:
        """Instantiate and wire all subsystems in dependency order."""
        self.state = RuntimeState.BOOTSTRAPPING
        self._boot_errors.clear()

        try:
            # Phase 1: Foundation (no dependencies)
            self._bootstrap_foundation()

            # Phase 2: Pools (depend on foundation)
            self._bootstrap_pools()

            # Phase 3: Analytics (depend on pools)
            self._bootstrap_analytics()

            # Phase 4: Optimization (depends on analytics)
            self._bootstrap_optimizer()

            # Phase 5: Governance (depends on everything)
            self._bootstrap_governance()

            # Phase 6: Observability (depends on everything)
            self._bootstrap_observability()

            # Phase 7: Wire into intelligence
            self._wire_intelligence()

            self.state = RuntimeState.ACTIVE
            logger.info(f"Runtime {self.runtime_id} bootstrapped successfully")
            return True

        except Exception as e:
            self._boot_errors.append({
                "phase": self.state.value,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            })
            logger.error(f"Runtime {self.runtime_id} bootstrap failed: {e}")
            return False

    def _bootstrap_foundation(self) -> None:
        """Phase 1: Memory & metrics (no dependencies)."""
        from .capital_memory import CapitalMemory
        from .allocation_memory import AllocationMemory
        from .capacity_memory import CapacityMemory

        self._memory = CapitalMemory(
            memory_id=f"{self.runtime_id}-mem",
            retention_days=self.config.get("memory_retention_days", 365),
        )
        self._allocation_memory = AllocationMemory()
        self._capacity_memory = CapacityMemory()

    def _bootstrap_pools(self) -> None:
        """Phase 2: Capital, Strategy, Portfolio pools."""
        from .capital_pool import CapitalPool
        from .strategy_pool import StrategyPool
        from .portfolio_pool import PortfolioPool

        pool_config = self.config.get("capital_pool", {})
        self._capital_pool = CapitalPool(
            pool_id=f"{self.runtime_id}-cp",
            initial_capital=pool_config.get("initial_capital", 0.0),
            config=pool_config,
        )

        strategy_config = self.config.get("strategy_pool", {})
        self._strategy_pool = StrategyPool(
            pool_id=f"{self.runtime_id}-sp",
            config=strategy_config,
        )

        portfolio_config = self.config.get("portfolio_pool", {})
        self._portfolio_pool = PortfolioPool(
            pool_id=f"{self.runtime_id}-pp",
            config=portfolio_config,
        )

    def _bootstrap_analytics(self) -> None:
        """Phase 3: Efficiency & Exposure analytics."""
        from .capital_efficiency import CapitalEfficiency
        from .exposure_matrix import ExposureMatrix

        self._efficiency = CapitalEfficiency(
            efficiency_id=f"{self.runtime_id}-eff",
            capital_pool=self._capital_pool,
            strategy_pool=self._strategy_pool,
        )

        self._exposure = ExposureMatrix(
            matrix_id=f"{self.runtime_id}-exp",
            strategy_pool=self._strategy_pool,
        )

    def _bootstrap_optimizer(self) -> None:
        """Phase 4: Allocation optimizer."""
        from .allocation_optimizer import AllocationOptimizer

        self._allocator = AllocationOptimizer(
            optimizer_id=f"{self.runtime_id}-opt",
            capital_pool=self._capital_pool,
            strategy_pool=self._strategy_pool,
            efficiency=self._efficiency,
            exposure=self._exposure,
            config=self.config.get("optimizer", {}),
        )

    def _bootstrap_governance(self) -> None:
        """Phase 5: Capital guard & decision governance."""
        from .capital_guard import CapitalGuard

        self._guard = CapitalGuard(
            guard_id=f"{self.runtime_id}-guard",
            capital_pool=self._capital_pool,
            config=self.config.get("guard", {}),
        )

    def _bootstrap_observability(self) -> None:
        """Phase 6: Metrics, telemetry, diagnostics, health."""
        from .metrics import InstitutionalCapitalMetrics
        from .telemetry import InstitutionalCapitalTelemetry
        from .diagnostics import InstitutionalCapitalDiagnostics
        from .health import InstitutionalCapitalHealth

        self._metrics = InstitutionalCapitalMetrics(
            metrics_id=f"{self.runtime_id}-metrics",
        )
        self._telemetry = InstitutionalCapitalTelemetry(
            telemetry_id=f"{self.runtime_id}-telemetry",
        )
        self._diagnostics = InstitutionalCapitalDiagnostics(
            diagnostics_id=f"{self.runtime_id}-diag",
        )
        self._health = InstitutionalCapitalHealth(
            health_id=f"{self.runtime_id}-health",
        )

    def _wire_intelligence(self) -> None:
        """Phase 7: Wire all subsystems into CapitalIntelligence."""
        from .capital_intelligence import CapitalIntelligence

        self._intelligence = CapitalIntelligence(
            intelligence_id=self.runtime_id,
            config=self.config,
        )
        self._intelligence._capital_pool = self._capital_pool
        self._intelligence._strategy_pool = self._strategy_pool
        self._intelligence._portfolio_pool = self._portfolio_pool
        self._intelligence._allocator = self._allocator
        self._intelligence._efficiency = self._efficiency
        self._intelligence._guard = self._guard
        self._intelligence._memory = self._memory
        self._intelligence.initialize()

    def _resolve_env_overrides(self) -> None:
        """Override config with environment variables."""
        import os
        prefix = "ICYQUANT_CAPITAL_"
        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix):].lower()
                # Try to coerce types
                try:
                    self.config[config_key] = float(value)
                except ValueError:
                    if value.lower() in ("true", "false"):
                        self.config[config_key] = value.lower() == "true"
                    else:
                        self.config[config_key] = value

    # ─── State Management ───────────────────────────────────────

    def pause(self) -> None:
        """Pause capital operations (no new allocations)."""
        self.state = RuntimeState.PAUSED
        if self._intelligence:
            self._intelligence.freeze()
        logger.warning(f"Runtime {self.runtime_id} PAUSED")

    def resume(self) -> None:
        """Resume capital operations."""
        self.state = RuntimeState.ACTIVE
        if self._intelligence:
            self._intelligence.unfreeze()
        logger.info(f"Runtime {self.runtime_id} RESUMED")

    def shutdown(self) -> None:
        """Graceful shutdown."""
        self.state = RuntimeState.SHUTTING_DOWN
        if self._intelligence:
            self._intelligence.shutdown()
        # Persist state
        if self._memory:
            self._memory.flush()
        self.state = RuntimeState.TERMINATED
        logger.info(f"Runtime {self.runtime_id} terminated")

    # ─── Accessors ──────────────────────────────────────────────

    @property
    def intelligence(self):
        """Get the wired CapitalIntelligence instance."""
        return self._intelligence

    @property
    def is_healthy(self) -> bool:
        """Quick health check."""
        if not self._health:
            return False
        return self._health.check_basic()

    def get_boot_errors(self) -> List[Dict[str, Any]]:
        """Get bootstrap errors."""
        return list(self._boot_errors)

    def get_status(self) -> Dict[str, Any]:
        """Get detailed runtime status."""
        return {
            "runtime_id": self.runtime_id,
            "state": self.state.value,
            "uptime_seconds": (
                (datetime.utcnow() - self.context.started_at).total_seconds()
                if self.context.started_at else 0
            ),
            "boot_errors": len(self._boot_errors),
            "subsystems": {
                "capital_pool": self._capital_pool is not None,
                "strategy_pool": self._strategy_pool is not None,
                "portfolio_pool": self._portfolio_pool is not None,
                "allocator": self._allocator is not None,
                "efficiency": self._efficiency is not None,
                "exposure": self._exposure is not None,
                "guard": self._guard is not None,
                "memory": self._memory is not None,
                "metrics": self._metrics is not None,
                "telemetry": self._telemetry is not None,
                "diagnostics": self._diagnostics is not None,
                "health": self._health is not None,
                "intelligence": self._intelligence is not None,
            },
            "healthy": self.is_healthy,
        }
