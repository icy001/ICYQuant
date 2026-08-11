"""
Paper Runtime
=============
Runtime configuration and lifecycle management for paper trading sessions.

Controls:
    - Session scheduling (start/end times)
    - Market data feed selection
    - Execution simulation parameters
    - Account and portfolio initialization
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RuntimeMode(str, Enum):
    """Paper trading runtime mode."""
    REPLAY = "replay"          # Historical data replay
    LIVE_SIM = "live_sim"      # Live market data, simulated execution
    BACKTEST = "backtest"      # Backtest-style simulation


@dataclass
class PaperConfig:
    """Configuration for a paper trading runtime."""
    mode: RuntimeMode = RuntimeMode.REPLAY
    initial_capital: float = 100_000.0
    base_currency: str = "USD"
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    slippage_model: str = "fixed"       # fixed / volume / atr / orderbook
    slippage_bps: float = 5.0
    commission_schedule: str = "default"
    latency_profile: str = "zero"       # zero / low / medium / high
    liquidity_model: str = "full"       # full / partial / realistic
    market_impact_model: str = "linear" # linear / sqrt / kissell
    enable_logging: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class PaperRuntime:
    """Runtime manager for paper trading sessions.

    Manages configuration, scheduling, and lifecycle for paper trading runs.
    """

    def __init__(self):
        self._config: Optional[PaperConfig] = None
        self._sessions: Dict[str, "PaperSession"] = {}
        self._is_running: bool = False
        self._started_at: Optional[datetime] = None
        self._stopped_at: Optional[datetime] = None
        self.is_initialized = False

    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize runtime with optional config override."""
        if config:
            self._config = PaperConfig(**{
                k: v for k, v in config.items()
                if k in PaperConfig.__dataclass_fields__
            })
        else:
            self._config = PaperConfig()
        self.is_initialized = True
        logger.info("PaperRuntime initialized (mode=%s, capital=%s)",
                     self._config.mode.value, self._config.initial_capital)

    async def start(self) -> None:
        """Start the paper trading runtime."""
        self._is_running = True
        self._started_at = datetime.now(timezone.utc)
        logger.info("PaperRuntime started")

    async def stop(self) -> None:
        """Stop the paper trading runtime."""
        self._is_running = False
        self._stopped_at = datetime.now(timezone.utc)
        logger.info("PaperRuntime stopped")

    @property
    def config(self) -> Optional[PaperConfig]:
        return self._config

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def uptime_seconds(self) -> float:
        if not self._started_at:
            return 0.0
        end = self._stopped_at or datetime.now(timezone.utc)
        return (end - self._started_at).total_seconds()

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "mode": self._config.mode.value if self._config else "unknown",
            "is_running": self._is_running,
            "uptime_seconds": self.uptime_seconds,
            "active_sessions": len(self._sessions),
            "initial_capital": self._config.initial_capital if self._config else 0,
        }
