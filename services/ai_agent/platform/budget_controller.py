"""Budget Controller — enforces spending limits across users, projects, and the platform.

The BudgetController integrates with the CostManager and TokenManager to
enforce spending limits at multiple levels. It supports per-user, per-project,
daily, and monthly budgets with configurable alert thresholds and actions.

Budget enforcement:
    - Soft limit: warning only
    - Hard limit: block further calls
    - Alert thresholds: 50%, 80%, 90%, 100%
    - Per-user daily/monthly caps
    - Per-project daily/monthly caps
    - Platform-wide monthly cap
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class BudgetStatus(str, Enum):
    """Budget consumption status."""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    EXCEEDED = "exceeded"


@dataclass
class BudgetConfig:
    """Budget configuration for a scope (user/project/platform)."""
    scope_id: str = ""
    scope_type: str = "user"  # user, project, platform
    daily_limit_usd: float = 10.0
    monthly_limit_usd: float = 100.0
    warning_threshold_pct: float = 0.50
    critical_threshold_pct: float = 0.80
    hard_limit: bool = True
    enabled: bool = True


@dataclass
class BudgetState:
    """Runtime state of a budget."""
    config: BudgetConfig
    daily_spent: float = 0.0
    monthly_spent: float = 0.0
    daily_reset: float = field(default_factory=time.monotonic)
    monthly_reset: float = field(default_factory=time.monotonic)
    status: BudgetStatus = BudgetStatus.NORMAL
    alerts_sent: int = 0


class BudgetController:
    """Enforces spending limits across the AI platform.

    Monitors real-time spending against configured budgets and enforces
    limits with configurable actions (warn, block, notify).

    Usage:
        bc = BudgetController()
        await bc.initialize()
        bc.set_budget(BudgetConfig(scope_id="user_1", daily_limit_usd=5.0))
        can_proceed, reason = bc.check_budget("user_1")
    """

    def __init__(self) -> None:
        self._budgets: Dict[str, BudgetState] = {}
        self._alert_callbacks: List[Callable] = []
        self._blocked_count: int = 0
        self._initialized: bool = False
        self._lock = threading.Lock()
        logger.info("BudgetController created")

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("BudgetController initialized")

    async def shutdown(self) -> None:
        with self._lock:
            self._budgets.clear()
            self._alert_callbacks.clear()
        self._initialized = False
        logger.info("BudgetController shutdown complete")

    def set_budget(self, config: BudgetConfig) -> None:
        """Set or update a budget for a scope."""
        with self._lock:
            self._budgets[config.scope_id] = BudgetState(config=config)
            logger.info("BudgetController: budget set for %s (daily=$%.2f, monthly=$%.2f)", config.scope_id, config.daily_limit_usd, config.monthly_limit_usd)

    def remove_budget(self, scope_id: str) -> bool:
        """Remove a budget."""
        with self._lock:
            if scope_id in self._budgets:
                del self._budgets[scope_id]
                return True
            return False

    def record_spending(self, scope_id: str, amount_usd: float) -> BudgetStatus:
        """Record spending against a budget and return current status."""
        with self._lock:
            state = self._budgets.get(scope_id)
            if not state or not state.config.enabled:
                return BudgetStatus.NORMAL

            now = time.monotonic()

            # Reset daily if needed
            if now - state.daily_reset > 86400.0:
                state.daily_spent = 0.0
                state.daily_reset = now

            # Reset monthly if needed
            if now - state.monthly_reset > 2592000.0:  # ~30 days
                state.monthly_spent = 0.0
                state.monthly_reset = now

            state.daily_spent += amount_usd
            state.monthly_spent += amount_usd

            # Determine status
            config = state.config
            daily_pct = state.daily_spent / config.daily_limit_usd if config.daily_limit_usd > 0 else 0
            monthly_pct = state.monthly_spent / config.monthly_limit_usd if config.monthly_limit_usd > 0 else 0
            max_pct = max(daily_pct, monthly_pct)

            if max_pct >= 1.0:
                state.status = BudgetStatus.EXCEEDED
                self._blocked_count += 1
                self._fire_alerts(scope_id, state)
            elif max_pct >= config.critical_threshold_pct:
                state.status = BudgetStatus.CRITICAL
                self._fire_alerts(scope_id, state)
            elif max_pct >= config.warning_threshold_pct:
                state.status = BudgetStatus.WARNING
            else:
                state.status = BudgetStatus.NORMAL

            logger.debug("BudgetController: %s spent $%.4f (daily=%.0f%%, monthly=%.0f%%, status=%s)", scope_id, amount_usd, daily_pct * 100, monthly_pct * 100, state.status.value)
            return state.status

    def check_budget(self, scope_id: str) -> tuple:
        """Check if a scope has remaining budget. Returns (allowed, reason)."""
        with self._lock:
            state = self._budgets.get(scope_id)
            if not state or not state.config.enabled:
                return True, ""

            if state.status == BudgetStatus.EXCEEDED and state.config.hard_limit:
                return False, f"Budget exceeded for {scope_id} (daily=${state.daily_spent:.2f}/${state.config.daily_limit_usd:.2f}, monthly=${state.monthly_spent:.2f}/${state.config.monthly_limit_usd:.2f})"

            return True, ""

    def register_alert_callback(self, callback: Callable) -> None:
        """Register a callback for budget alerts."""
        self._alert_callbacks.append(callback)

    def _fire_alerts(self, scope_id: str, state: BudgetState) -> None:
        """Fire alert callbacks for budget threshold crossings."""
        state.alerts_sent += 1
        for callback in self._alert_callbacks:
            try:
                callback(scope_id, state)
            except Exception as e:
                logger.error("BudgetController alert callback error: %s", e)

    def get_budget_status(self, scope_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed budget status for a scope."""
        state = self._budgets.get(scope_id)
        if not state:
            return None
        config = state.config
        return {
            "scope_id": scope_id,
            "scope_type": config.scope_type,
            "status": state.status.value,
            "daily_spent": round(state.daily_spent, 4),
            "daily_limit": config.daily_limit_usd,
            "daily_pct": round(state.daily_spent / config.daily_limit_usd * 100, 1) if config.daily_limit_usd > 0 else 0,
            "monthly_spent": round(state.monthly_spent, 4),
            "monthly_limit": config.monthly_limit_usd,
            "monthly_pct": round(state.monthly_spent / config.monthly_limit_usd * 100, 1) if config.monthly_limit_usd > 0 else 0,
            "alerts_sent": state.alerts_sent,
            "hard_limit": config.hard_limit,
            "enabled": config.enabled,
        }

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            exceeded = sum(1 for s in self._budgets.values() if s.status == BudgetStatus.EXCEEDED)
            critical = sum(1 for s in self._budgets.values() if s.status == BudgetStatus.CRITICAL)
            warning = sum(1 for s in self._budgets.values() if s.status == BudgetStatus.WARNING)
            return {
                "initialized": self._initialized,
                "total_budgets": len(self._budgets),
                "exceeded": exceeded,
                "critical": critical,
                "warning": warning,
                "normal": len(self._budgets) - exceeded - critical - warning,
                "total_blocked": self._blocked_count,
            }
