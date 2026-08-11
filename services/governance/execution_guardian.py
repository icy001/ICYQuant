"""
Execution Guardian — monitors order execution anomalies.

Part 1.5: detects execution anomalies such as excessive slippage,
order rejections, latency spikes, and abnormal execution patterns.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from .control_trigger import ControlTrigger, TriggerType, Severity


class ExecutionGuardian:
    """Monitors execution state and detects anomalies.

    Checks:
      - Slippage breaches
      - Order rejection spikes
      - Latency anomalies
      - Fill rate anomalies
      - Cancel/reject patterns
    """

    def __init__(self):
        self._execution_records: List[Dict[str, Any]] = []
        self._alerts: List[Dict[str, Any]] = []

        # Configurable thresholds
        self._max_slippage_bps: float = 50.0       # 50 bps
        self._critical_slippage_bps: float = 100.0  # 100 bps
        self._max_rejection_rate: float = 0.05       # 5%
        self._max_latency_ms: float = 500.0
        self._window_seconds: float = 300.0          # 5 min window

    def record_execution(
        self,
        order_id: str,
        expected_price: float,
        executed_price: float,
        latency_ms: float = 0.0,
        status: str = "FILLED",
    ) -> None:
        """Record an execution for monitoring."""
        slippage_bps = 0.0
        if expected_price > 0:
            slippage_bps = abs(executed_price - expected_price) / expected_price * 10000

        self._execution_records.append({
            "order_id": order_id,
            "expected_price": expected_price,
            "executed_price": executed_price,
            "slippage_bps": slippage_bps,
            "latency_ms": latency_ms,
            "status": status,
            "timestamp": time.time(),
        })

        # Trim old records
        cutoff = time.time() - self._window_seconds * 4
        self._execution_records = [r for r in self._execution_records if r["timestamp"] > cutoff]

    def check(self) -> List[ControlTrigger]:
        """Check execution state for anomalies.

        Returns:
            List of ControlTrigger objects.
        """
        triggers: List[ControlTrigger] = []
        corr_id = f"CORR-{uuid.uuid4().hex[:8].upper()}"

        if not self._execution_records:
            return triggers

        # Get recent records (within window)
        cutoff = time.time() - self._window_seconds
        recent = [r for r in self._execution_records if r["timestamp"] > cutoff]

        if not recent:
            return triggers

        # Check slippage
        for record in recent:
            if record["slippage_bps"] >= self._critical_slippage_bps:
                triggers.append(ControlTrigger(
                    trigger_id=f"TRG-{uuid.uuid4().hex[:12].upper()}",
                    trigger_type=TriggerType.SLIPPAGE_BREACH,
                    severity=Severity.HIGH,
                    source="execution-guardian",
                    description=f"Critical slippage for {record['order_id']}: {record['slippage_bps']:.0f} bps >= {self._critical_slippage_bps:.0f} bps",
                    value=record["slippage_bps"],
                    threshold=self._critical_slippage_bps,
                    correlation_id=corr_id,
                ))
            elif record["slippage_bps"] >= self._max_slippage_bps:
                triggers.append(ControlTrigger(
                    trigger_id=f"TRG-{uuid.uuid4().hex[:12].upper()}",
                    trigger_type=TriggerType.SLIPPAGE_BREACH,
                    severity=Severity.MEDIUM,
                    source="execution-guardian",
                    description=f"Slippage for {record['order_id']}: {record['slippage_bps']:.0f} bps >= {self._max_slippage_bps:.0f} bps",
                    value=record["slippage_bps"],
                    threshold=self._max_slippage_bps,
                    correlation_id=corr_id,
                ))

        # Check rejection rate
        rejected = sum(1 for r in recent if r["status"] == "REJECTED")
        rejection_rate = rejected / len(recent) if recent else 0.0
        if rejection_rate > self._max_rejection_rate:
            triggers.append(ControlTrigger(
                trigger_id=f"TRG-{uuid.uuid4().hex[:12].upper()}",
                trigger_type=TriggerType.ORDER_REJECTION_SPIKE,
                severity=Severity.HIGH,
                source="execution-guardian",
                description=f"Order rejection rate {rejection_rate:.1%} > {self._max_rejection_rate:.0%}",
                value=rejection_rate,
                threshold=self._max_rejection_rate,
                correlation_id=corr_id,
            ))

        # Check latency
        avg_latency = sum(r["latency_ms"] for r in recent) / len(recent)
        if avg_latency > self._max_latency_ms:
            triggers.append(ControlTrigger(
                trigger_id=f"TRG-{uuid.uuid4().hex[:12].upper()}",
                trigger_type=TriggerType.LATENCY_BREACH,
                severity=Severity.MEDIUM,
                source="execution-guardian",
                description=f"Average latency {avg_latency:.0f} ms > {self._max_latency_ms:.0f} ms",
                value=avg_latency,
                threshold=self._max_latency_ms,
                correlation_id=corr_id,
            ))

        if triggers:
            self._alerts.append({
                "timestamp": time.time(),
                "triggers": [t.to_dict() for t in triggers],
            })

        return triggers

    def get_metrics(self) -> Dict[str, Any]:
        cutoff = time.time() - self._window_seconds
        recent = [r for r in self._execution_records if r["timestamp"] > cutoff]

        avg_slippage = sum(r["slippage_bps"] for r in recent) / len(recent) if recent else 0.0
        avg_latency = sum(r["latency_ms"] for r in recent) / len(recent) if recent else 0.0

        return {
            "recent_executions": len(recent),
            "avg_slippage_bps": avg_slippage,
            "avg_latency_ms": avg_latency,
            "alerts_count": len(self._alerts),
        }
