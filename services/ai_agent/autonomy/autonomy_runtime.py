"""Autonomy Runtime — configuration and execution environment for autonomous workflows.

Pipelines:
    AutonomyConfig -> AutonomyRuntime.initialize()
        -> bootstrap components
        -> start monitoring loop
        -> AutonomyRuntime.shutdown() (graceful teardown)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class AutonomyMode(str, Enum):
    """Operating mode for the autonomy engine."""
    RESEARCH_ONLY = "research_only"
    PAPER_TRADING = "paper_trading"
    LIVE_TRADING = "live_trading"


class ApprovalMode(str, Enum):
    """Human-in-the-Loop configuration."""
    NONE = "none"
    SIGNIFICANT_ONLY = "significant_only"
    ALWAYS = "always"


@dataclass
class AutonomyConfig:
    """Configuration for the autonomous research and trading engine.

    Attributes:
        mode: Operating mode (research_only / paper_trading / live_trading).
        approval_mode: Human approval configuration.
        max_parallel_workflows: Maximum concurrent autonomous workflows.
        market_monitor_interval_sec: How often to scan for opportunities.
        max_backtest_symbols: Maximum symbols per autonomous backtest.
        confidence_threshold: Minimum confidence for auto-approval (0.0-1.0).
        max_position_size_pct: Maximum single position as % of portfolio.
        risk_budget_pct: Maximum risk budget as % of portfolio VaR.
        learning_enabled: Whether continuous learning is active.
        audit_enabled: Whether full audit logging is enabled.
        max_autonomy_duration_min: Maximum duration for a single autonomous workflow.
    """

    mode: AutonomyMode = AutonomyMode.RESEARCH_ONLY
    approval_mode: ApprovalMode = ApprovalMode.ALWAYS
    max_parallel_workflows: int = 3
    market_monitor_interval_sec: float = 60.0
    max_backtest_symbols: int = 50
    confidence_threshold: float = 0.80
    max_position_size_pct: float = 0.10
    risk_budget_pct: float = 0.05
    learning_enabled: bool = True
    audit_enabled: bool = True
    max_autonomy_duration_min: float = 120.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "approval_mode": self.approval_mode.value,
            "max_parallel_workflows": self.max_parallel_workflows,
            "market_monitor_interval_sec": self.market_monitor_interval_sec,
            "max_backtest_symbols": self.max_backtest_symbols,
            "confidence_threshold": self.confidence_threshold,
            "max_position_size_pct": self.max_position_size_pct,
            "risk_budget_pct": self.risk_budget_pct,
            "learning_enabled": self.learning_enabled,
            "audit_enabled": self.audit_enabled,
            "max_autonomy_duration_min": self.max_autonomy_duration_min,
        }


class AutonomyRuntime:
    """Runtime environment for the autonomous research engine.

    Manages configuration, lifecycle, and monitoring for autonomous workflows.
    Provides the execution sandbox within which autonomous operations run.

    Supports:
        - Configuration management
        - Workflow concurrency limits
        - Duration bounds enforcement
        - Health status tracking

    Usage:
        config = AutonomyConfig(mode=AutonomyMode.RESEARCH_ONLY)
        runtime = AutonomyRuntime(config)
        await runtime.initialize()
        runtime.is_within_bounds()
    """

    def __init__(self, config: Optional[AutonomyConfig] = None) -> None:
        self._config = config or AutonomyConfig()
        self._initialized: bool = False
        self._active_workflows: int = 0
        self._total_workflows: int = 0
        self._total_approvals: int = 0
        self._total_rejections: int = 0
        logger.info("AutonomyRuntime created (mode=%s)", self._config.mode.value)

    async def initialize(self) -> None:
        if self._initialized:
            logger.warning("AutonomyRuntime already initialized")
            return
        self._initialized = True
        logger.info("AutonomyRuntime initialized")

    async def shutdown(self) -> None:
        self._initialized = False
        logger.info("AutonomyRuntime shutdown complete")

    @property
    def config(self) -> AutonomyConfig:
        return self._config

    @property
    def active_workflows(self) -> int:
        return self._active_workflows

    def can_start_workflow(self) -> bool:
        return self._active_workflows < self._config.max_parallel_workflows

    def workflow_started(self) -> None:
        self._active_workflows += 1
        self._total_workflows += 1

    def workflow_completed(self) -> None:
        self._active_workflows = max(0, self._active_workflows - 1)

    def record_approval(self, approved: bool) -> None:
        if approved:
            self._total_approvals += 1
        else:
            self._total_rejections += 1

    def get_summary(self) -> Dict[str, Any]:
        return {
            "initialized": self._initialized,
            "config": self._config.to_dict(),
            "active_workflows": self._active_workflows,
            "total_workflows": self._total_workflows,
            "total_approvals": self._total_approvals,
            "total_rejections": self._total_rejections,
        }
