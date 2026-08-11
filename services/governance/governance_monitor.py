"""
Governance Monitor — unified governance system monitor.

Part 1.5: polls the governance system state, runs detectors, and produces
signals for the control plane. Acts as the OBSERVE phase bridge between
the runtime system and the control plane.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from .governance_state import GovernanceRuntimeState
from .governance_signal import GovernanceSignal, SignalType
from .governance_threshold import GovernanceThreshold, STANDARD_THRESHOLDS
from .governance_detector import GovernanceDetector, RiskDetector, ExecutionDetector
from .control_trigger import ControlTrigger, TriggerType, Severity
from .control_state import GovernanceStateType


class GovernanceMonitor:
    """Unified governance system monitor.

    Continuously polls the governance runtime state and detects anomalies.
    Converts detections into signals for the control plane.
    """

    def __init__(self):
        self._detector = GovernanceDetector()
        self._detector.add_thresholds(STANDARD_THRESHOLDS)

        # Sub-detectors
        self._risk_detector = RiskDetector(STANDARD_THRESHOLDS)
        self._execution_detector = ExecutionDetector(STANDARD_THRESHOLDS)

        # History
        self._signals_history: List[GovernanceSignal] = []
        self._state_snapshots: List[GovernanceRuntimeState] = []
        self._max_history = 10000

        # Metrics
        self._monitor_cycles: int = 0
        self._total_signals: int = 0

    def observe(self, state: GovernanceRuntimeState) -> Dict[str, Any]:
        """Observe the current governance state and detect issues.

        Returns:
            Dict with signals, breaches, and current state summary.
        """
        self._monitor_cycles += 1

        # Store snapshot
        self._state_snapshots.append(state)
        if len(self._state_snapshots) > self._max_history:
            self._state_snapshots = self._state_snapshots[-self._max_history:]

        # Detect signals
        signals = self._detector.detect(state)

        # Also run specific detectors
        risk_signals = self._risk_detector.detect(state)
        exec_signals = self._execution_detector.detect(state)

        all_signals = signals + risk_signals + exec_signals

        # Store signals
        self._signals_history.extend(all_signals)
        self._total_signals += len(all_signals)
        if len(self._signals_history) > self._max_history:
            self._signals_history = self._signals_history[-self._max_history:]

        # Convert to ControlTriggers for the control plane
        triggers = self._to_control_triggers(all_signals)

        # Health assessment
        health = self._assess_health(state)

        return {
            "state": state.to_dict(),
            "signals": [s.to_dict() for s in all_signals],
            "triggers": [t.to_dict() for t in triggers],
            "breaches": state.get_breaches(STANDARD_THRESHOLDS),
            "signals_count": len(all_signals),
            "health": health,
            "monitor_cycle": self._monitor_cycles,
        }

    def _to_control_triggers(self, signals: List[GovernanceSignal]) -> List[ControlTrigger]:
        """Convert GovernanceSignals to ControlTriggers."""
        triggers = []

        # Map signal types to trigger types
        signal_to_trigger = {
            SignalType.RISK_BREACH: TriggerType.RISK_BREACH,
            SignalType.DRAWDOWN_BREACH: TriggerType.DRAWDOWN_BREACH,
            SignalType.VAR_BREACH: TriggerType.VAR_BREACH,
            SignalType.EXPOSURE_BREACH: TriggerType.EXPOSURE_BREACH,
            SignalType.LEVERAGE_BREACH: TriggerType.LEVERAGE_BREACH,
            SignalType.LIQUIDITY_BREACH: TriggerType.LIQUIDITY_BREACH,
            SignalType.POLICY_BREACH: TriggerType.POLICY_BREACH,
            SignalType.AUTHORITY_BREACH: TriggerType.AUTHORITY_BREACH,
            SignalType.SLIPPAGE_BREACH: TriggerType.SLIPPAGE_BREACH,
            SignalType.EXECUTION_ANOMALY: TriggerType.EXECUTION_ANOMALY,
            SignalType.AUDIT_INTEGRITY_FAILURE: TriggerType.AUDIT_INTEGRITY_FAILURE,
            SignalType.SERVICE_DEGRADATION: TriggerType.SERVICE_DEGRADATION,
        }

        for signal in signals:
            trigger_type = signal_to_trigger.get(signal.signal_type, TriggerType.POLICY_BREACH)
            trigger = ControlTrigger(
                trigger_id=f"TRG-{uuid.uuid4().hex[:12].upper()}",
                trigger_type=trigger_type,
                severity=signal.severity,
                source=signal.source,
                description=signal.description,
                value=signal.value,
                threshold=signal.threshold,
                observed_at=signal.observed_at,
                correlation_id=signal.correlation_id,
            )
            triggers.append(trigger)

        return triggers

    def _assess_health(self, state: GovernanceRuntimeState) -> Dict[str, Any]:
        """Assess overall governance health."""
        health_checks = [
            state.risk_engine_healthy,
            state.policy_engine_healthy,
            state.approval_engine_healthy,
            state.audit_engine_healthy,
            state.audit_integrity_valid,
            state.audit_chain_intact,
        ]

        all_healthy = all(health_checks)
        degraded = [name for name, ok in zip(
            ["risk_engine", "policy_engine", "approval_engine", "audit_engine",
             "audit_integrity", "audit_chain"],
            health_checks,
        ) if not ok]

        return {
            "healthy": all_healthy,
            "degraded_components": degraded,
            "risks": [
                {"metric": "drawdown", "value": state.portfolio_drawdown, "status": "OK" if state.portfolio_drawdown < 0.02 else "ELEVATED"},
                {"metric": "var", "value": state.value_at_risk, "status": "OK" if state.value_at_risk < 0.015 else "ELEVATED"},
                {"metric": "exposure", "value": state.portfolio_exposure, "status": "OK" if state.portfolio_exposure <= 0.15 else "ELEVATED"},
                {"metric": "leverage", "value": state.leverage_ratio, "status": "OK" if state.leverage_ratio <= 2.0 else "ELEVATED"},
                {"metric": "stress", "value": state.stress_score, "status": "OK" if state.stress_score < 80 else "ELEVATED"},
            ],
        }

    def get_triggers(self) -> List[ControlTrigger]:
        """Get all detected control triggers from recent signals."""
        return self._to_control_triggers(self._signals_history[-100:])

    def get_recent_signals(self, limit: int = 100) -> List[GovernanceSignal]:
        return list(reversed(self._signals_history[-limit:]))

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "monitor_cycles": self._monitor_cycles,
            "total_signals": self._total_signals,
            "recent_signals_count": len(self._signals_history),
            "snapshots_count": len(self._state_snapshots),
        }
