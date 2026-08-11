"""
Strategy Manager — central coordination layer for the Production Strategy Platform.

The StrategyManager sits between the StrategyEngine and individual subsystems,
providing coordinated operations that span the registry, runtime, scheduler,
loader, and snapshot components.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ManagerEventType(str, Enum):
    """Events emitted by the StrategyManager."""
    STRATEGY_LOADED = "strategy.loaded"
    STRATEGY_REGISTERED = "strategy.registered"
    STRATEGY_DEPLOYED = "strategy.deployed"
    STRATEGY_STARTED = "strategy.started"
    STRATEGY_STOPPED = "strategy.stopped"
    STRATEGY_PAUSED = "strategy.paused"
    STRATEGY_RESUMED = "strategy.resumed"
    STRATEGY_FAILED = "strategy.failed"
    STRATEGY_SNAPSHOTED = "strategy.snapshoted"
    STRATEGY_RECOVERED = "strategy.recovered"


@dataclass
class ManagerEvent:
    """An event raised by the StrategyManager."""
    event_type: ManagerEventType
    strategy_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = ""


class StrategyManager:
    """Central coordinator for strategy operations.

    Coordinates between:
        - StrategyRegistry    (registration & discovery)
        - StrategyRepository  (persistence)
        - StrategyRuntime     (execution sandbox)
        - StrategyScheduler   (trigger management)
        - StrategyLoader      (package loading)
        - SnapshotManager     (state preservation)

    Usage:
        manager = StrategyManager()
        manager.registry = registry
        manager.runtime = runtime
        await manager._init_dependencies()
    """

    def __init__(self) -> None:
        # Sub-system references (wired by StrategyEngine)
        self.registry: Any = None
        self.repository: Any = None
        self.runtime: Any = None
        self.scheduler: Any = None
        self.loader: Any = None
        self.snapshot_manager: Any = None

        self._initialized: bool = False
        self._event_listeners: Dict[str, List[Any]] = {}
        self._managed_strategies: Set[str] = set()
        logger.info("StrategyManager created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        self._initialized = True
        logger.info("StrategyManager initialized")

    async def shutdown(self) -> None:
        self._managed_strategies.clear()
        self._event_listeners.clear()
        self._initialized = False
        logger.info("StrategyManager shut down")

    async def _init_dependencies(self) -> None:
        """Wire internal dependencies after engine wires subsystem refs."""
        logger.info("StrategyManager dependencies wired")

    # ── Event Emitter ──

    def _emit(self, event_type: ManagerEventType, strategy_id: str, **data: Any) -> None:
        """Emit a manager event to registered listeners."""
        event = ManagerEvent(event_type=event_type, strategy_id=strategy_id, data=data)
        for listeners in self._event_listeners.values():
            for listener in listeners:
                try:
                    listener(event)
                except Exception as e:
                    logger.error("Event listener error: %s", e)

    def on(self, event_type: str, listener: Any) -> None:
        """Register an event listener."""
        self._event_listeners.setdefault(event_type, []).append(listener)

    # ── Strategy Counts ──

    @property
    def total_strategies(self) -> int:
        if self.registry:
            return self.registry.count
        return 0

    @property
    def active_strategies(self) -> int:
        if self.registry:
            return self.registry.active_count
        return 0

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_strategies": self.total_strategies,
            "active_strategies": self.active_strategies,
            "managed_strategies": len(self._managed_strategies),
            "event_listeners": len(self._event_listeners),
            "initialized": self._initialized,
        }
