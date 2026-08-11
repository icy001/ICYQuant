"""
Kill Switch
===========
Automatic strategy circuit breaker for risk management.

Triggers on:
    - Max drawdown exceeded
    - Loss limit breached
    - Risk event detected
    - Abnormal behavior
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class KillReason(str, Enum):
    DRAWDOWN = "drawdown"
    LOSS_LIMIT = "loss_limit"
    RISK_EVENT = "risk_event"
    ABNORMAL_BEHAVIOR = "abnormal_behavior"
    MANUAL = "manual"
    COMPLIANCE = "compliance"


@dataclass
class KillSwitchRule:
    """A kill switch rule definition."""
    rule_id: str = field(default_factory=lambda: f"ksr_{uuid4().hex[:8]}")
    name: str = ""
    reason: KillReason = KillReason.DRAWDOWN
    threshold: float = 0.0
    window_days: int = 1
    enabled: bool = True
    auto_reset_hours: int = 24  # Hours before auto-reset (0 = no auto-reset)


@dataclass
class KillSwitchEvent:
    """A kill switch activation event."""
    event_id: str = field(default_factory=lambda: f"kse_{uuid4().hex[:8]}")
    strategy_id: str = ""
    rule_id: str = ""
    reason: KillReason = KillReason.DRAWDOWN
    threshold: float = 0.0
    actual_value: float = 0.0
    message: str = ""
    triggered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None


class KillSwitch:
    """Automatic strategy circuit breaker.

    Pipeline:
        Drawdown → Loss Limit → Risk Event → Stop Strategy
    """

    # Default rules
    DEFAULT_RULES: List[KillSwitchRule] = [
        KillSwitchRule(
            name="Max Drawdown (20%)",
            reason=KillReason.DRAWDOWN,
            threshold=0.20,
            window_days=30,
        ),
        KillSwitchRule(
            name="Daily Loss Limit (5%)",
            reason=KillReason.LOSS_LIMIT,
            threshold=0.05,
            window_days=1,
        ),
        KillSwitchRule(
            name="Weekly Loss Limit (10%)",
            reason=KillReason.LOSS_LIMIT,
            threshold=0.10,
            window_days=7,
        ),
    ]

    def __init__(self):
        self._rules: List[KillSwitchRule] = list(self.DEFAULT_RULES)
        self._triggered: Dict[str, List[KillSwitchEvent]] = {}  # strategy_id → events
        self._active_switches: Dict[str, KillSwitchEvent] = {}  # strategy_id → active event
        self._strategy_metrics: Dict[str, Dict[str, Any]] = {}
        self.is_initialized = False

    async def initialize(self) -> None:
        self.is_initialized = True
        logger.info("KillSwitch initialized with %d rules", len(self._rules))

    # ------------------------------------------------------------------
    # Rule Management
    # ------------------------------------------------------------------

    def add_rule(self, rule: KillSwitchRule) -> None:
        self._rules.append(rule)

    def remove_rule(self, rule_id: str) -> None:
        self._rules = [r for r in self._rules if r.rule_id != rule_id]

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    async def evaluate(self, strategy_id: str,
                       metrics: Dict[str, Any]) -> Optional[KillSwitchEvent]:
        """Evaluate all kill switch rules for a strategy."""
        self._strategy_metrics[strategy_id] = metrics

        for rule in self._rules:
            if not rule.enabled:
                continue

            triggered = await self._check_rule(strategy_id, rule, metrics)
            if triggered:
                self._active_switches[strategy_id] = triggered
                logger.critical(
                    "KILL SWITCH TRIGGERED: strategy=%s reason=%s threshold=%s actual=%s",
                    strategy_id, triggered.reason.value,
                    triggered.threshold, triggered.actual_value,
                )
                return triggered

        return None

    async def _check_rule(self, strategy_id: str, rule: KillSwitchRule,
                          metrics: Dict[str, Any]) -> Optional[KillSwitchEvent]:
        """Check a single rule against strategy metrics."""
        actual_value = 0.0
        triggered = False

        if rule.reason == KillReason.DRAWDOWN:
            actual_value = abs(metrics.get("max_drawdown", 0))
            triggered = actual_value > rule.threshold

        elif rule.reason == KillReason.LOSS_LIMIT:
            actual_value = abs(metrics.get("period_return", 0))
            triggered = actual_value < -rule.threshold

        elif rule.reason == KillReason.RISK_EVENT:
            var_breach = metrics.get("var_breach", False)
            triggered = var_breach

        elif rule.reason == KillReason.ABNORMAL_BEHAVIOR:
            # Check for anomalous patterns
            trade_frequency = metrics.get("trade_frequency", 0)
            avg_trades = metrics.get("avg_trade_frequency", 0)
            if avg_trades > 0 and trade_frequency > avg_trades * 5:
                triggered = True

        if triggered:
            event = KillSwitchEvent(
                strategy_id=strategy_id,
                rule_id=rule.rule_id,
                reason=rule.reason,
                threshold=rule.threshold,
                actual_value=actual_value,
                message=f"{rule.name}: {actual_value:.4f} > threshold {rule.threshold:.4f}",
            )
            if strategy_id not in self._triggered:
                self._triggered[strategy_id] = []
            self._triggered[strategy_id].append(event)
            return event

        return None

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def is_triggered(self, strategy_id: str) -> bool:
        """Check if kill switch is active for a strategy."""
        return strategy_id in self._active_switches

    def get_active_event(self, strategy_id: str) -> Optional[KillSwitchEvent]:
        return self._active_switches.get(strategy_id)

    async def reset(self, strategy_id: str) -> bool:
        """Manually reset the kill switch for a strategy."""
        if strategy_id in self._active_switches:
            event = self._active_switches.pop(strategy_id)
            event.resolved_at = datetime.now(timezone.utc)
            logger.info("Kill switch reset for strategy %s", strategy_id)
            return True
        return False

    def active_switches(self) -> Dict[str, KillSwitchEvent]:
        return dict(self._active_switches)

    def triggered_strategies(self) -> List[str]:
        return list(self._active_switches.keys())

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "rules_configured": len(self._rules),
            "rules_enabled": sum(1 for r in self._rules if r.enabled),
            "active_switches": len(self._active_switches),
            "total_triggered": sum(len(v) for v in self._triggered.values()),
            "triggered_strategies": self.triggered_strategies(),
        }
