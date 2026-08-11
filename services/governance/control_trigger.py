"""
Control Trigger — conditions that trigger control plane actions.

Part 1.5: defines the trigger types that the control plane monitors
and responds to.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional


class TriggerCategory(Enum):
    """High-level trigger categories."""

    RISK = auto()
    POLICY = auto()
    AUTHORITY = auto()
    APPROVAL = auto()
    EXECUTION = auto()
    AUDIT = auto()
    MARKET = auto()
    INFRASTRUCTURE = auto()


class TriggerType(Enum):
    """Specific trigger types."""

    # Risk triggers
    DRAWDOWN_BREACH = auto()
    VAR_BREACH = auto()
    EXPOSURE_BREACH = auto()
    LEVERAGE_BREACH = auto()
    LIQUIDITY_BREACH = auto()
    CONCENTRATION_BREACH = auto()
    STRESS_BREACH = auto()
    CORRELATION_BREACH = auto()
    COUNTERPARTY_BREACH = auto()

    # Policy triggers
    POLICY_BREACH = auto()
    POLICY_INTEGRITY_FAILURE = auto()
    POLICY_VERSION_MISMATCH = auto()
    POLICY_CONFLICT = auto()

    # Authority triggers
    AUTHORITY_BREACH = auto()
    AUTHORITY_COMPROMISE = auto()
    AUTHORITY_EXPIRY = auto()
    DELEGATION_CASCADE = auto()

    # Approval triggers
    APPROVAL_SCOPE_BREACH = auto()
    APPROVAL_EXPIRY = auto()
    APPROVAL_ANOMALY = auto()

    # Execution triggers
    EXECUTION_ANOMALY = auto()
    SLIPPAGE_BREACH = auto()
    ORDER_REJECTION_SPIKE = auto()
    LATENCY_BREACH = auto()

    # Audit triggers
    AUDIT_INTEGRITY_FAILURE = auto()
    AUDIT_CHAIN_BREAK = auto()
    AUDIT_HASH_MISMATCH = auto()
    AUDIT_COMPLETENESS_FAILURE = auto()

    # Market triggers
    MARKET_SHOCK = auto()
    VOLATILITY_SPIKE = auto()
    CIRCUIT_BREAKER = auto()

    # Infrastructure triggers
    SERVICE_DEGRADATION = auto()
    DATA_INTEGRITY_FAILURE = auto()
    RISK_ENGINE_UNAVAILABLE = auto()

    @property
    def category(self) -> TriggerCategory:
        cat_map = {
            TriggerType.DRAWDOWN_BREACH: TriggerCategory.RISK,
            TriggerType.VAR_BREACH: TriggerCategory.RISK,
            TriggerType.EXPOSURE_BREACH: TriggerCategory.RISK,
            TriggerType.LEVERAGE_BREACH: TriggerCategory.RISK,
            TriggerType.LIQUIDITY_BREACH: TriggerCategory.RISK,
            TriggerType.CONCENTRATION_BREACH: TriggerCategory.RISK,
            TriggerType.STRESS_BREACH: TriggerCategory.RISK,
            TriggerType.CORRELATION_BREACH: TriggerCategory.RISK,
            TriggerType.COUNTERPARTY_BREACH: TriggerCategory.RISK,
            TriggerType.POLICY_BREACH: TriggerCategory.POLICY,
            TriggerType.POLICY_INTEGRITY_FAILURE: TriggerCategory.POLICY,
            TriggerType.POLICY_VERSION_MISMATCH: TriggerCategory.POLICY,
            TriggerType.POLICY_CONFLICT: TriggerCategory.POLICY,
            TriggerType.AUTHORITY_BREACH: TriggerCategory.AUTHORITY,
            TriggerType.AUTHORITY_COMPROMISE: TriggerCategory.AUTHORITY,
            TriggerType.AUTHORITY_EXPIRY: TriggerCategory.AUTHORITY,
            TriggerType.DELEGATION_CASCADE: TriggerCategory.AUTHORITY,
            TriggerType.APPROVAL_SCOPE_BREACH: TriggerCategory.APPROVAL,
            TriggerType.APPROVAL_EXPIRY: TriggerCategory.APPROVAL,
            TriggerType.APPROVAL_ANOMALY: TriggerCategory.APPROVAL,
            TriggerType.EXECUTION_ANOMALY: TriggerCategory.EXECUTION,
            TriggerType.SLIPPAGE_BREACH: TriggerCategory.EXECUTION,
            TriggerType.ORDER_REJECTION_SPIKE: TriggerCategory.EXECUTION,
            TriggerType.LATENCY_BREACH: TriggerCategory.EXECUTION,
            TriggerType.AUDIT_INTEGRITY_FAILURE: TriggerCategory.AUDIT,
            TriggerType.AUDIT_CHAIN_BREAK: TriggerCategory.AUDIT,
            TriggerType.AUDIT_HASH_MISMATCH: TriggerCategory.AUDIT,
            TriggerType.AUDIT_COMPLETENESS_FAILURE: TriggerCategory.AUDIT,
            TriggerType.MARKET_SHOCK: TriggerCategory.MARKET,
            TriggerType.VOLATILITY_SPIKE: TriggerCategory.MARKET,
            TriggerType.CIRCUIT_BREAKER: TriggerCategory.MARKET,
            TriggerType.SERVICE_DEGRADATION: TriggerCategory.INFRASTRUCTURE,
            TriggerType.DATA_INTEGRITY_FAILURE: TriggerCategory.INFRASTRUCTURE,
            TriggerType.RISK_ENGINE_UNAVAILABLE: TriggerCategory.INFRASTRUCTURE,
        }
        return cat_map.get(self, TriggerCategory.RISK)


class Severity(Enum):
    """Unified severity levels for governance signals."""

    INFO = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4
    FATAL = 5

    @property
    def label(self) -> str:
        return self.name


@dataclass
class ControlTrigger:
    """A control trigger representing a detected condition."""

    trigger_id: str = ""
    trigger_type: TriggerType = TriggerType.POLICY_BREACH
    severity: Severity = Severity.INFO
    source: str = ""
    description: str = ""
    value: Any = None
    threshold: Any = None
    observed_at: float = field(default_factory=time.time)
    correlation_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_critical(self) -> bool:
        return self.severity in (Severity.CRITICAL, Severity.FATAL)

    @property
    def requires_immediate_action(self) -> bool:
        return self.severity >= Severity.HIGH

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "trigger_type": self.trigger_type.name,
            "severity": self.severity.name,
            "source": self.source,
            "description": self.description,
            "value": self.value,
            "threshold": self.threshold,
            "observed_at": self.observed_at,
            "correlation_id": self.correlation_id,
        }
