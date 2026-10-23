"""Replay Engine package (Commit 012).

Replays the historical 1m series (Commit 008) through ICYQuant on a
virtual clock — deterministically, auditable, and without touching the
wall clock in the replay path.

The engine is a *source*, not a second market data system: it consumes an
existing ``HistoricalProvider``, synthesises no ticks and fills no gaps.
See :mod:`services.market_data.replay.replay_engine` for the invariants.

Import surface::

    from services.market_data.replay import (
        ReplayEngine,            # explicit instance (tests / DI)
        replay_engine,           # process-wide singleton
        ReplayClock,             # the virtual trading clock (§5)
        ReplayEvent,             # one replayed instant (§8)
        ReplayEventType,         # BAR | QUOTE
        ReplayMarketDataAdapter, # 001 contract + §17 Paper source
        ReplayConfig,            # env-driven settings (§6)
        ReplayState,             # §20 lifecycle
        ReplayRun,               # §24 audit record
        ReplayError,             # typed quarantine reasons
        ReplayBlockedError,      # typed refusal carrying a ReplayError
    )
"""
from __future__ import annotations

from .replay_adapter import ReplayMarketDataAdapter
from .replay_clock import ReplayClock
from .replay_config import SUPPORTED_TIMEFRAMES, ReplayConfig
from .replay_engine import ReplayEngine, replay_engine
from .replay_event import ReplayEvent, ReplayEventType
from .replay_state import (
    ReplayBlockedError,
    ReplayError,
    ReplayRun,
    ReplayState,
)

__all__ = [
    "ReplayEngine",
    "replay_engine",
    "ReplayClock",
    "ReplayEvent",
    "ReplayEventType",
    "ReplayMarketDataAdapter",
    "ReplayConfig",
    "SUPPORTED_TIMEFRAMES",
    "ReplayState",
    "ReplayError",
    "ReplayBlockedError",
    "ReplayRun",
]
