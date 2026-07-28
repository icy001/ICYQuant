"""Trading Permission Engine – determines whether trading is ALLOWED, LIMITED, PAUSED, or BLOCKED."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class Permission(Enum):
    ALLOW = "ALLOW"
    LIMIT = "LIMIT"
    PAUSE = "PAUSE"
    BLOCK = "BLOCK"


@dataclass
class PermissionDecision:
    permission: Permission
    reason: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class TradingPermissionEngine:
    """Decides whether the system is allowed to trade.

    Evaluates system health, risk, compliance, market state, and AI confidence
    to produce one of: ALLOW, LIMIT, PAUSE, BLOCK.
    """

    HEALTH_BLOCK_THRESHOLD = 60
    HEALTH_PAUSE_THRESHOLD = 75
    MIN_CONFIDENCE = 0.5

    def decide(
        self,
        health: float,
        risk_ok: bool,
        compliance_ok: bool,
        confidence: float = 1.0,
        market_open: bool = True,
        circuit_breaker_active: bool = False,
    ) -> str:
        """Decide trading permission level.

        Args:
            health: system health score (0-100).
            risk_ok: whether risk checks pass.
            compliance_ok: whether compliance checks pass.
            confidence: overall AI confidence (0-1).
            market_open: whether market is open.
            circuit_breaker_active: whether circuit breaker is triggered.

        Returns:
            One of "ALLOW", "LIMIT", "PAUSE", "BLOCK".
        """
        # Hard blocks
        if circuit_breaker_active:
            return Permission.BLOCK.value
        if not compliance_ok:
            return Permission.BLOCK.value
        if not market_open:
            return Permission.BLOCK.value
        if health < self.HEALTH_BLOCK_THRESHOLD:
            return Permission.BLOCK.value

        # Pause
        if health < self.HEALTH_PAUSE_THRESHOLD:
            return Permission.PAUSE.value
        if confidence < self.MIN_CONFIDENCE:
            return Permission.PAUSE.value

        # Limit
        if not risk_ok:
            return Permission.LIMIT.value

        return Permission.ALLOW.value

    def decide_full(
        self,
        health: float,
        risk_ok: bool,
        compliance_ok: bool,
        confidence: float = 1.0,
        market_open: bool = True,
        circuit_breaker_active: bool = False,
        exposure_pct: float = 0.0,
        max_exposure_pct: float = 100.0,
    ) -> PermissionDecision:
        """Full permission decision with detailed reasoning.

        Returns:
            PermissionDecision with level, reason, and details.
        """
        reasons = []

        if circuit_breaker_active:
            return PermissionDecision(
                permission=Permission.BLOCK,
                reason="Global circuit breaker is active",
                details={"circuit_breaker": True},
            )

        if not compliance_ok:
            return PermissionDecision(
                permission=Permission.BLOCK,
                reason="Compliance validation failed",
                details={"compliance": False},
            )

        if not market_open:
            return PermissionDecision(
                permission=Permission.BLOCK,
                reason="Market is closed",
                details={"market_open": False},
            )

        if health < self.HEALTH_BLOCK_THRESHOLD:
            return PermissionDecision(
                permission=Permission.BLOCK,
                reason=f"System health critical ({health:.0f}%)",
                details={"health": health},
            )

        if health < self.HEALTH_PAUSE_THRESHOLD:
            reasons.append(f"System health degraded ({health:.0f}%)")

        if confidence < self.MIN_CONFIDENCE:
            reasons.append(f"AI confidence low ({confidence:.0%})")

        if reasons:
            return PermissionDecision(
                permission=Permission.PAUSE,
                reason="; ".join(reasons),
                details={"health": health, "confidence": confidence},
            )

        if not risk_ok:
            return PermissionDecision(
                permission=Permission.LIMIT,
                reason="Risk limits exceeded",
                details={"risk_ok": False},
            )

        if exposure_pct >= max_exposure_pct:
            return PermissionDecision(
                permission=Permission.LIMIT,
                reason=f"Exposure at limit ({exposure_pct:.0f}%)",
                details={"exposure": exposure_pct, "limit": max_exposure_pct},
            )

        return PermissionDecision(
            permission=Permission.ALLOW,
            reason="All checks passed",
            details={
                "health": health,
                "risk_ok": risk_ok,
                "compliance_ok": compliance_ok,
                "confidence": confidence,
                "market_open": market_open,
            },
        )
