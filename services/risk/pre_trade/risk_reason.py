"""
Pre-Trade Risk Reason — Structured reason model for risk decisions.

Every rejection or escalation must carry a machine-readable reason
for downstream analysis, alerting, and audit trails.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class ReasonSeverity(str, Enum):
    """Severity of the risk reason."""
    INFO = "INFO"
    WARNING = "WARNING"
    BLOCKING = "BLOCKING"
    CRITICAL = "CRITICAL"


class ReasonCategory(str, Enum):
    """Category of the risk reason."""
    POSITION_LIMIT = "position_limit"
    EXPOSURE_LIMIT = "exposure_limit"
    LEVERAGE = "leverage"
    MARGIN = "margin"
    BUYING_POWER = "buying_power"
    CASH = "cash"
    CONCENTRATION = "concentration"
    LIQUIDITY = "liquidity"
    VOLATILITY = "volatility"
    INSTRUMENT_PERMISSION = "instrument_permission"
    COMPLIANCE = "compliance"
    ORDER_SIZE = "order_size"
    RATE_LIMIT = "rate_limit"
    TRADING_SESSION = "trading_session"
    MARKET_STATUS = "market_status"
    GENERAL = "general"


@dataclass(frozen=True)
class RiskReason:
    """
    Structured risk reason produced by a checker.

    Each checker that fails or warns produces one or more reasons
    explaining what went wrong and how to resolve it.

    Usage::

        reason = RiskReason.blocking(
            category=ReasonCategory.POSITION_LIMIT,
            message="Position limit exceeded for AAPL: 1,500 > 1,000 max.",
            current_value=1500.0,
            limit=1000.0,
            checker="PositionLimitChecker",
        )
    """

    reason_id: str = field(default_factory=lambda: uuid4().hex)
    category: ReasonCategory = ReasonCategory.GENERAL
    severity: ReasonSeverity = ReasonSeverity.WARNING
    checker: str = ""
    rule_id: str = ""
    message: str = ""

    # ---- Quantitative Context ----
    current_value: Optional[float] = None
    limit: Optional[float] = None
    threshold_pct: Optional[float] = None

    # ---- Resolution ----
    resolution: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ---- Factory Methods ----

    @classmethod
    def blocking(
        cls,
        category: ReasonCategory,
        message: str,
        checker: str = "",
        rule_id: str = "",
        current_value: Optional[float] = None,
        limit: Optional[float] = None,
        resolution: str = "",
        **kwargs: Any,
    ) -> RiskReason:
        return cls(
            category=category,
            severity=ReasonSeverity.BLOCKING,
            checker=checker,
            rule_id=rule_id,
            message=message,
            current_value=current_value,
            limit=limit,
            threshold_pct=(current_value / limit) if (current_value and limit) else None,
            resolution=resolution,
            **kwargs,
        )

    @classmethod
    def warning(
        cls,
        category: ReasonCategory,
        message: str,
        checker: str = "",
        rule_id: str = "",
        current_value: Optional[float] = None,
        limit: Optional[float] = None,
        resolution: str = "",
        **kwargs: Any,
    ) -> RiskReason:
        return cls(
            category=category,
            severity=ReasonSeverity.WARNING,
            checker=checker,
            rule_id=rule_id,
            message=message,
            current_value=current_value,
            limit=limit,
            threshold_pct=(current_value / limit) if (current_value and limit) else None,
            resolution=resolution,
            **kwargs,
        )

    @classmethod
    def info(
        cls,
        category: ReasonCategory,
        message: str,
        checker: str = "",
        **kwargs: Any,
    ) -> RiskReason:
        return cls(
            category=category,
            severity=ReasonSeverity.INFO,
            checker=checker,
            message=message,
            **kwargs,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason_id": self.reason_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "checker": self.checker,
            "rule_id": self.rule_id,
            "message": self.message,
            "current_value": self.current_value,
            "limit": self.limit,
            "threshold_pct": self.threshold_pct,
            "resolution": self.resolution,
            "created_at": self.created_at.isoformat(),
        }
