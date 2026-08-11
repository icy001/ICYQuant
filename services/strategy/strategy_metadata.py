"""
Strategy metadata model.

Captures descriptive, operational, and performance metadata for
each registered strategy within the production platform.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .strategy_state import StrategyLifecycleState


@dataclass
class StrategyCapability:
    """Declared capabilities of a strategy."""

    asset_classes: List[str] = field(default_factory=list)
    """Supported asset classes (e.g. equity, futures, options)."""

    markets: List[str] = field(default_factory=list)
    """Target markets (e.g. CN, US, HK)."""

    frequency: str = "daily"
    """Trading frequency: tick, minute, hourly, daily, weekly."""

    style: str = "unknown"
    """Strategy style: trend, mean_reversion, arbitrage, market_making, etc."""

    long_only: bool = True
    """Whether the strategy is long-only."""

    multi_instrument: bool = False
    """Whether the strategy trades multiple instruments."""

    supports_partial_execution: bool = False
    """Whether the strategy supports partial fills."""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_classes": self.asset_classes,
            "markets": self.markets,
            "frequency": self.frequency,
            "style": self.style,
            "long_only": self.long_only,
            "multi_instrument": self.multi_instrument,
            "supports_partial_execution": self.supports_partial_execution,
        }


@dataclass
class StrategyPerformanceStats:
    """Aggregated performance statistics."""

    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    signals_generated: int = 0
    last_signal_at: Optional[datetime] = None
    last_execution_at: Optional[datetime] = None
    uptime_seconds: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_executions == 0:
            return 0.0
        return self.successful_executions / self.total_executions

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "success_rate": self.success_rate,
            "avg_latency_ms": self.avg_latency_ms,
            "p50_latency_ms": self.p50_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "p99_latency_ms": self.p99_latency_ms,
            "signals_generated": self.signals_generated,
            "last_signal_at": self.last_signal_at.isoformat() if self.last_signal_at else None,
            "last_execution_at": self.last_execution_at.isoformat() if self.last_execution_at else None,
            "uptime_seconds": self.uptime_seconds,
        }


@dataclass
class StrategyMetadata:
    """Comprehensive metadata for a registered strategy."""

    strategy_id: str
    name: str
    version: str
    author: str = "unknown"
    description: str = ""
    tags: List[str] = field(default_factory=list)
    capability: StrategyCapability = field(default_factory=StrategyCapability)
    state: StrategyLifecycleState = StrategyLifecycleState.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    deployed_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    transition_history: List[Dict[str, Any]] = field(default_factory=list)
    performance: StrategyPerformanceStats = field(default_factory=StrategyPerformanceStats)
    custom_metadata: Dict[str, Any] = field(default_factory=dict)

    def add_transition(
        self,
        from_state: StrategyLifecycleState,
        to_state: StrategyLifecycleState,
        reason: str = "",
    ) -> None:
        self.transition_history.append({
            "from": from_state.value,
            "to": to_state.value,
            "reason": reason,
            "at": datetime.now(timezone.utc).isoformat(),
        })
        self.state = to_state
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "tags": self.tags,
            "capability": self.capability.to_dict(),
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "deployed_at": self.deployed_at.isoformat() if self.deployed_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
            "transition_history": self.transition_history,
            "performance": self.performance.to_dict(),
            "custom_metadata": self.custom_metadata,
        }
