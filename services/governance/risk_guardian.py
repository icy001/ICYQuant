"""
Risk Guardian — proactive risk monitor and anomaly detector.

Part 1.5: monitors risk metrics (drawdown, VaR, exposure, leverage, etc.)
and produces governance signals when thresholds are breached.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from .governance_signal import GovernanceSignal, SignalType
from .governance_state import GovernanceRuntimeState
from .control_trigger import ControlTrigger, TriggerType, Severity
from .control_state import GovernanceStateType


class RiskGuardian:
    """Monitors risk metrics and detects governance-relevant breaches.

    Acts as the RISK layer of autonomous governance, detecting:
      - Drawdown breaches
      - VaR breaches
      - Exposure / Leverage / Concentration breaches
      - Liquidity issues
      - Stress test anomalies
    """

    def __init__(self, risk_engine: Any = None):
        self._risk_engine = risk_engine  # Optional external risk engine
        self._alerts: List[Dict[str, Any]] = []
        self._detection_count: int = 0

        # Configurable thresholds
        self._drawdown_watch: float = 0.02
        self._drawdown_restrict: float = 0.04
        self._drawdown_freeze: float = 0.06
        self._var_watch: float = 0.015
        self._var_restrict: float = 0.025
        self._exposure_restrict: float = 0.15
        self._exposure_freeze: float = 0.20
        self._leverage_restrict: float = 2.0
        self._leverage_freeze: float = 3.0
        self._stress_restrict: float = 80.0
        self._stress_freeze: float = 90.0
        self._max_concentration: float = 0.25
        self._liquidity_min: float = 0.2

    def check(self, state: Optional[GovernanceRuntimeState] = None) -> List[ControlTrigger]:
        """Check risk metrics and return control triggers.

        Args:
            state: Optional GovernanceRuntimeState snapshot.

        Returns:
            List of ControlTrigger objects for detected breaches.
        """
        triggers: List[ControlTrigger] = []
        corr_id = f"CORR-{uuid.uuid4().hex[:8].upper()}"

        if state is None:
            state = GovernanceRuntimeState.create_default()

        checks = [
            # (value, threshold, trigger_type, severity, description)
            (state.portfolio_drawdown, self._drawdown_freeze, TriggerType.DRAWDOWN_BREACH,
             Severity.HIGH, f"Drawdown {state.portfolio_drawdown:.2%} >= {self._drawdown_freeze:.0%} → FREEZE"),
            (state.portfolio_drawdown, self._drawdown_restrict, TriggerType.DRAWDOWN_BREACH,
             Severity.MEDIUM, f"Drawdown {state.portfolio_drawdown:.2%} >= {self._drawdown_restrict:.0%} → RESTRICT"),
            (state.portfolio_drawdown, self._drawdown_watch, TriggerType.DRAWDOWN_BREACH,
             Severity.LOW, f"Drawdown {state.portfolio_drawdown:.2%} >= {self._drawdown_watch:.0%} → WATCH"),
            (state.value_at_risk, self._var_restrict, TriggerType.VAR_BREACH,
             Severity.MEDIUM, f"VaR {state.value_at_risk:.2%} >= {self._var_restrict:.2%}"),
            (state.value_at_risk, self._var_watch, TriggerType.VAR_BREACH,
             Severity.LOW, f"VaR {state.value_at_risk:.2%} >= {self._var_watch:.2%}"),
            (state.portfolio_exposure, self._exposure_freeze, TriggerType.EXPOSURE_BREACH,
             Severity.HIGH, f"Exposure {state.portfolio_exposure:.0%} > {self._exposure_freeze:.0%} → FREEZE"),
            (state.portfolio_exposure, self._exposure_restrict, TriggerType.EXPOSURE_BREACH,
             Severity.MEDIUM, f"Exposure {state.portfolio_exposure:.0%} > {self._exposure_restrict:.0%}"),
            (state.leverage_ratio, self._leverage_freeze, TriggerType.LEVERAGE_BREACH,
             Severity.HIGH, f"Leverage {state.leverage_ratio:.1f}x > {self._leverage_freeze:.0f}x"),
            (state.leverage_ratio, self._leverage_restrict, TriggerType.LEVERAGE_BREACH,
             Severity.MEDIUM, f"Leverage {state.leverage_ratio:.1f}x > {self._leverage_restrict:.0f}x"),
            (state.stress_score, self._stress_freeze, TriggerType.STRESS_BREACH,
             Severity.HIGH, f"Stress {state.stress_score:.0f} >= {self._stress_freeze:.0f} → FREEZE"),
            (state.stress_score, self._stress_restrict, TriggerType.STRESS_BREACH,
             Severity.MEDIUM, f"Stress {state.stress_score:.0f} >= {self._stress_restrict:.0f}"),
        ]

        for value, threshold, trigger_type, severity, description in checks:
            if value is None or threshold is None:
                continue
            if value >= threshold:
                trigger = ControlTrigger(
                    trigger_id=f"TRG-{uuid.uuid4().hex[:12].upper()}",
                    trigger_type=trigger_type,
                    severity=severity,
                    source="risk-guardian",
                    description=description,
                    value=value,
                    threshold=threshold,
                    correlation_id=corr_id,
                )
                triggers.append(trigger)

        # Check liquidity (inverse: lower is worse)
        if state.liquidity_score is not None and state.liquidity_score <= self._liquidity_min:
            triggers.append(ControlTrigger(
                trigger_id=f"TRG-{uuid.uuid4().hex[:12].upper()}",
                trigger_type=TriggerType.LIQUIDITY_BREACH,
                severity=Severity.MEDIUM,
                source="risk-guardian",
                description=f"Liquidity {state.liquidity_score:.0%} <= {self._liquidity_min:.0%}",
                value=state.liquidity_score,
                threshold=self._liquidity_min,
                correlation_id=corr_id,
            ))

        # Track
        if triggers:
            self._detection_count += len(triggers)
            self._alerts.append({
                "timestamp": time.time(),
                "triggers": [t.to_dict() for t in triggers],
            })

        return triggers

    def get_alerts(self, limit: int = 100) -> List[Dict[str, Any]]:
        return list(reversed(self._alerts[-limit:]))

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "alerts_count": self._detection_count,
            "thresholds": {
                "drawdown_watch": self._drawdown_watch,
                "drawdown_restrict": self._drawdown_restrict,
                "drawdown_freeze": self._drawdown_freeze,
                "var_watch": self._var_watch,
                "var_restrict": self._var_restrict,
                "exposure_restrict": self._exposure_restrict,
                "exposure_freeze": self._exposure_freeze,
                "leverage_restrict": self._leverage_restrict,
                "leverage_freeze": self._leverage_freeze,
            },
        }
