"""
Risk Action Engine — Automated risk response execution.

Processes risk alerts and triggers automated actions: position
reduction, hedging, strategy pause, and kill switch activation.

Architecture::

    Risk Event → Decision Engine → Reduce/Hedge/Pause/Kill → Notify Operator
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from .risk_alert_center import RiskAlert, AlertSeverity

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    """Types of automated risk actions."""
    REDUCE_POSITION = "REDUCE_POSITION"
    HEDGE = "HEDGE"
    PAUSE_STRATEGY = "PAUSE_STRATEGY"
    RESUME_STRATEGY = "RESUME_STRATEGY"
    KILL_SWITCH = "KILL_SWITCH"
    NOTIFY_OPERATOR = "NOTIFY_OPERATOR"
    NO_ACTION = "NO_ACTION"


class ActionStatus(str, Enum):
    """Action execution status."""
    PENDING = "PENDING"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    REVERSED = "REVERSED"


class ActionMode(str, Enum):
    """Risk action execution mode."""
    FULLY_AUTOMATED = "FULLY_AUTOMATED"
    SEMI_AUTOMATED = "SEMI_AUTOMATED"
    MANUAL_ONLY = "MANUAL_ONLY"


@dataclass
class RiskAction:
    """A single risk response action."""
    action_id: str
    action_type: ActionType
    severity: AlertSeverity
    account_id: str = ""
    strategy_id: str = ""
    symbol: str = ""
    target_reduction_pct: float = 0.0
    reason: str = ""
    status: ActionStatus = ActionStatus.PENDING
    mode: ActionMode = ActionMode.FULLY_AUTOMATED
    requires_approval: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    executed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "severity": self.severity.value,
            "account_id": self.account_id,
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "target_reduction_pct": self.target_reduction_pct,
            "reason": self.reason,
            "status": self.status.value,
            "mode": self.mode.value,
            "requires_approval": self.requires_approval,
            "created_at": self.created_at.isoformat(),
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
        }


class RiskActionEngine:
    """
    Automated risk response execution engine.

    Processes risk alerts and triggers automated actions based on
    severity and configured response policies. Supports fully
    automated, semi-automated, and manual-only modes.

    Usage::

        engine = RiskActionEngine(mode=ActionMode.FULLY_AUTOMATED)
        await engine.initialize()

        actions = await engine.process_alerts(alerts)
        await engine.execute(actions)
    """

    def __init__(
        self,
        mode: ActionMode = ActionMode.SEMI_AUTOMATED,
        max_actions_per_minute: int = 10,
        cooldown_seconds: int = 60,
    ) -> None:
        self._mode = mode
        self._max_actions_per_minute = max_actions_per_minute
        self._cooldown_seconds = cooldown_seconds

        self._action_history: list[RiskAction] = []
        self._active_actions: dict[str, RiskAction] = {}
        self._action_counter: int = 0
        self._last_action_time: Optional[datetime] = None
        self._kill_switch_active: bool = False
        self._strategies_paused: set[str] = set()

        self._lock = asyncio.Lock()
        self._initialized = False

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize the risk action engine."""
        self._initialized = True
        logger.info(f"RiskActionEngine initialized (mode={self._mode.value}).")

    async def stop(self) -> None:
        """Stop the risk action engine."""
        self._initialized = False
        logger.info("RiskActionEngine stopped.")

    # ---- Core API ----

    async def process_alerts(self, alerts: list[RiskAlert]) -> list[RiskAction]:
        """
        Process alerts and generate risk actions.

        Maps alert severity to action types:
            - EMERGENCY → KILL_SWITCH
            - CRITICAL → PAUSE_STRATEGY + REDUCE_POSITION
            - HIGH → REDUCE_POSITION
            - WARNING → NOTIFY_OPERATOR
        """
        if self._mode == ActionMode.MANUAL_ONLY:
            logger.info("Manual-only mode: alerts logged, no automated actions.")
            return []

        actions = []

        for alert in alerts:
            action = self._determine_action(alert)
            if action and action.action_type != ActionType.NO_ACTION:
                actions.append(action)

                async with self._lock:
                    self._action_history.append(action)
                    self._active_actions[action.action_id] = action

        if actions:
            logger.info(f"Generated {len(actions)} actions from {len(alerts)} alerts.")

        return actions

    async def execute(self, actions: list[RiskAction]) -> list[RiskAction]:
        """
        Execute a list of risk actions.

        Respects rate limits, cooldown periods, and the current mode.
        Returns the executed actions with updated status.
        """
        if not self._initialized:
            return actions

        executed = []

        for action in actions:
            # Check kill switch override
            if self._kill_switch_active and action.action_type != ActionType.KILL_SWITCH:
                action.status = ActionStatus.REJECTED
                action.error_message = "Kill switch active — action rejected"
                continue

            # Check rate limit
            if not await self._check_rate_limit():
                action.status = ActionStatus.REJECTED
                action.error_message = "Rate limit exceeded"
                continue

            # Check approval requirement
            if self._mode == ActionMode.SEMI_AUTOMATED:
                severity_order = {
                    AlertSeverity.INFO: 0, AlertSeverity.WARNING: 1,
                    AlertSeverity.HIGH: 2, AlertSeverity.CRITICAL: 3,
                    AlertSeverity.EMERGENCY: 4,
                }
                if severity_order.get(action.severity, 0) >= 3:
                    action.requires_approval = True
                    logger.warning(
                        f"Action {action.action_id} requires manual approval "
                        f"(severity={action.severity.value})"
                    )
                    continue

            # Execute
            try:
                await self._execute_action(action)
                action.status = ActionStatus.COMPLETED
                action.executed_at = datetime.now(timezone.utc)
                action.completed_at = datetime.now(timezone.utc)
                executed.append(action)
            except Exception as e:
                action.status = ActionStatus.FAILED
                action.error_message = str(e)
                logger.error(f"Action {action.action_id} failed: {e}")

        return executed

    async def trigger_kill_switch(self, reason: str = "") -> RiskAction:
        """Activate the emergency kill switch."""
        self._kill_switch_active = True

        self._action_counter += 1
        action = RiskAction(
            action_id=f"ACTION-{self._action_counter:08d}",
            action_type=ActionType.KILL_SWITCH,
            severity=AlertSeverity.EMERGENCY,
            reason=reason or "Manual kill switch activated",
            mode=ActionMode.FULLY_AUTOMATED,
        )

        async with self._lock:
            self._action_history.append(action)
            self._active_actions[action.action_id] = action

        logger.critical(f"KILL SWITCH ACTIVATED: {reason}")
        return action

    async def release_kill_switch(self) -> None:
        """Release the kill switch."""
        self._kill_switch_active = False
        logger.warning("Kill switch released — normal operations may resume.")

    async def pause_strategy(self, strategy_id: str, reason: str = "") -> RiskAction:
        """Pause a specific strategy."""
        self._strategies_paused.add(strategy_id)

        self._action_counter += 1
        action = RiskAction(
            action_id=f"ACTION-{self._action_counter:08d}",
            action_type=ActionType.PAUSE_STRATEGY,
            severity=AlertSeverity.HIGH,
            strategy_id=strategy_id,
            reason=reason or f"Strategy {strategy_id} paused due to risk limits",
        )
        async with self._lock:
            self._action_history.append(action)
        logger.warning(f"Strategy paused: {strategy_id} — {reason}")
        return action

    async def resume_strategy(self, strategy_id: str) -> RiskAction:
        """Resume a paused strategy."""
        self._strategies_paused.discard(strategy_id)

        self._action_counter += 1
        action = RiskAction(
            action_id=f"ACTION-{self._action_counter:08d}",
            action_type=ActionType.RESUME_STRATEGY,
            severity=AlertSeverity.INFO,
            strategy_id=strategy_id,
            reason=f"Strategy {strategy_id} resumed",
        )
        logger.info(f"Strategy resumed: {strategy_id}")
        return action

    # ---- Query ----

    @property
    def kill_switch_active(self) -> bool:
        return self._kill_switch_active

    @property
    def paused_strategies(self) -> set[str]:
        return set(self._strategies_paused)

    async def get_active_actions(self) -> list[RiskAction]:
        """Get all pending/executing actions."""
        return [
            a for a in self._active_actions.values()
            if a.status in (ActionStatus.PENDING, ActionStatus.EXECUTING)
        ]

    async def get_action_history(self, limit: int = 100) -> list[RiskAction]:
        """Get recent action history."""
        return self._action_history[-limit:]

    async def get_stats(self) -> dict[str, Any]:
        """Get engine statistics."""
        async with self._lock:
            return {
                "mode": self._mode.value,
                "kill_switch_active": self._kill_switch_active,
                "paused_strategies": list(self._strategies_paused),
                "total_actions": len(self._action_history),
                "active_actions": len(self._active_actions),
                "last_action_time": (
                    self._last_action_time.isoformat()
                    if self._last_action_time else None
                ),
            }

    # ---- Internal ----

    def _determine_action(self, alert: RiskAlert) -> Optional[RiskAction]:
        """Determine the appropriate action for an alert."""
        self._action_counter += 1
        action_id = f"ACTION-{self._action_counter:08d}"

        if alert.severity == AlertSeverity.EMERGENCY:
            self._kill_switch_active = True
            return RiskAction(
                action_id=action_id,
                action_type=ActionType.KILL_SWITCH,
                severity=alert.severity,
                account_id=alert.account_id,
                reason=alert.message,
            )
        elif alert.severity == AlertSeverity.CRITICAL:
            return RiskAction(
                action_id=action_id,
                action_type=ActionType.PAUSE_STRATEGY,
                severity=alert.severity,
                account_id=alert.account_id,
                reason=alert.message,
            )
        elif alert.severity == AlertSeverity.HIGH:
            return RiskAction(
                action_id=action_id,
                action_type=ActionType.REDUCE_POSITION,
                severity=alert.severity,
                account_id=alert.account_id,
                target_reduction_pct=50.0,
                reason=alert.message,
            )
        elif alert.severity == AlertSeverity.WARNING:
            return RiskAction(
                action_id=action_id,
                action_type=ActionType.NOTIFY_OPERATOR,
                severity=alert.severity,
                account_id=alert.account_id,
                reason=alert.message,
            )

        return RiskAction(
            action_id=action_id,
            action_type=ActionType.NO_ACTION,
            severity=alert.severity,
        )

    async def _execute_action(self, action: RiskAction) -> None:
        """Execute a specific action."""
        action.status = ActionStatus.EXECUTING

        if action.action_type == ActionType.KILL_SWITCH:
            self._kill_switch_active = True
            logger.critical(f"EXECUTED: Kill switch — {action.reason}")

        elif action.action_type == ActionType.PAUSE_STRATEGY:
            self._strategies_paused.add(action.strategy_id)
            logger.warning(f"EXECUTED: Pause strategy {action.strategy_id}")

        elif action.action_type == ActionType.RESUME_STRATEGY:
            self._strategies_paused.discard(action.strategy_id)
            logger.info(f"EXECUTED: Resume strategy {action.strategy_id}")

        elif action.action_type == ActionType.REDUCE_POSITION:
            logger.warning(
                f"EXECUTED: Reduce {action.symbol or 'all positions'} "
                f"by {action.target_reduction_pct:.0f}% — {action.reason}"
            )

        elif action.action_type == ActionType.NOTIFY_OPERATOR:
            logger.info(f"EXECUTED: Operator notified — {action.reason}")

        self._last_action_time = datetime.now(timezone.utc)

    async def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits."""
        if not self._last_action_time:
            return True

        elapsed = (datetime.now(timezone.utc) - self._last_action_time).total_seconds()
        if elapsed < self._cooldown_seconds:
            return False

        return True

    async def health_check(self) -> dict[str, Any]:
        """Check engine health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "kill_switch_active": self._kill_switch_active,
            "paused_strategies": len(self._strategies_paused),
        }
