"""
Governance Signal — unified signal representation for the monitor layer.

Part 1.5: all governance observations and detections are converted into
GovernanceSignal objects, which feed into the control plane.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional

from .control_trigger import Severity


class SignalType(Enum):
    """Types of governance signals."""

    # Risk signals
    RISK_BREACH = auto()
    DRAWDOWN_BREACH = auto()
    VAR_BREACH = auto()
    EXPOSURE_BREACH = auto()
    LEVERAGE_BREACH = auto()
    LIQUIDITY_BREACH = auto()

    # Policy signals
    POLICY_BREACH = auto()
    POLICY_INTEGRITY_FAILURE = auto()

    # Authority signals
    AUTHORITY_BREACH = auto()
    AUTHORITY_COMPROMISE = auto()

    # Approval signals
    APPROVAL_SCOPE_BREACH = auto()
    APPROVAL_EXPIRY = auto()

    # Execution signals
    EXECUTION_ANOMALY = auto()
    SLIPPAGE_BREACH = auto()

    # Audit signals
    AUDIT_INTEGRITY_FAILURE = auto()
    AUDIT_CHAIN_BREAK = auto()

    # Infrastructure signals
    SERVICE_DEGRADATION = auto()
    DATA_INTEGRITY_FAILURE = auto()
    RISK_ENGINE_UNAVAILABLE = auto()


@dataclass
class GovernanceSignal:
    """A governance signal produced by monitoring/detection.

    This is the unified format all guardians and detectors emit.
    """

    signal_id: str = field(default_factory=lambda: f"GSIG-{uuid.uuid4().hex[:12].upper()}")
    signal_type: SignalType = SignalType.RISK_BREACH
    severity: Severity = Severity.INFO
    source: str = ""
    description: str = ""
    value: Any = None
    threshold: Any = None
    target_state: str = ""
    actor: str = ""
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
            "signal_id": self.signal_id,
            "signal_type": self.signal_type.name,
            "severity": self.severity.name,
            "source": self.source,
            "description": self.description,
            "value": self.value,
            "threshold": self.threshold,
            "target_state": self.target_state,
            "actor": self.actor,
            "observed_at": self.observed_at,
            "correlation_id": self.correlation_id,
            "metadata": self.metadata,
        }

    @classmethod
    def create(
        cls,
        signal_type: SignalType,
        severity: Severity,
        value: Any,
        threshold: Any,
        source: str = "",
        description: str = "",
        correlation_id: str = "",
        **kwargs,
    ) -> "GovernanceSignal":
        return cls(
            signal_type=signal_type,
            severity=severity,
            value=value,
            threshold=threshold,
            source=source,
            description=description or f"{signal_type.name}: {value} vs threshold {threshold}",
            correlation_id=correlation_id,
            **kwargs,
        )
