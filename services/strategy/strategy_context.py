"""
Production strategy execution context.

Captures the full runtime environment for a strategy execution,
including market state, account configuration, and execution parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class StrategyExecutionContext:
    """Immutable snapshot of the execution context for a strategy run."""

    strategy_id: str
    execution_id: str
    session_id: str = ""

    # Account and portfolio
    account_id: str = ""
    portfolio_id: str = ""
    universe: List[str] = field(default_factory=list)
    """List of instruments in scope."""

    # Market state
    market_open: bool = False
    trading_date: Optional[str] = None
    market_session: str = ""
    """e.g. pre_market, regular, after_hours."""

    # Configuration
    config: Dict[str, Any] = field(default_factory=dict)
    """Strategy-specific configuration parameters."""

    # Execution parameters
    mode: str = "paper"
    """Execution mode: paper, live, backtest."""

    dry_run: bool = False
    """If True, compute signals but do not emit orders."""

    max_position_pct: float = 1.0
    """Maximum position size as a fraction of portfolio."""

    # Timing
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    timeout_seconds: int = 300

    # Observability
    trace_id: str = ""
    parent_span_id: str = ""

    # Custom extensions
    custom_context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "execution_id": self.execution_id,
            "session_id": self.session_id,
            "account_id": self.account_id,
            "portfolio_id": self.portfolio_id,
            "universe": self.universe,
            "market_open": self.market_open,
            "trading_date": self.trading_date,
            "market_session": self.market_session,
            "config": self.config,
            "mode": self.mode,
            "dry_run": self.dry_run,
            "max_position_pct": self.max_position_pct,
            "created_at": self.created_at.isoformat(),
            "timeout_seconds": self.timeout_seconds,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "custom_context": self.custom_context,
        }

    def with_overrides(self, **kwargs: Any) -> StrategyExecutionContext:
        """Create a new context with overridden fields."""
        current = self.to_dict()
        current.update(kwargs)
        return StrategyExecutionContext(
            strategy_id=kwargs.get("strategy_id", self.strategy_id),
            execution_id=kwargs.get("execution_id", self.execution_id),
            session_id=kwargs.get("session_id", self.session_id),
            account_id=kwargs.get("account_id", self.account_id),
            portfolio_id=kwargs.get("portfolio_id", self.portfolio_id),
            universe=kwargs.get("universe", list(self.universe)),
            market_open=kwargs.get("market_open", self.market_open),
            trading_date=kwargs.get("trading_date", self.trading_date),
            market_session=kwargs.get("market_session", self.market_session),
            config=kwargs.get("config", dict(self.config)),
            mode=kwargs.get("mode", self.mode),
            dry_run=kwargs.get("dry_run", self.dry_run),
            max_position_pct=kwargs.get("max_position_pct", self.max_position_pct),
            timeout_seconds=kwargs.get("timeout_seconds", self.timeout_seconds),
            trace_id=kwargs.get("trace_id", self.trace_id),
            parent_span_id=kwargs.get("parent_span_id", self.parent_span_id),
            custom_context=kwargs.get("custom_context", dict(self.custom_context)),
        )
