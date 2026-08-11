"""
Governance Detector — detects governance anomalies from system state.

Part 1.5: polls governance state and converts breaches into signals.
Supports multiple detector types (risk, policy, authority, etc.).
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional, Callable

from .governance_signal import GovernanceSignal, SignalType
from .governance_threshold import GovernanceThreshold
from .governance_state import GovernanceRuntimeState
from .control_trigger import Severity
from .control_state import GovernanceStateType


class GovernanceDetector:
    """Detects governance signals from runtime state.

    Evaluates thresholds against current state and produces signals
    for the control plane.
    """

    def __init__(self):
        self._thresholds: Dict[str, GovernanceThreshold] = {}
        self._detection_count: int = 0
        self._last_detection: float = 0.0

    def add_threshold(self, threshold: GovernanceThreshold) -> None:
        self._thresholds[threshold.threshold_id] = threshold

    def add_thresholds(self, thresholds: List[GovernanceThreshold]) -> None:
        for t in thresholds:
            self.add_threshold(t)

    def detect(self, state: GovernanceRuntimeState) -> List[GovernanceSignal]:
        """Detect governance signals from runtime state.

        Compares state metrics against all registered thresholds.
        """
        signals: List[GovernanceSignal] = []
        correlation_id = f"CORR-{uuid.uuid4().hex[:8].upper()}"

        for threshold in self._thresholds.values():
            metric_value = getattr(state, threshold.metric, None)
            if metric_value is None:
                continue

            if not threshold.is_breached(metric_value):
                continue

            # Map SignalType
            signal_type_map = {
                "DRAWDOWN_BREACH": SignalType.DRAWDOWN_BREACH,
                "VAR_BREACH": SignalType.VAR_BREACH,
                "EXPOSURE_BREACH": SignalType.EXPOSURE_BREACH,
                "LEVERAGE_BREACH": SignalType.LEVERAGE_BREACH,
                "LIQUIDITY_BREACH": SignalType.LIQUIDITY_BREACH,
                "STRESS_BREACH": SignalType.RISK_BREACH,
                "SLIPPAGE_BREACH": SignalType.SLIPPAGE_BREACH,
            }

            sig_type = signal_type_map.get(
                threshold.trigger_type.name,
                SignalType.RISK_BREACH,
            )

            signal = GovernanceSignal.create(
                signal_type=sig_type,
                severity=threshold.severity,
                value=metric_value,
                threshold=threshold.value,
                source="governance-detector",
                description=threshold.description,
                correlation_id=correlation_id,
            )
            signal.target_state = threshold.target_state.name
            signals.append(signal)

        self._detection_count += len(signals)
        if signals:
            self._last_detection = time.time()

        return signals

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "thresholds_count": len(self._thresholds),
            "detection_count": self._detection_count,
            "last_detection": self._last_detection,
        }


class RiskDetector:
    """Detects risk-specific governance signals."""

    def __init__(self, thresholds: Optional[List[GovernanceThreshold]] = None):
        self._detector = GovernanceDetector()
        if thresholds:
            self._detector.add_thresholds(thresholds)

    def detect(self, state: GovernanceRuntimeState) -> List[GovernanceSignal]:
        return [s for s in self._detector.detect(state)
                if s.signal_type in (SignalType.DRAWDOWN_BREACH, SignalType.VAR_BREACH,
                                      SignalType.EXPOSURE_BREACH, SignalType.LEVERAGE_BREACH,
                                      SignalType.LIQUIDITY_BREACH, SignalType.RISK_BREACH)]


class ExecutionDetector:
    """Detects execution-specific governance signals."""

    def __init__(self, thresholds: Optional[List[GovernanceThreshold]] = None):
        self._detector = GovernanceDetector()
        if thresholds:
            self._detector.add_thresholds(thresholds)

    def detect(self, state: GovernanceRuntimeState) -> List[GovernanceSignal]:
        return [s for s in self._detector.detect(state)
                if s.signal_type == SignalType.SLIPPAGE_BREACH]
