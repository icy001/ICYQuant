"""
GatePolicy — the deterministic decision procedure of the Trading Gate.

Evaluation order (spec section 24):

    1. Kill Switch                 (highest priority hard gate)
    2. System State
    3. Critical Component Health   (Risk / Execution / Event Bus)
    4. Trading State
    5. Recovery State
    6. Data Freshness
    7. Risk Decision
    8. Order Context

The first failing check produces a DENY with a canonical :class:`GateReason`.
Only when every check passes does the gate return ALLOW.

Severity convention:
    CRITICAL  → kill switch, critical-component health, position/ledger trust
    WARNING   → system not ready, trading halted, recovery, stale data, ...
    INFO      → ALLOW
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from ..domain.operational_state import OperationalState
from ..domain.system_state import SystemState
from ..domain.trading_state import TradingState
from ..health.health_status import HealthStatus
from ..health.readiness import DataFreshness
from ..kill_switch.kill_switch_state import KillSwitchState
from .gate_context import GateContext, RiskDecision
from .gate_decision import (
    GateDecision,
    GateDecisionRecord,
    GateSeverity,
)
from .gate_reason import GateReason

DEFAULT_POLICY_VERSION = "trading-policy-v1.0"


def _utcnow() -> datetime:
    from datetime import timezone

    return datetime.now(timezone.utc)


@dataclass
class GatePolicy:
    """Deterministic gate evaluation procedure."""

    version: str = DEFAULT_POLICY_VERSION
    require_system_ready: bool = True
    require_risk_approved: bool = True

    # ------------------------------------------------------------------
    # evaluate
    # ------------------------------------------------------------------

    def evaluate(
        self,
        context: GateContext,
        kill_switch=None,
        now: Optional[datetime] = None,
        correlation_id: str = "",
    ) -> GateDecisionRecord:
        now = now or _utcnow()
        snapshot = context.to_dict()

        # 1. Kill Switch — priority 0 hard gate, checked before everything.
        if kill_switch is not None:
            blocked = kill_switch.is_blocked(context.order)
            if blocked is not None:
                return self._record(
                    GateDecision.DENY,
                    GateReason.EMERGENCY_HALT,
                    GateSeverity.CRITICAL,
                    now,
                    correlation_id,
                    snapshot,
                    extra={
                        "kill_switch_scope": blocked.scope.value,
                        "kill_switch_scope_id": blocked.scope_id,
                    },
                )
        elif context.kill_switch_state is KillSwitchState.ACTIVE:
            return self._record(
                GateDecision.DENY,
                GateReason.EMERGENCY_HALT,
                GateSeverity.CRITICAL,
                now,
                correlation_id,
                snapshot,
                extra={"kill_switch_state": "ACTIVE"},
            )

        # 2. System State.
        if self.require_system_ready and context.system_state is not SystemState.READY:
            if context.system_state is SystemState.MAINTENANCE:
                reason, severity = GateReason.MAINTENANCE_MODE, GateSeverity.WARNING
            else:
                reason, severity = GateReason.SYSTEM_NOT_READY, GateSeverity.WARNING
            return self._record(
                GateDecision.DENY, reason, severity, now, correlation_id, snapshot
            )

        # 3. Critical Component Health.
        if context.risk_health is not HealthStatus.HEALTHY:
            return self._deny_health(GateReason.RISK_ENGINE_UNHEALTHY, now, correlation_id, snapshot)
        if context.execution_health is not HealthStatus.HEALTHY:
            return self._deny_health(GateReason.EXECUTION_ENGINE_UNHEALTHY, now, correlation_id, snapshot)
        if context.event_bus_health is not HealthStatus.HEALTHY:
            return self._deny_health(GateReason.EVENT_BUS_UNHEALTHY, now, correlation_id, snapshot)

        # 4. Trading State.
        if context.trading_state is TradingState.TRADING_HALTED:
            return self._record(
                GateDecision.DENY,
                GateReason.TRADING_HALTED,
                GateSeverity.WARNING,
                now,
                correlation_id,
                snapshot,
            )

        # 5. Recovery State — position state may be converging; no new orders.
        if context.active_recovery is not None and context.active_recovery.is_active:
            return self._record(
                GateDecision.DENY,
                GateReason.RECOVERY_IN_PROGRESS,
                GateSeverity.WARNING,
                now,
                correlation_id,
                snapshot,
            )

        # 6. Data Freshness — stale/expired market data cannot price new orders.
        if context.market_data_freshness in (DataFreshness.STALE, DataFreshness.EXPIRED):
            return self._record(
                GateDecision.DENY,
                GateReason.MARKET_DATA_STALE,
                GateSeverity.WARNING,
                now,
                correlation_id,
                snapshot,
            )

        # 7. Risk Decision — double authorisation: risk + gate must both pass.
        if self.require_risk_approved and context.risk_decision is not RiskDecision.APPROVED:
            return self._record(
                GateDecision.DENY,
                GateReason.RISK_NOT_APPROVED,
                GateSeverity.WARNING,
                now,
                correlation_id,
                snapshot,
            )

        # 8. Order Context — position/ledger trust and operational mode.
        if context.position_health is HealthStatus.UNHEALTHY:
            return self._deny_health(GateReason.POSITION_STATE_UNTRUSTED, now, correlation_id, snapshot)
        if context.ledger_health is HealthStatus.UNHEALTHY:
            return self._deny_health(GateReason.LEDGER_STATE_UNTRUSTED, now, correlation_id, snapshot)
        if context.operational_state is OperationalState.EMERGENCY:
            return self._record(
                GateDecision.DENY,
                GateReason.EMERGENCY_HALT,
                GateSeverity.CRITICAL,
                now,
                correlation_id,
                snapshot,
            )
        if context.operational_state is OperationalState.MAINTENANCE:
            return self._record(
                GateDecision.DENY,
                GateReason.MAINTENANCE_MODE,
                GateSeverity.WARNING,
                now,
                correlation_id,
                snapshot,
            )
        if context.operational_state is OperationalState.HALT:
            return self._record(
                GateDecision.DENY,
                GateReason.MANUAL_HALT,
                GateSeverity.WARNING,
                now,
                correlation_id,
                snapshot,
            )

        # All checks passed.
        return self._record(
            GateDecision.ALLOW,
            GateReason.SYSTEM_HEALTHY,
            GateSeverity.INFO,
            now,
            correlation_id,
            snapshot,
        )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _deny_health(
        self,
        reason: GateReason,
        now: datetime,
        correlation_id: str,
        snapshot: Dict[str, Any],
    ) -> GateDecisionRecord:
        return self._record(
            GateDecision.DENY, reason, GateSeverity.CRITICAL, now, correlation_id, snapshot
        )

    def _record(
        self,
        decision: GateDecision,
        reason: GateReason,
        severity: GateSeverity,
        now: datetime,
        correlation_id: str,
        snapshot: Dict[str, Any],
        extra: Optional[Dict[str, Any]] = None,
    ) -> GateDecisionRecord:
        snap = dict(snapshot)
        if extra:
            snap.update(extra)
        return GateDecisionRecord(
            decision=decision,
            reason=reason,
            severity=severity,
            evaluated_at=now,
            policy_version=self.version,
            correlation_id=correlation_id,
            snapshot=snap,
        )
