"""
Strategy Pause Controller — Granular strategy-level risk control.

Manages pause/resume of individual strategies based on risk events,
with configurable auto-pause triggers and recovery conditions.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PauseReason(str, Enum):
    """Reasons for strategy pause."""
    DRAWDOWN_LIMIT = "DRAWDOWN_LIMIT"
    PNL_LIMIT = "PNL_LIMIT"
    EXPOSURE_LIMIT = "EXPOSURE_LIMIT"
    MARGIN_BREACH = "MARGIN_BREACH"
    VOLATILITY_SPIKE = "VOLATILITY_SPIKE"
    MANUAL = "MANUAL"
    KILL_SWITCH = "KILL_SWITCH"
    COMPLIANCE = "COMPLIANCE"
    SCHEDULED = "SCHEDULED"


class PauseStatus(str, Enum):
    """Strategy pause status."""
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    PAUSING = "PAUSING"
    RESUMING = "RESUMING"


@dataclass
class StrategyState:
    """State of a single strategy."""
    strategy_id: str
    status: PauseStatus = PauseStatus.ACTIVE
    paused_at: Optional[datetime] = None
    paused_by: str = ""
    pause_reason: PauseReason = PauseReason.MANUAL
    pause_message: str = ""
    auto_resume_enabled: bool = False
    auto_resume_after_seconds: int = 0
    resume_conditions: dict[str, Any] = field(default_factory=dict)
    pause_count: int = 0
    total_paused_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AutoPauseRule:
    """Rule for automatically pausing a strategy."""
    rule_id: str
    strategy_id: str = ""  # Empty = applies to all
    reason: PauseReason = PauseReason.DRAWDOWN_LIMIT
    metric: str = "drawdown_pct"
    threshold: float = 10.0
    direction: str = "above"  # above or below
    cooldown_seconds: int = 300
    auto_resume: bool = False
    auto_resume_after_seconds: int = 600
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class StrategyPauseController:
    """
    Granular strategy-level pause/resume control.

    Manages individual strategy lifecycle with configurable auto-
    pause triggers, manual override, and automatic recovery.

    Usage::

        controller = StrategyPauseController()
        await controller.initialize()

        # Auto-pause rules
        controller.add_auto_pause_rule(AutoPauseRule(
            rule_id="dd_rule_01",
            reason=PauseReason.DRAWDOWN_LIMIT,
            metric="drawdown_pct",
            threshold=10.0,
        ))

        # Check conditions
        paused = await controller.check_auto_pause("STRAT-01", {"drawdown_pct": 12.5})
    """

    def __init__(self) -> None:
        self._strategies: dict[str, StrategyState] = {}
        self._auto_rules: dict[str, AutoPauseRule] = {}
        self._last_action_time: dict[str, datetime] = {}
        self._lock = asyncio.Lock()
        self._initialized = False

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize the strategy pause controller."""
        self._initialized = True
        logger.info("StrategyPauseController initialized.")

    async def stop(self) -> None:
        """Stop the strategy pause controller."""
        self._initialized = False
        logger.info("StrategyPauseController stopped.")

    # ---- Strategy Management ----

    async def register_strategy(self, strategy_id: str) -> StrategyState:
        """Register a strategy for pause control."""
        async with self._lock:
            if strategy_id not in self._strategies:
                self._strategies[strategy_id] = StrategyState(strategy_id=strategy_id)
        logger.info(f"Strategy registered: {strategy_id}")
        return self._strategies[strategy_id]

    async def pause_strategy(
        self,
        strategy_id: str,
        reason: PauseReason,
        message: str = "",
        paused_by: str = "system",
        auto_resume_after_seconds: int = 0,
    ) -> StrategyState:
        """
        Pause a strategy.

        Returns the updated StrategyState.
        """
        async with self._lock:
            if strategy_id not in self._strategies:
                await self.register_strategy(strategy_id)

            state = self._strategies[strategy_id]
            if state.status == PauseStatus.PAUSED:
                return state

            state.status = PauseStatus.PAUSING
            state.paused_at = datetime.now(timezone.utc)
            state.paused_by = paused_by
            state.pause_reason = reason
            state.pause_message = message
            state.pause_count += 1

            if auto_resume_after_seconds > 0:
                state.auto_resume_enabled = True
                state.auto_resume_after_seconds = auto_resume_after_seconds

            state.status = PauseStatus.PAUSED

        logger.warning(
            f"Strategy PAUSED: {strategy_id} reason={reason.value} "
            f"message='{message}' by={paused_by}"
        )
        return state

    async def resume_strategy(self, strategy_id: str) -> StrategyState:
        """Resume a paused strategy."""
        async with self._lock:
            state = self._strategies.get(strategy_id)
            if not state:
                logger.warning(f"Unknown strategy: {strategy_id}")
                return StrategyState(strategy_id=strategy_id)

            if state.status != PauseStatus.PAUSED:
                return state

            state.status = PauseStatus.RESUMING

            if state.paused_at:
                paused_seconds = (
                    datetime.now(timezone.utc) - state.paused_at
                ).total_seconds()
                state.total_paused_seconds += paused_seconds
                state.paused_at = None

            state.auto_resume_enabled = False
            state.status = PauseStatus.ACTIVE

        logger.info(f"Strategy RESUMED: {strategy_id}")
        return state

    async def pause_all(self, reason: PauseReason, message: str = "") -> list[str]:
        """Pause all registered strategies."""
        paused = []
        for strategy_id in list(self._strategies.keys()):
            await self.pause_strategy(strategy_id, reason, message)
            paused.append(strategy_id)
        logger.warning(f"ALL strategies paused ({len(paused)}): {reason.value}")
        return paused

    async def resume_all(self) -> list[str]:
        """Resume all paused strategies."""
        resumed = []
        for strategy_id, state in self._strategies.items():
            if state.status == PauseStatus.PAUSED:
                await self.resume_strategy(strategy_id)
                resumed.append(strategy_id)
        logger.info(f"All strategies resumed ({len(resumed)})")
        return resumed

    # ---- Auto-Pause Rules ----

    def add_auto_pause_rule(self, rule: AutoPauseRule) -> None:
        """Add an auto-pause rule."""
        self._auto_rules[rule.rule_id] = rule
        logger.info(f"Auto-pause rule added: {rule.rule_id} ({rule.reason.value})")

    def remove_auto_pause_rule(self, rule_id: str) -> None:
        """Remove an auto-pause rule."""
        self._auto_rules.pop(rule_id, None)
        logger.info(f"Auto-pause rule removed: {rule_id}")

    async def check_auto_pause(
        self,
        strategy_id: str,
        metrics: dict[str, float],
    ) -> Optional[StrategyState]:
        """
        Check strategy metrics against auto-pause rules.

        Returns the StrategyState if paused, None otherwise.
        """
        for rule in self._auto_rules.values():
            if not rule.enabled:
                continue

            # Check strategy filter
            if rule.strategy_id and rule.strategy_id != strategy_id:
                continue

            # Check cooldown
            last_time = self._last_action_time.get(rule.rule_id)
            if last_time:
                elapsed = (datetime.now(timezone.utc) - last_time).total_seconds()
                if elapsed < rule.cooldown_seconds:
                    continue

            metric_value = metrics.get(rule.metric)
            if metric_value is None:
                continue

            # Check threshold
            triggered = False
            if rule.direction == "above" and metric_value > rule.threshold:
                triggered = True
            elif rule.direction == "below" and metric_value < rule.threshold:
                triggered = True

            if not triggered:
                continue

            # Pause the strategy
            auto_resume = rule.auto_resume_after_seconds if rule.auto_resume else 0
            state = await self.pause_strategy(
                strategy_id=strategy_id,
                reason=rule.reason,
                message=f"Auto-pause: {rule.metric}={metric_value:.2f} (threshold={rule.threshold})",
                auto_resume_after_seconds=auto_resume,
            )

            self._last_action_time[rule.rule_id] = datetime.now(timezone.utc)
            return state

        return None

    # ---- Query ----

    async def get_strategy_state(self, strategy_id: str) -> Optional[StrategyState]:
        """Get state for a specific strategy."""
        return self._strategies.get(strategy_id)

    async def get_all_states(self) -> dict[str, StrategyState]:
        """Get all strategy states."""
        return dict(self._strategies)

    async def get_paused_strategies(self) -> list[StrategyState]:
        """Get all paused strategies."""
        return [
            s for s in self._strategies.values()
            if s.status == PauseStatus.PAUSED
        ]

    async def get_active_strategies(self) -> list[StrategyState]:
        """Get all active strategies."""
        return [
            s for s in self._strategies.values()
            if s.status == PauseStatus.ACTIVE
        ]

    # ---- Stats ----

    async def get_stats(self) -> dict[str, Any]:
        """Get controller statistics."""
        async with self._lock:
            return {
                "total_strategies": len(self._strategies),
                "paused_strategies": sum(
                    1 for s in self._strategies.values()
                    if s.status == PauseStatus.PAUSED
                ),
                "active_strategies": sum(
                    1 for s in self._strategies.values()
                    if s.status == PauseStatus.ACTIVE
                ),
                "auto_rules": len(self._auto_rules),
            }

    async def health_check(self) -> dict[str, Any]:
        """Check controller health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "strategies_tracked": len(self._strategies),
        }
