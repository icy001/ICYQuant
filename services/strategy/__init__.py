"""
Production Strategy Platform.

The unified platform for managing, deploying, and executing production
trading strategies with full lifecycle management, versioning, snapshotting,
and recovery.

Architecture:
    StrategyEngine (unified entry)
        ├── StrategyManager (coordination)
        │       ├── StrategyRegistry (registration)
        │       ├── StrategyRepository (persistence)
        │       ├── StrategyFactory (instantiation)
        │       └── StrategyLoader (package loading)
        ├── StrategyRuntime (execution sandbox)
        ├── StrategyLifecycle (state machine)
        ├── StrategyScheduler (trigger management)
        ├── StrategyValidator (pre-deployment checks)
        ├── StrategySnapshot (state preservation)
        └── StrategyRecovery (failure recovery)
"""

from __future__ import annotations

from .strategy_engine import StrategyEngine
from .strategy_manager import StrategyManager
from .strategy_runtime import StrategyRuntime
from .strategy_snapshot import StrategySnapshot, SnapshotManager
from .strategy_recovery import StrategyRecovery

__all__ = [
    "StrategyEngine",
    "StrategyManager",
    "StrategyRuntime",
    "StrategySnapshot",
    "SnapshotManager",
    "StrategyRecovery",
]

# -- auto-restored exports (test-collection repair) --
from services.strategy.duplicate import DuplicateSignalValidator
from services.strategy.order_mapper import OrderMapper
from services.strategy.position_sizer import PositionSizer
from services.strategy.generator import SignalGenerator
from services.strategy.enums import SignalType
from services.strategy.context import StrategyContext
