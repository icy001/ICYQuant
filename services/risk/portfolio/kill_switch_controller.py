"""
Kill Switch Controller — Unified emergency shutdown for risk events.

Provides a centralized emergency stop mechanism that immediately
halts all trading activity when critical risk thresholds are
breached. Supports multiple activation triggers and a controlled
release process.

Architecture::

    PnL Limit / Margin Breach / Risk Score → Kill Switch → Stop All Orders
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class KillSwitchStatus(str, Enum):
    """Kill switch operational status."""
    ARMED = "ARMED"
    ACTIVE = "ACTIVE"
    RELEASING = "RELEASING"
    DISABLED = "DISABLED"


class KillTrigger(str, Enum):
    """Triggers that activate the kill switch."""
    PNL_LIMIT = "PNL_LIMIT"
    MARGIN_BREACH = "MARGIN_BREACH"
    RISK_SCORE = "RISK_SCORE"
    DRAWDOWN = "DRAWDOWN"
    EXPOSURE = "EXPOSURE"
    MANUAL = "MANUAL"
    SYSTEM_ERROR = "SYSTEM_ERROR"
    COMPLIANCE = "COMPLIANCE"


@dataclass
class KillSwitchRule:
    """A rule that can trigger the kill switch."""
    rule_id: str
    trigger: KillTrigger
    metric: str
    threshold: float
    direction: str = "above"  # above or below
    enabled: bool = True
    cooldown_seconds: int = 300
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class KillSwitchEvent:
    """Record of a kill switch activation."""
    event_id: str
    trigger: KillTrigger
    reason: str
    activated_by: str = "system"
    activated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    released_at: Optional[datetime] = None
    metrics_snapshot: dict[str, Any] = field(default_factory=dict)
    affected_strategies: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "trigger": self.trigger.value,
            "reason": self.reason,
            "activated_by": self.activated_by,
            "activated_at": self.activated_at.isoformat(),
            "released_at": self.released_at.isoformat() if self.released_at else None,
            "affected_strategies": self.affected_strategies,
        }


class KillSwitchController:
    """
    Centralized emergency stop mechanism for risk events.

    Immediately halts all trading activity when critical thresholds
    are breached. Supports multiple activation triggers, controlled
    release process, and full audit trail.

    Usage::

        controller = KillSwitchController()
        await controller.initialize()

        # Add rules
        controller.add_rule(KillSwitchRule(
            rule_id="pnl_kill_01",
            trigger=KillTrigger.PNL_LIMIT,
            metric="daily_pnl_pct",
            threshold=-10.0,
            direction="below",
        ))

        # Check conditions
        activated = await controller.check("daily_pnl_pct", -12.5)
        if activated:
            await controller.activate(KillTrigger.PNL_LIMIT, "Daily PnL -12.5%")
    """

    def __init__(self, require_dual_approval: bool = False) -> None:
        self._require_dual_approval = require_dual_approval
        self._status = KillSwitchStatus.ARMED
        self._rules: dict[str, KillSwitchRule] = {}
        self._event_history: list[KillSwitchEvent] = []
        self._active_event: Optional[KillSwitchEvent] = None
        self._event_counter: int = 0
        self._release_approvals: set[str] = set()
        self._lock = asyncio.Lock()
        self._initialized = False

    # ---- Properties ----

    @property
    def is_active(self) -> bool:
        return self._status == KillSwitchStatus.ACTIVE

    @property
    def status(self) -> KillSwitchStatus:
        return self._status

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize the kill switch controller."""
        self._initialized = True
        logger.info("KillSwitchController initialized (ARMED).")

    async def stop(self) -> None:
        """Stop the kill switch controller."""
        self._initialized = False
        logger.info("KillSwitchController stopped.")

    # ---- Rule Management ----

    def add_rule(self, rule: KillSwitchRule) -> None:
        """Add a kill switch trigger rule."""
        self._rules[rule.rule_id] = rule
        logger.info(f"Kill switch rule added: {rule.rule_id} ({rule.trigger.value})")

    def remove_rule(self, rule_id: str) -> None:
        """Remove a kill switch rule."""
        self._rules.pop(rule_id, None)
        logger.info(f"Kill switch rule removed: {rule_id}")

    def get_rules(self) -> dict[str, KillSwitchRule]:
        """Get all kill switch rules."""
        return dict(self._rules)

    # ---- Core API ----

    async def check(
        self,
        metric: str,
        value: float,
        metrics_snapshot: Optional[dict[str, Any]] = None,
    ) -> bool:
        """
        Check if a metric value triggers any kill switch rule.

        Returns True if any rule is triggered (but does NOT auto-activate).
        Call activate() separately after confirming.
        """
        if self._status == KillSwitchStatus.DISABLED:
            return False

        for rule in self._rules.values():
            if not rule.enabled:
                continue
            if rule.metric != metric:
                continue

            triggered = False
            if rule.direction == "above" and value > rule.threshold:
                triggered = True
            elif rule.direction == "below" and value < rule.threshold:
                triggered = True

            if triggered:
                logger.critical(
                    f"Kill switch rule triggered: {rule.rule_id} "
                    f"({metric}={value:.2f}, threshold={rule.threshold})"
                )
                return True

        return False

    async def activate(
        self,
        trigger: KillTrigger,
        reason: str,
        activated_by: str = "system",
        metrics_snapshot: Optional[dict[str, Any]] = None,
        affected_strategies: Optional[list[str]] = None,
    ) -> KillSwitchEvent:
        """
        Activate the kill switch.

        Immediately sets status to ACTIVE. All trading and new orders
        must be stopped. Returns the KillSwitchEvent for audit.
        """
        if self._status == KillSwitchStatus.DISABLED:
            logger.warning("Kill switch is DISABLED — activation ignored.")
            return KillSwitchEvent(
                event_id="REJECTED",
                trigger=trigger,
                reason="Kill switch is disabled",
            )

        async with self._lock:
            self._status = KillSwitchStatus.ACTIVE
            self._event_counter += 1

            event = KillSwitchEvent(
                event_id=f"KILL-{self._event_counter:06d}",
                trigger=trigger,
                reason=reason,
                activated_by=activated_by,
                metrics_snapshot=metrics_snapshot or {},
                affected_strategies=affected_strategies or [],
            )

            self._active_event = event
            self._event_history.append(event)

        logger.critical(
            f"KILL SWITCH ACTIVATED: {trigger.value} — {reason} "
            f"(event={event.event_id}, by={activated_by})"
        )

        return event

    async def release(
        self,
        approved_by: str = "",
        reason: str = "",
    ) -> bool:
        """
        Attempt to release the kill switch.

        If dual approval is required, both approvers must call release()
        before the kill switch is actually released.
        """
        if self._status != KillSwitchStatus.ACTIVE:
            logger.warning("Kill switch is not active — nothing to release.")
            return False

        if self._require_dual_approval:
            self._release_approvals.add(approved_by)
            if len(self._release_approvals) < 2:
                logger.info(
                    f"Kill switch release: 1/2 approvals received "
                    f"(from {approved_by})"
                )
                return False

        async with self._lock:
            self._status = KillSwitchStatus.ARMED

            if self._active_event:
                self._active_event.released_at = datetime.now(timezone.utc)

            self._release_approvals.clear()

        logger.warning(
            f"KILL SWITCH RELEASED: approved by {approved_by} — {reason}"
        )
        return True

    async def disable(self) -> None:
        """Disable the kill switch entirely (use with extreme caution)."""
        self._status = KillSwitchStatus.DISABLED
        logger.critical("Kill switch DISABLED — no protection active!")

    async def enable(self) -> None:
        """Re-enable the kill switch."""
        self._status = KillSwitchStatus.ARMED
        logger.info("Kill switch ARMED.")

    # ---- Query ----

    async def get_active_event(self) -> Optional[KillSwitchEvent]:
        """Get the currently active kill switch event."""
        return self._active_event

    async def get_event_history(self, limit: int = 100) -> list[KillSwitchEvent]:
        """Get kill switch event history."""
        return self._event_history[-limit:]

    async def get_status(self) -> dict[str, Any]:
        """Get detailed kill switch status."""
        return {
            "status": self._status.value,
            "is_active": self.is_active,
            "active_event": self._active_event.to_dict() if self._active_event else None,
            "rules_count": len(self._rules),
            "total_activations": self._event_counter,
            "require_dual_approval": self._require_dual_approval,
        }

    # ---- Stats ----

    async def get_stats(self) -> dict[str, Any]:
        """Get controller statistics."""
        return {
            "status": self._status.value,
            "rules": {
                rid: {"trigger": r.trigger.value, "enabled": r.enabled}
                for rid, r in self._rules.items()
            },
            "total_activations": self._event_counter,
        }

    async def health_check(self) -> dict[str, Any]:
        """Check controller health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "kill_switch_status": self._status.value,
            "rules_count": len(self._rules),
        }
