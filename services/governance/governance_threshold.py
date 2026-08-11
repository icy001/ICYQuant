"""
Governance Threshold — threshold definitions for governance monitoring.

Part 1.5: defines configurable thresholds that trigger governance state
transitions and actions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .control_trigger import TriggerType, Severity
from .control_state import GovernanceStateType


@dataclass
class GovernanceThreshold:
    """A threshold that maps a metric value to a governance state transition."""

    threshold_id: str = ""
    name: str = ""
    metric: str = ""              # Metric name to monitor
    trigger_type: TriggerType = TriggerType.POLICY_BREACH
    value: float = 0.0
    operator: str = ">="          # >=, >, <=, <
    target_state: GovernanceStateType = GovernanceStateType.WATCH
    severity: Severity = Severity.LOW
    description: str = ""
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_breached(self, observed: float) -> bool:
        """Check if the observed value breaches this threshold."""
        try:
            if self.operator == ">=":
                return observed >= self.value
            elif self.operator == ">":
                return observed > self.value
            elif self.operator == "<=":
                return observed <= self.value
            elif self.operator == "<":
                return observed < self.value
            elif self.operator == "==":
                return observed == self.value
        except (TypeError, ValueError):
            pass
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "threshold_id": self.threshold_id,
            "name": self.name,
            "metric": self.metric,
            "trigger_type": self.trigger_type.name,
            "value": self.value,
            "operator": self.operator,
            "target_state": self.target_state.name,
            "severity": self.severity.name,
            "enabled": self.enabled,
        }


# ── Standard Thresholds ──

STANDARD_THRESHOLDS: List[GovernanceThreshold] = [
    # Drawdown thresholds
    GovernanceThreshold(
        threshold_id="TH-DD-WATCH",
        name="Drawdown Watch",
        metric="portfolio_drawdown",
        trigger_type=TriggerType.DRAWDOWN_BREACH,
        value=0.02,
        operator=">=",
        target_state=GovernanceStateType.WATCH,
        severity=Severity.LOW,
        description="Portfolio drawdown >= 2%",
    ),
    GovernanceThreshold(
        threshold_id="TH-DD-RESTRICT",
        name="Drawdown Restrict",
        metric="portfolio_drawdown",
        trigger_type=TriggerType.DRAWDOWN_BREACH,
        value=0.04,
        operator=">=",
        target_state=GovernanceStateType.RESTRICTED,
        severity=Severity.MEDIUM,
        description="Portfolio drawdown >= 4%",
    ),
    GovernanceThreshold(
        threshold_id="TH-DD-FREEZE",
        name="Drawdown Freeze",
        metric="portfolio_drawdown",
        trigger_type=TriggerType.DRAWDOWN_BREACH,
        value=0.06,
        operator=">=",
        target_state=GovernanceStateType.FROZEN,
        severity=Severity.HIGH,
        description="Portfolio drawdown >= 6%",
    ),
    # VaR thresholds
    GovernanceThreshold(
        threshold_id="TH-VAR-WATCH",
        name="VaR Watch",
        metric="value_at_risk",
        trigger_type=TriggerType.VAR_BREACH,
        value=0.015,
        operator=">=",
        target_state=GovernanceStateType.WATCH,
        severity=Severity.LOW,
        description="VaR >= 1.5%",
    ),
    GovernanceThreshold(
        threshold_id="TH-VAR-RESTRICT",
        name="VaR Restrict",
        metric="value_at_risk",
        trigger_type=TriggerType.VAR_BREACH,
        value=0.025,
        operator=">=",
        target_state=GovernanceStateType.RESTRICTED,
        severity=Severity.MEDIUM,
        description="VaR >= 2.5%",
    ),
    # Exposure thresholds
    GovernanceThreshold(
        threshold_id="TH-EXP-RESTRICT",
        name="Exposure Restrict",
        metric="portfolio_exposure",
        trigger_type=TriggerType.EXPOSURE_BREACH,
        value=0.15,
        operator=">",
        target_state=GovernanceStateType.RESTRICTED,
        severity=Severity.MEDIUM,
        description="Portfolio exposure > 15%",
    ),
    GovernanceThreshold(
        threshold_id="TH-EXP-FREEZE",
        name="Exposure Freeze",
        metric="portfolio_exposure",
        trigger_type=TriggerType.EXPOSURE_BREACH,
        value=0.20,
        operator=">",
        target_state=GovernanceStateType.FROZEN,
        severity=Severity.HIGH,
        description="Portfolio exposure > 20%",
    ),
    # Leverage thresholds
    GovernanceThreshold(
        threshold_id="TH-LEV-RESTRICT",
        name="Leverage Restrict",
        metric="leverage_ratio",
        trigger_type=TriggerType.LEVERAGE_BREACH,
        value=2.0,
        operator=">",
        target_state=GovernanceStateType.RESTRICTED,
        severity=Severity.MEDIUM,
        description="Leverage > 2x",
    ),
    GovernanceThreshold(
        threshold_id="TH-LEV-FREEZE",
        name="Leverage Freeze",
        metric="leverage_ratio",
        trigger_type=TriggerType.LEVERAGE_BREACH,
        value=3.0,
        operator=">",
        target_state=GovernanceStateType.FROZEN,
        severity=Severity.HIGH,
        description="Leverage > 3x",
    ),
    # Stress test thresholds
    GovernanceThreshold(
        threshold_id="TH-STRESS-RESTRICT",
        name="Stress Restrict",
        metric="stress_score",
        trigger_type=TriggerType.STRESS_BREACH,
        value=80,
        operator=">=",
        target_state=GovernanceStateType.RESTRICTED,
        severity=Severity.MEDIUM,
        description="Stress score >= 80",
    ),
    GovernanceThreshold(
        threshold_id="TH-STRESS-FREEZE",
        name="Stress Freeze",
        metric="stress_score",
        trigger_type=TriggerType.STRESS_BREACH,
        value=90,
        operator=">=",
        target_state=GovernanceStateType.FROZEN,
        severity=Severity.HIGH,
        description="Stress score >= 90",
    ),
    # Liquidity thresholds
    GovernanceThreshold(
        threshold_id="TH-LIQ-WATCH",
        name="Liquidity Watch",
        metric="liquidity_score",
        trigger_type=TriggerType.LIQUIDITY_BREACH,
        value=0.3,
        operator="<=",
        target_state=GovernanceStateType.WATCH,
        severity=Severity.LOW,
        description="Liquidity score <= 30%",
    ),
    GovernanceThreshold(
        threshold_id="TH-LIQ-RESTRICT",
        name="Liquidity Restrict",
        metric="liquidity_score",
        trigger_type=TriggerType.LIQUIDITY_BREACH,
        value=0.2,
        operator="<=",
        target_state=GovernanceStateType.RESTRICTED,
        severity=Severity.MEDIUM,
        description="Liquidity score <= 20%",
    ),
    # Slippage thresholds
    GovernanceThreshold(
        threshold_id="TH-SLIPPAGE-RESTRICT",
        name="Slippage Restrict",
        metric="execution_slippage_bps",
        trigger_type=TriggerType.SLIPPAGE_BREACH,
        value=50,
        operator=">=",
        target_state=GovernanceStateType.RESTRICTED,
        severity=Severity.MEDIUM,
        description="Slippage >= 50 bps",
    ),
    GovernanceThreshold(
        threshold_id="TH-SLIPPAGE-PAUSE",
        name="Slippage Pause",
        metric="execution_slippage_bps",
        trigger_type=TriggerType.SLIPPAGE_BREACH,
        value=100,
        operator=">=",
        target_state=GovernanceStateType.FROZEN,
        severity=Severity.HIGH,
        description="Slippage >= 100 bps",
    ),
]
