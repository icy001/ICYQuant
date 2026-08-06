"""Backtest Context — shared context propagated through all backtest operations.

Carries session, trace, user, workspace, and strategy configuration
across the backtesting engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


@dataclass
class BacktestContext:
    """Contextual data propagated through backtest operations.

    Carries:
    * Session/trace identifiers
    * User/workspace identity
    * Universe and benchmark configuration
    * Data frequency and date ranges
    * Capital and commission settings
    """

    session_id: str = field(default_factory=lambda: str(uuid4()))
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    user_id: Optional[str] = None
    workspace_id: Optional[str] = None
    project_id: Optional[str] = None
    experiment_id: Optional[str] = None
    strategy_id: Optional[str] = None

    # ── universe and data ──────────────────────────────────────────────────
    universe: List[str] = field(default_factory=list)
    benchmark: str = "CSI300"
    frequency: str = "daily"  # tick, 1m, 5m, 15m, 1h, daily
    start_date: Optional[str] = None
    end_date: Optional[str] = None

    # ── capital and cost ───────────────────────────────────────────────────
    initial_capital: float = 1_000_000.0
    commission_rate: float = 0.0003
    slippage_rate: float = 0.001
    tax_rate: float = 0.001

    # ── risk ───────────────────────────────────────────────────────────────
    max_position_size: float = 0.1
    max_leverage: float = 1.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    # ── execution ──────────────────────────────────────────────────────────
    execution_model: str = "default"  # default, twap, vwap
    latency_ms: float = 0.0
    allow_short: bool = False
    enable_margin: bool = False

    # ── extras ─────────────────────────────────────────────────────────────
    config: Dict[str, Any] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def with_overrides(self, **kwargs) -> "BacktestContext":
        """Return a new context with specified fields overridden."""
        new_ctx = BacktestContext(
            session_id=self.session_id,
            trace_id=kwargs.get("trace_id", self.trace_id),
            user_id=kwargs.get("user_id", self.user_id),
            workspace_id=kwargs.get("workspace_id", self.workspace_id),
            project_id=kwargs.get("project_id", self.project_id),
            experiment_id=kwargs.get("experiment_id", self.experiment_id),
            strategy_id=kwargs.get("strategy_id", self.strategy_id),
            universe=kwargs.get("universe", self.universe),
            benchmark=kwargs.get("benchmark", self.benchmark),
            frequency=kwargs.get("frequency", self.frequency),
            start_date=kwargs.get("start_date", self.start_date),
            end_date=kwargs.get("end_date", self.end_date),
            initial_capital=kwargs.get("initial_capital", self.initial_capital),
            commission_rate=kwargs.get("commission_rate", self.commission_rate),
            slippage_rate=kwargs.get("slippage_rate", self.slippage_rate),
            tax_rate=kwargs.get("tax_rate", self.tax_rate),
            max_position_size=kwargs.get("max_position_size", self.max_position_size),
            max_leverage=kwargs.get("max_leverage", self.max_leverage),
            stop_loss=kwargs.get("stop_loss", self.stop_loss),
            take_profit=kwargs.get("take_profit", self.take_profit),
            execution_model=kwargs.get("execution_model", self.execution_model),
            latency_ms=kwargs.get("latency_ms", self.latency_ms),
            allow_short=kwargs.get("allow_short", self.allow_short),
            enable_margin=kwargs.get("enable_margin", self.enable_margin),
            config={**self.config, **kwargs.get("config", {})},
            tags={**self.tags, **kwargs.get("tags", {})},
            metadata={**self.metadata, **kwargs.get("metadata", {})},
            created_at=kwargs.get("created_at", self.created_at),
        )
        return new_ctx

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "user_id": self.user_id,
            "workspace_id": self.workspace_id,
            "project_id": self.project_id,
            "experiment_id": self.experiment_id,
            "strategy_id": self.strategy_id,
            "universe": self.universe,
            "benchmark": self.benchmark,
            "frequency": self.frequency,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "initial_capital": self.initial_capital,
            "commission_rate": self.commission_rate,
            "slippage_rate": self.slippage_rate,
            "tax_rate": self.tax_rate,
            "max_position_size": self.max_position_size,
            "max_leverage": self.max_leverage,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "execution_model": self.execution_model,
            "latency_ms": self.latency_ms,
            "allow_short": self.allow_short,
            "enable_margin": self.enable_margin,
            "config": self.config,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BacktestContext":
        return cls(
            session_id=data.get("session_id", str(uuid4())),
            trace_id=data.get("trace_id", str(uuid4())),
            user_id=data.get("user_id"),
            workspace_id=data.get("workspace_id"),
            project_id=data.get("project_id"),
            experiment_id=data.get("experiment_id"),
            strategy_id=data.get("strategy_id"),
            universe=data.get("universe", []),
            benchmark=data.get("benchmark", "CSI300"),
            frequency=data.get("frequency", "daily"),
            start_date=data.get("start_date"),
            end_date=data.get("end_date"),
            initial_capital=data.get("initial_capital", 1_000_000.0),
            commission_rate=data.get("commission_rate", 0.0003),
            slippage_rate=data.get("slippage_rate", 0.001),
            tax_rate=data.get("tax_rate", 0.001),
            max_position_size=data.get("max_position_size", 0.1),
            max_leverage=data.get("max_leverage", 1.0),
            stop_loss=data.get("stop_loss"),
            take_profit=data.get("take_profit"),
            execution_model=data.get("execution_model", "default"),
            latency_ms=data.get("latency_ms", 0.0),
            allow_short=data.get("allow_short", False),
            enable_margin=data.get("enable_margin", False),
            config=data.get("config", {}),
            tags=data.get("tags", {}),
            metadata=data.get("metadata", {}),
        )
