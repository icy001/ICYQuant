"""AI Permissions — Permission model and enforcement for AI operations.

AI permissions define what AI agents and subsystems are authorized to do.
This is a layered permission model that enforces separation between
AI analysis and trading execution.

Permission levels (ascending):
    RESEARCH     — Read data, run analysis, generate hypotheses
    ANALYZE      — Run models, analyze features, compare predictions
    PREDICT      — Generate predictions and forecasts
    SIGNAL       — Generate trading signals
    PROPOSE_ORDER — Propose orders for review
    REQUEST_EXECUTION — Request execution (requires separate approval)

Note: EXECUTE_ORDER is NOT an AI permission. It belongs to the trading
control layer (OMS/EMS), not the AI layer. AI ≠ Execution Authority.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .ai_context import AIContext
from .ai_session import AISession

if TYPE_CHECKING:
    from .ai_platform import AIPlatformConfig, AIPlatformMode

logger = logging.getLogger(__name__)


class AIPermissionLevel(IntEnum):
    """AI permission levels — ascending authority.

    Each level includes all lower-level permissions.
    """

    NONE = 0
    RESEARCH = 1
    ANALYZE = 2
    PREDICT = 3
    SIGNAL = 4
    PROPOSE_ORDER = 5
    REQUEST_EXECUTION = 6

    # NOTICE: EXECUTE_ORDER is NOT in this enum.
    # Execution authority belongs to OMS/EMS, not AI.


@dataclass
class PermissionCheck:
    """Result of a permission check."""

    granted: bool
    level: AIPermissionLevel
    requested: AIPermissionLevel
    reason: str = ""
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PermissionContext:
    """Context for permission evaluation."""

    session_mode: "AIPlatformMode"
    agent_type: str = "system"
    agent_id: str = "default"
    model_status: str = "unknown"
    risk_status: str = "unknown"
    data_quality: str = "good"


class AIPermissions:
    """AI Permissions — enforcement layer for AI operations.

    Permission model:
        RESEARCH → ANALYZE → PREDICT → SIGNAL → PROPOSE_ORDER → REQUEST_EXECUTION

    Mode-based restrictions:
        research mode:    RESEARCH, ANALYZE, PREDICT
        paper_trading:    RESEARCH, ANALYZE, PREDICT, SIGNAL
        backtest:         RESEARCH, ANALYZE, PREDICT, SIGNAL
        live:             Full chain (but execution requires separate approval)
        audit:            RESEARCH only

    Critical invariants:
        - AI can NEVER skip the Risk Engine
        - AI can NEVER directly execute orders
        - Lower-confidence predictions require higher permissions
        - Emergency mode revokes all AI permissions
    """

    def __init__(self, config: "AIPlatformConfig") -> None:
        self.config = config
        self._permission_grants: Dict[str, List[AIPermissionLevel]] = {}
        self._emergency_locked = False

    # ------------------------------------------------------------------
    # Mode-based Permissions
    # ------------------------------------------------------------------

    _MODE_PERMISSIONS = {
        "research": AIPermissionLevel.PREDICT,
        "paper_trading": AIPermissionLevel.SIGNAL,
        "backtest": AIPermissionLevel.SIGNAL,
        "live": AIPermissionLevel.REQUEST_EXECUTION,
        "audit": AIPermissionLevel.RESEARCH,
    }

    def get_max_permission(
        self, mode: Optional["AIPlatformMode"] = None
    ) -> AIPermissionLevel:
        """Get maximum permission level for the current mode."""
        if self._emergency_locked:
            return AIPermissionLevel.NONE

        if mode is None:
            mode = self.config.mode

        mode_str = mode.value if hasattr(mode, 'value') else str(mode)
        return self._MODE_PERMISSIONS.get(
            mode_str, AIPermissionLevel.RESEARCH
        )

    # ------------------------------------------------------------------
    # Permission Checking
    # ------------------------------------------------------------------

    async def check(
        self,
        session: AISession,
        context: AIContext,
        requested: Optional[AIPermissionLevel] = None,
    ) -> PermissionCheck:
        """Check if the current session has the required permission level.

        Args:
            session: The AI session.
            context: The AI context for additional checks.
            requested: The permission level being requested.

        Returns:
            PermissionCheck with grant/deny result.
        """
        if requested is None:
            requested = AIPermissionLevel.ANALYZE

        if self._emergency_locked:
            return PermissionCheck(
                granted=False,
                level=self.get_max_permission(session.mode),
                requested=requested,
                reason="Emergency lock active — all AI operations suspended",
            )

        max_allowed = self.get_max_permission(session.mode)

        # Check agent-specific grants
        agent_grants = self._permission_grants.get(
            session.metadata.get("agent_id", "default"), []
        )
        if agent_grants:
            effective_max = max(max_allowed, max(agent_grants))
        else:
            effective_max = max_allowed

        if requested > effective_max:
            return PermissionCheck(
                granted=False,
                level=effective_max,
                requested=requested,
                reason=(
                    f"Permission denied: {requested.name} exceeds max "
                    f"{effective_max.name} for mode {session.mode}"
                ),
            )

        # Additional checks for higher permissions
        if requested >= AIPermissionLevel.PROPOSE_ORDER:
            # Must have risk check passed
            if not context.risk_approved:
                return PermissionCheck(
                    granted=False,
                    level=effective_max,
                    requested=requested,
                    reason="Risk check not passed — cannot propose orders",
                )

        if requested >= AIPermissionLevel.REQUEST_EXECUTION:
            # Must have explicit approval
            if not context.decision_approved:
                return PermissionCheck(
                    granted=False,
                    level=effective_max,
                    requested=requested,
                    reason="Decision not approved — cannot request execution",
                )

        return PermissionCheck(
            granted=True,
            level=effective_max,
            requested=requested,
            reason="Permission granted",
        )

    # ------------------------------------------------------------------
    # Agent-Specific Grants
    # ------------------------------------------------------------------

    def grant_permission(
        self,
        agent_id: str,
        levels: List[AIPermissionLevel],
    ) -> None:
        """Grant specific permission levels to an agent."""
        self._permission_grants[agent_id] = levels
        logger.info(
            "Permissions granted to %s: %s",
            agent_id,
            [l.name for l in levels],
        )

    def revoke_permission(self, agent_id: str) -> None:
        """Revoke all special permissions for an agent."""
        self._permission_grants.pop(agent_id, None)
        logger.info("Permissions revoked for %s", agent_id)

    def get_agent_permissions(self, agent_id: str) -> List[AIPermissionLevel]:
        """Get granted permissions for an agent."""
        return self._permission_grants.get(agent_id, [])

    # ------------------------------------------------------------------
    # Emergency Controls
    # ------------------------------------------------------------------

    def emergency_lock(self) -> None:
        """Revoke all AI permissions immediately."""
        self._emergency_locked = True
        logger.critical("EMERGENCY LOCK: All AI permissions revoked")

    def emergency_unlock(self) -> None:
        """Restore AI permissions."""
        self._emergency_locked = False
        logger.warning("EMERGENCY UNLOCK: AI permissions restored")

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def can_research(self, mode: Optional["AIPlatformMode"] = None) -> bool:
        """Check if research is allowed."""
        return self.get_max_permission(mode) >= AIPermissionLevel.RESEARCH

    def can_predict(self, mode: Optional["AIPlatformMode"] = None) -> bool:
        """Check if prediction is allowed."""
        return self.get_max_permission(mode) >= AIPermissionLevel.PREDICT

    def can_generate_signal(self, mode: Optional["AIPlatformMode"] = None) -> bool:
        """Check if signal generation is allowed."""
        return self.get_max_permission(mode) >= AIPermissionLevel.SIGNAL

    def can_propose_order(self, mode: Optional["AIPlatformMode"] = None) -> bool:
        """Check if order proposal is allowed."""
        return self.get_max_permission(mode) >= AIPermissionLevel.PROPOSE_ORDER

    def is_emergency_locked(self) -> bool:
        """Check if emergency lock is active."""
        return self._emergency_locked
