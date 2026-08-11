"""Autonomy Controller — Command and state control for autonomous operations.

Manages the autonomy state machine, enforces autonomy level boundaries,
and controls what the autonomous system is allowed to do at each level.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .autonomous_platform import AutonomyConfig, AutonomyLevel

logger = logging.getLogger(__name__)


class ControllerState(str, Enum):
    """Controller state machine."""

    IDLE = "idle"
    SCANNING = "scanning"
    DISCOVERING = "discovering"
    HYPOTHESIZING = "hypothesizing"
    RESEARCHING = "researching"
    FACTOR_MINING = "factor_mining"
    ALPHA_DISCOVERING = "alpha_discovering"
    STRATEGY_GENERATING = "strategy_generating"
    BACKTESTING = "backtesting"
    VALIDATING = "validating"
    PAUSED = "paused"
    ABORTED = "aborted"


@dataclass
class ActionRequest:
    """An action the autonomous system wants to perform."""

    action_id: str
    action_type: str  # scan, hypothesize, mine, generate, backtest
    level_required: Any  # AutonomyLevel
    parameters: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ActionResult:
    """Result of an action request."""

    action_id: str
    allowed: bool
    reason: str = ""
    result: Optional[Any] = None


class AutonomyController:
    """Autonomy Controller — enforces autonomy boundaries.

    The controller ensures the autonomous system never exceeds its
    configured autonomy level. It gates every autonomous action:
        - Level 0: No autonomous actions
        - Level 1: Can suggest research directions
        - Level 2: Can run experiments
        - Level 3: Can generate candidates
        - Level 4: Can validate candidates
        - Level 5: Can propose for production

    At no level can the autonomous system bypass Risk/Approval/Execution.
    """

    def __init__(self, config: "AutonomyConfig") -> None:
        self.config = config
        self.state = ControllerState.IDLE
        self._action_history: List[ActionRequest] = []
        self._daily_actions: Dict[str, int] = {}
        self._started = False

    async def start(self) -> None:
        self._started = True
        logger.info("Autonomy Controller started (level=%s)", self.config.level.name)

    async def stop(self) -> None:
        self._started = False
        self.state = ControllerState.IDLE
        logger.info("Autonomy Controller stopped")

    # ------------------------------------------------------------------
    # Action Authorization
    # ------------------------------------------------------------------

    async def authorize(
        self,
        action_type: str,
        level_required: "AutonomyLevel",
        **parameters,
    ) -> ActionResult:
        """Check if an action is authorized at current autonomy level.

        Args:
            action_type: Type of action.
            level_required: Minimum autonomy level needed.
            **parameters: Action parameters.

        Returns:
            ActionResult with allowed/rejected status.
        """
        from .autonomous_platform import AutonomyLevel

        action = ActionRequest(
            action_id=f"act_{action_type}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
            action_type=action_type,
            level_required=level_required,
            parameters=parameters,
        )
        self._action_history.append(action)

        # Check autonomy level
        if level_required.value > self.config.level.value:
            return ActionResult(
                action_id=action.action_id,
                allowed=False,
                reason=(
                    f"Action '{action_type}' requires level {level_required.name} "
                    f"(current: {self.config.level.name})"
                ),
            )

        # Check daily limits
        daily_count = self._daily_actions.get(action_type, 0)
        limits = {
            "hypothesize": self.config.max_daily_hypotheses,
            "experiment": self.config.max_daily_experiments,
            "backtest": self.config.max_daily_backtests,
        }
        limit = limits.get(action_type, float("inf"))
        if daily_count >= limit:
            return ActionResult(
                action_id=action.action_id,
                allowed=False,
                reason=f"Daily limit reached for '{action_type}': {daily_count}/{limit}",
            )

        # Require approval for high autonomy actions
        if (
            self.config.require_approval_above_level is not None
            and level_required.value >= self.config.require_approval_above_level.value
        ):
            logger.info(
                "Action '%s' at level %s requires approval",
                action_type,
                level_required.name,
            )
            # Approval check would be integrated with ApprovalGate

        self._daily_actions[action_type] = daily_count + 1
        self.state = self._state_for_action(action_type)

        return ActionResult(
            action_id=action.action_id,
            allowed=True,
            reason=f"Authorized at level {self.config.level.name}",
        )

    def _state_for_action(self, action_type: str) -> ControllerState:
        """Map action type to controller state."""
        mapping = {
            "scan": ControllerState.SCANNING,
            "hypothesize": ControllerState.HYPOTHESIZING,
            "research": ControllerState.RESEARCHING,
            "mine_factor": ControllerState.FACTOR_MINING,
            "discover_alpha": ControllerState.ALPHA_DISCOVERING,
            "generate_strategy": ControllerState.STRATEGY_GENERATING,
            "backtest": ControllerState.BACKTESTING,
            "validate": ControllerState.VALIDATING,
        }
        return mapping.get(action_type, ControllerState.DISCOVERING)

    # ------------------------------------------------------------------
    # State Management
    # ------------------------------------------------------------------

    def pause(self) -> None:
        """Pause autonomous operations."""
        self.state = ControllerState.PAUSED
        logger.info("Autonomy Controller paused")

    def resume(self) -> None:
        """Resume autonomous operations."""
        self.state = ControllerState.IDLE
        logger.info("Autonomy Controller resumed")

    def abort(self, reason: str = "") -> None:
        """Emergency abort all autonomous operations."""
        self.state = ControllerState.ABORTED
        logger.critical("Autonomy Controller ABORTED: %s", reason)

    # ------------------------------------------------------------------
    # Daily reset
    # ------------------------------------------------------------------

    def reset_daily(self) -> None:
        """Reset daily action counters."""
        self._daily_actions.clear()
        logger.info("Daily action counters reset")

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        return {
            "started": self._started,
            "state": self.state.value,
            "autonomy_level": self.config.level.name,
            "daily_actions": dict(self._daily_actions),
            "total_actions": len(self._action_history),
            "limits": {
                "hypotheses": self.config.max_daily_hypotheses,
                "experiments": self.config.max_daily_experiments,
                "backtests": self.config.max_daily_backtests,
            },
        }
