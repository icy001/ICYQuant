"""Trading Governor Service – orchestrates the full governance pipeline.

This is the top-level governance layer. It sits between the Decision Center
and the Execution Engine, and has the final say on whether a trade executes.
"""

from typing import Any, Dict, List, Optional

from .authority import RiskAuthorityController, RiskLimits
from .circuit_breaker import BreakerScope, GlobalCircuitBreaker
from .compliance import ComplianceAuthority
from .coordinator import Strategy, StrategyCoordinator, StrategyStatus
from .emergency import EmergencyController
from .health import SystemHealthMonitor
from .memory import GovernanceMemory
from .permission import PermissionDecision, TradingPermissionEngine
from .runtime import RuntimeMode, RuntimeModeManager


class TradingGovernorService:
    """Top-level governance service — the final gatekeeper before execution.

    Pipeline:
        Health Check → Permission Decision → Circuit Breaker Check
        → Risk Authority → Compliance → Runtime Mode → Final Authorization
    """

    def __init__(
        self,
        permission_engine: TradingPermissionEngine,
        health_monitor: Optional[SystemHealthMonitor] = None,
        circuit_breaker: Optional[GlobalCircuitBreaker] = None,
        coordinator: Optional[StrategyCoordinator] = None,
        risk_authority: Optional[RiskAuthorityController] = None,
        compliance_authority: Optional[ComplianceAuthority] = None,
        emergency_controller: Optional[EmergencyController] = None,
        runtime_manager: Optional[RuntimeModeManager] = None,
        memory: Optional[GovernanceMemory] = None,
    ) -> None:
        self.permission_engine = permission_engine
        self.health_monitor = health_monitor or SystemHealthMonitor()
        self.circuit_breaker = circuit_breaker or GlobalCircuitBreaker()
        self.coordinator = coordinator or StrategyCoordinator()
        self.risk_authority = risk_authority or RiskAuthorityController()
        self.compliance_authority = compliance_authority or ComplianceAuthority()
        self.emergency = emergency_controller or EmergencyController()
        self.runtime = runtime_manager or RuntimeModeManager()
        self.memory = memory or GovernanceMemory()

    def authorize(
        self,
        health: float,
        risk_ok: bool,
        compliance_ok: bool,
    ) -> str:
        """Simple authorization: health + risk + compliance → permission.

        Args:
            health: system health score (0-100).
            risk_ok: risk checks passed.
            compliance_ok: compliance checks passed.

        Returns:
            Permission string: "ALLOW", "LIMIT", "PAUSE", "BLOCK".
        """
        return self.permission_engine.decide(health, risk_ok, compliance_ok)

    def authorize_full(
        self,
        health_metrics: Dict[str, float],
        risk_ok: bool,
        compliance_ok: bool,
        confidence: float = 1.0,
        market_open: bool = True,
        symbol: str = "",
        risk_score: float = 0.0,
    ) -> Dict[str, Any]:
        """Full governance pipeline authorization.

        Pipeline:
        1. System health evaluation
        2. Emergency / circuit breaker check
        3. Compliance validation
        4. Risk authority limits
        5. Runtime mode check
        6. Permission decision
        7. Record in governance memory

        Args:
            health_metrics: component health scores.
            risk_ok: risk checks passed.
            compliance_ok: compliance checks passed.
            confidence: overall AI confidence.
            market_open: whether market is open.
            symbol: trading symbol for compliance check.
            risk_score: current risk score for authority limits.

        Returns:
            Complete governance report dict.
        """
        # 1. System health
        health_report = self.health_monitor.evaluate_full(health_metrics)
        health_score = health_report.score

        # 2. Emergency / circuit breaker check
        breaker_active = self.circuit_breaker.active or self.emergency.is_active
        if self.emergency.is_active:
            breaker_active = True

        # 3. Compliance
        if symbol:
            compliance_passed = self.compliance_authority.is_approved(symbol)
            compliance_ok = compliance_ok and compliance_passed

        # 4. Risk authority
        limits = self.risk_authority.adjust_all(risk_score) if risk_score > 0 else self.risk_authority.current_limits

        # 5. Runtime mode
        runtime_mode = self.runtime.current_mode_value
        if self.runtime.is_safe():
            market_open = False  # safe mode overrides

        # 6. Permission decision
        decision = self.permission_engine.decide_full(
            health=health_score,
            risk_ok=risk_ok,
            compliance_ok=compliance_ok,
            confidence=confidence,
            market_open=market_open,
            circuit_breaker_active=breaker_active,
        )

        # 7. Record
        self.memory.record_permission(
            permission=decision.permission.value,
            reason=decision.reason,
            details=decision.details,
        )

        return {
            "permission": decision.permission.value,
            "reason": decision.reason,
            "health": {
                "score": health_score,
                "status": health_report.status.value,
                "components": health_report.components,
                "unhealthy": health_report.details.get("unhealthy_components", []),
            },
            "circuit_breaker": {
                "active": breaker_active,
                "scoped_breakers": len(self.circuit_breaker.get_active_breakers()),
            },
            "compliance": {
                "approved": compliance_ok,
            },
            "risk_limits": {
                "leverage": limits.leverage_limit,
                "max_position": limits.max_position,
                "exposure": limits.exposure_limit,
                "daily_loss": limits.daily_loss_limit,
            },
            "runtime": {
                "mode": runtime_mode,
                "is_live": self.runtime.is_live(),
            },
            "decision": decision.details,
        }

    def kill_switch(self, reason: str = "Manual kill switch") -> Dict[str, Any]:
        """Emergency kill switch — stop everything immediately."""
        self.circuit_breaker.kill_switch(reason)
        self.emergency.kill_switch(reason)
        self.runtime.safe_mode(reason)
        self.coordinator.pause_all()

        self.memory.record_emergency("kill_switch", reason)

        return {
            "action": "kill_switch",
            "reason": reason,
            "circuit_breaker": self.circuit_breaker.active,
            "emergency": self.emergency.is_active,
            "runtime_mode": self.runtime.current_mode_value,
        }

    def register_strategy(self, name: str, priority: int = 1) -> Strategy:
        s = Strategy(name=name, priority=priority)
        self.coordinator.register(s)
        return s
